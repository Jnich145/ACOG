"""
Audio/Voice API endpoints for ElevenLabs TTS integration.

Provides endpoints for:
- Listing available voices
- Getting voice details and settings
- Generating audio previews
- Generating full episode audio
"""

import base64
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from acog.core.config import Settings, get_settings
from acog.core.database import get_db
from acog.core.exceptions import NotFoundError, ValidationError
from acog.integrations.elevenlabs_client import (
    ElevenLabsClient,
    Voice,
    VoiceSettings,
    get_elevenlabs_client,
)
from acog.models.channel import Channel
from acog.models.episode import Episode
from acog.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class VoiceResponse(BaseModel):
    """Voice information response."""

    voice_id: str
    name: str
    category: str
    description: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    preview_url: str | None = None
    settings: dict[str, Any] | None = None

    @classmethod
    def from_voice(cls, voice: Voice) -> "VoiceResponse":
        """Create from Voice dataclass."""
        return cls(
            voice_id=voice.voice_id,
            name=voice.name,
            category=voice.category,
            description=voice.description,
            labels=voice.labels,
            preview_url=voice.preview_url,
            settings=voice.settings.model_dump() if voice.settings else None,
        )


class VoiceListResponse(BaseModel):
    """Response for voice listing."""

    voices: list[VoiceResponse]
    total: int


class AudioPreviewRequest(BaseModel):
    """Request for generating audio preview."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text to convert to speech (max 5000 characters for preview)",
    )
    voice_id: str = Field(..., description="ElevenLabs voice ID")
    stability: float = Field(default=0.5, ge=0.0, le=1.0, description="Voice stability")
    similarity_boost: float = Field(
        default=0.75, ge=0.0, le=1.0, description="Speaker similarity boost"
    )
    style: float = Field(default=0.0, ge=0.0, le=1.0, description="Style exaggeration")


class AudioPreviewResponse(BaseModel):
    """Response for audio preview (non-streaming)."""

    audio_base64: str = Field(description="Base64-encoded MP3 audio data")
    content_type: str = Field(default="audio/mpeg")
    character_count: int
    estimated_duration_seconds: float
    estimated_cost_usd: float
    voice_id: str
    model_id: str


class EpisodeAudioRequest(BaseModel):
    """Request for generating episode audio."""

    voice_id: str | None = Field(
        default=None,
        description="Override voice ID (uses channel default if not provided)",
    )
    stability: float | None = Field(default=None, ge=0.0, le=1.0)
    similarity_boost: float | None = Field(default=None, ge=0.0, le=1.0)
    style: float | None = Field(default=None, ge=0.0, le=1.0)
    save_to_storage: bool = Field(
        default=True, description="Save generated audio to S3 storage"
    )


class EpisodeAudioResponse(BaseModel):
    """Response for episode audio generation."""

    episode_id: str
    audio_base64: str | None = Field(
        default=None, description="Base64-encoded audio (if not saved to storage)"
    )
    storage_uri: str | None = Field(default=None, description="S3 URI (if saved)")
    character_count: int
    estimated_duration_seconds: float
    estimated_cost_usd: float
    voice_id: str
    model_id: str


# =============================================================================
# Dependencies
# =============================================================================


def get_elevenlabs_or_error(settings: Settings = Depends(get_settings)) -> ElevenLabsClient:
    """
    Get ElevenLabs client, raising error if not configured.

    Raises:
        ValidationError: If ElevenLabs API key is not configured
    """
    if not settings.elevenlabs_api_key:
        raise ValidationError(
            message="ElevenLabs API key is not configured. Set ELEVENLABS_API_KEY environment variable.",
            field="elevenlabs_api_key",
        )
    return get_elevenlabs_client(settings)


# =============================================================================
# Voice Endpoints
# =============================================================================


@router.get(
    "/voices",
    response_model=ApiResponse[VoiceListResponse],
    summary="List Available Voices",
    description="Get all available ElevenLabs voices for text-to-speech.",
)
async def list_voices(
    settings: Settings = Depends(get_settings),
    show_legacy: bool = Query(default=False, description="Include legacy voices"),
) -> ApiResponse[VoiceListResponse]:
    """
    List all available ElevenLabs voices.

    Returns premade voices and any custom/cloned voices associated with the account.
    """
    client = get_elevenlabs_or_error(settings)

    try:
        voices = client.list_voices(show_legacy=show_legacy)
        voice_responses = [VoiceResponse.from_voice(v) for v in voices]

        return ApiResponse(
            data=VoiceListResponse(
                voices=voice_responses,
                total=len(voice_responses),
            )
        )
    finally:
        client.close()


@router.get(
    "/voices/{voice_id}",
    response_model=ApiResponse[VoiceResponse],
    summary="Get Voice Details",
    description="Get details and default settings for a specific voice.",
)
async def get_voice(
    voice_id: str,
    settings: Settings = Depends(get_settings),
) -> ApiResponse[VoiceResponse]:
    """
    Get details for a specific voice including default settings.
    """
    client = get_elevenlabs_or_error(settings)

    try:
        voice = client.get_voice(voice_id)
        return ApiResponse(data=VoiceResponse.from_voice(voice))
    finally:
        client.close()


@router.get(
    "/voices/defaults",
    response_model=ApiResponse[dict[str, str]],
    summary="Get Default Voice IDs",
    description="Get mapping of common voice names to their IDs.",
)
async def get_default_voices() -> ApiResponse[dict[str, str]]:
    """
    Get mapping of default voice names to their ElevenLabs voice IDs.

    Useful for quick reference when selecting voices.
    """
    return ApiResponse(data=ElevenLabsClient.DEFAULT_VOICES)


# =============================================================================
# Audio Preview Endpoints
# =============================================================================


@router.post(
    "/preview",
    response_model=ApiResponse[AudioPreviewResponse],
    summary="Generate Audio Preview",
    description="Generate a short audio preview from text. Limited to 5000 characters.",
)
async def generate_audio_preview(
    request: AudioPreviewRequest,
    settings: Settings = Depends(get_settings),
) -> ApiResponse[AudioPreviewResponse]:
    """
    Generate audio preview from text.

    This endpoint is for testing voice settings before committing to
    full episode audio generation. Returns base64-encoded audio.

    Cost is tracked and returned in the response.
    """
    client = get_elevenlabs_or_error(settings)

    try:
        voice_settings = VoiceSettings(
            stability=request.stability,
            similarity_boost=request.similarity_boost,
            style=request.style,
        )

        result = client.generate_speech(
            text=request.text,
            voice_id=request.voice_id,
            voice_settings=voice_settings,
        )

        # Encode audio as base64
        audio_base64 = base64.b64encode(result.audio_data).decode("utf-8")

        return ApiResponse(
            data=AudioPreviewResponse(
                audio_base64=audio_base64,
                content_type=result.content_type,
                character_count=result.character_count,
                estimated_duration_seconds=result.duration_seconds or 0,
                estimated_cost_usd=float(result.usage.estimated_cost_usd) if result.usage else 0,
                voice_id=result.voice_id,
                model_id=result.model_id,
            )
        )
    finally:
        client.close()


@router.post(
    "/preview/stream",
    summary="Stream Audio Preview (POST)",
    description="Generate audio preview with streaming response for real-time playback.",
)
async def stream_audio_preview(
    request: AudioPreviewRequest,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """
    Generate audio with streaming response (POST version).

    Returns audio data as it's generated, enabling real-time playback
    in the browser without waiting for full generation.
    """
    client = get_elevenlabs_or_error(settings)

    voice_settings = VoiceSettings(
        stability=request.stability,
        similarity_boost=request.similarity_boost,
        style=request.style,
    )

    def audio_stream():
        try:
            for chunk in client.generate_speech_stream(
                text=request.text,
                voice_id=request.voice_id,
                voice_settings=voice_settings,
            ):
                yield chunk
        finally:
            client.close()

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=preview.mp3",
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/preview/stream",
    summary="Stream Audio Preview (GET)",
    description="Generate audio preview with streaming response. GET version for browser audio elements.",
)
async def stream_audio_preview_get(
    text: str = Query(..., min_length=1, max_length=5000, description="Text to convert to speech"),
    voice_id: str = Query(..., description="ElevenLabs voice ID"),
    stability: float = Query(default=0.5, ge=0.0, le=1.0, description="Voice stability"),
    similarity_boost: float = Query(default=0.75, ge=0.0, le=1.0, description="Speaker similarity"),
    style: float = Query(default=0.0, ge=0.0, le=1.0, description="Style exaggeration"),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """
    Generate audio with streaming response (GET version).

    This GET endpoint allows browser audio elements to directly use the URL
    as their src attribute for streaming audio playback.
    """
    client = get_elevenlabs_or_error(settings)

    voice_settings = VoiceSettings(
        stability=stability,
        similarity_boost=similarity_boost,
        style=style,
    )

    def audio_stream():
        try:
            for chunk in client.generate_speech_stream(
                text=text,
                voice_id=voice_id,
                voice_settings=voice_settings,
            ):
                yield chunk
        finally:
            client.close()

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=preview.mp3",
            "Cache-Control": "no-cache",
        },
    )


# =============================================================================
# Episode Audio Endpoints
# =============================================================================


@router.post(
    "/episodes/{episode_id}/generate",
    response_model=ApiResponse[EpisodeAudioResponse],
    summary="Generate Episode Audio",
    description="Generate full audio for an episode's script using channel voice settings.",
)
async def generate_episode_audio(
    episode_id: UUID,
    request: EpisodeAudioRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiResponse[EpisodeAudioResponse]:
    """
    Generate audio from an episode's script.

    Uses the channel's voice_profile settings unless overridden in the request.
    Can optionally save the generated audio to S3 storage.
    """
    # Fetch episode
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError("Episode", str(episode_id))

    if not episode.script:
        raise ValidationError(
            message="Episode has no script. Generate a script first.",
            field="script",
        )

    # Fetch channel for voice settings
    channel = (
        db.query(Channel)
        .filter(Channel.id == episode.channel_id, Channel.deleted_at.is_(None))
        .first()
    )
    if not channel:
        raise NotFoundError("Channel", str(episode.channel_id))

    # Get voice settings from channel or request
    channel_voice = channel.get_voice_settings()
    voice_id = request.voice_id or channel_voice.get("voice_id")

    if not voice_id:
        raise ValidationError(
            message="No voice_id specified and channel has no default voice configured.",
            field="voice_id",
        )

    # Build voice settings
    voice_settings = VoiceSettings(
        stability=request.stability if request.stability is not None else channel_voice.get("stability", 0.5),
        similarity_boost=request.similarity_boost if request.similarity_boost is not None else channel_voice.get("similarity_boost", 0.75),
        style=request.style if request.style is not None else channel_voice.get("style", 0.0),
    )

    # Extract speakable text from script (AVATAR and VO markers)
    import re
    pattern = r'\[(AVATAR|VO):\s*([^\]]+)\]'
    matches = re.findall(pattern, episode.script)
    speakable_text = " ".join(text.strip() for _, text in matches)

    if not speakable_text:
        raise ValidationError(
            message="Script contains no speakable text (no [AVATAR:] or [VO:] markers found).",
            field="script",
        )

    client = get_elevenlabs_or_error(settings)

    try:
        if request.save_to_storage:
            # Generate and save to S3
            from acog.integrations.storage_client import get_storage_client
            storage = get_storage_client(settings)

            result = client.generate_speech_and_save(
                text=speakable_text,
                voice_id=voice_id,
                episode_id=episode_id,
                storage_client=storage,
                voice_settings=voice_settings,
            )

            return ApiResponse(
                data=EpisodeAudioResponse(
                    episode_id=str(episode_id),
                    storage_uri=result.storage_result.uri if result.storage_result else None,
                    character_count=result.character_count,
                    estimated_duration_seconds=result.duration_seconds or 0,
                    estimated_cost_usd=float(result.usage.estimated_cost_usd) if result.usage else 0,
                    voice_id=result.voice_id,
                    model_id=result.model_id,
                )
            )
        else:
            # Generate and return as base64
            result = client.generate_speech(
                text=speakable_text,
                voice_id=voice_id,
                voice_settings=voice_settings,
            )

            audio_base64 = base64.b64encode(result.audio_data).decode("utf-8")

            return ApiResponse(
                data=EpisodeAudioResponse(
                    episode_id=str(episode_id),
                    audio_base64=audio_base64,
                    character_count=result.character_count,
                    estimated_duration_seconds=result.duration_seconds or 0,
                    estimated_cost_usd=float(result.usage.estimated_cost_usd) if result.usage else 0,
                    voice_id=result.voice_id,
                    model_id=result.model_id,
                )
            )
    finally:
        client.close()


@router.post(
    "/episodes/{episode_id}/preview",
    response_model=ApiResponse[AudioPreviewResponse],
    summary="Preview Episode Audio",
    description="Generate a short audio preview of an episode's script (first 500 characters).",
)
async def preview_episode_audio(
    episode_id: UUID,
    voice_id: str | None = Query(default=None, description="Override voice ID"),
    stability: float = Query(default=0.5, ge=0.0, le=1.0),
    similarity_boost: float = Query(default=0.75, ge=0.0, le=1.0),
    style: float = Query(default=0.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiResponse[AudioPreviewResponse]:
    """
    Generate a short preview of the episode's script audio.

    Takes the first 500 characters of speakable text for a quick preview.
    """
    # Fetch episode
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError("Episode", str(episode_id))

    if not episode.script:
        raise ValidationError(
            message="Episode has no script. Generate a script first.",
            field="script",
        )

    # Fetch channel for voice settings
    channel = (
        db.query(Channel)
        .filter(Channel.id == episode.channel_id, Channel.deleted_at.is_(None))
        .first()
    )
    if not channel:
        raise NotFoundError("Channel", str(episode.channel_id))

    # Get voice ID
    channel_voice = channel.get_voice_settings()
    final_voice_id = voice_id or channel_voice.get("voice_id")

    if not final_voice_id:
        raise ValidationError(
            message="No voice_id specified and channel has no default voice configured.",
            field="voice_id",
        )

    # Extract speakable text
    import re
    pattern = r'\[(AVATAR|VO):\s*([^\]]+)\]'
    matches = re.findall(pattern, episode.script)
    speakable_text = " ".join(text.strip() for _, text in matches)

    if not speakable_text:
        raise ValidationError(
            message="Script contains no speakable text.",
            field="script",
        )

    # Limit to first 500 characters for preview
    preview_text = speakable_text[:500]
    if len(speakable_text) > 500:
        # Try to cut at word boundary
        last_space = preview_text.rfind(" ")
        if last_space > 400:
            preview_text = preview_text[:last_space] + "..."

    voice_settings = VoiceSettings(
        stability=stability,
        similarity_boost=similarity_boost,
        style=style,
    )

    client = get_elevenlabs_or_error(settings)

    try:
        result = client.generate_speech(
            text=preview_text,
            voice_id=final_voice_id,
            voice_settings=voice_settings,
        )

        audio_base64 = base64.b64encode(result.audio_data).decode("utf-8")

        return ApiResponse(
            data=AudioPreviewResponse(
                audio_base64=audio_base64,
                content_type=result.content_type,
                character_count=result.character_count,
                estimated_duration_seconds=result.duration_seconds or 0,
                estimated_cost_usd=float(result.usage.estimated_cost_usd) if result.usage else 0,
                voice_id=result.voice_id,
                model_id=result.model_id,
            )
        )
    finally:
        client.close()


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.get(
    "/subscription",
    response_model=ApiResponse[dict[str, Any]],
    summary="Get ElevenLabs Subscription Info",
    description="Get current ElevenLabs subscription and usage information.",
)
async def get_subscription_info(
    settings: Settings = Depends(get_settings),
) -> ApiResponse[dict[str, Any]]:
    """
    Get ElevenLabs account subscription details.

    Returns information about character quota, usage, and subscription tier.
    """
    client = get_elevenlabs_or_error(settings)

    try:
        info = client.get_user_subscription_info()
        return ApiResponse(data=info)
    finally:
        client.close()


@router.get(
    "/models",
    response_model=ApiResponse[dict[str, str]],
    summary="Get Available Models",
    description="Get available ElevenLabs TTS models.",
)
async def get_available_models() -> ApiResponse[dict[str, str]]:
    """
    Get available ElevenLabs text-to-speech models.

    Returns model IDs mapped to their descriptions.
    """
    return ApiResponse(data=ElevenLabsClient.MODELS)
