"""
ElevenLabs API client for voice synthesis.

This module provides integration with ElevenLabs text-to-speech API for:
- Voice listing and management
- High-quality speech generation
- Voice settings configuration
- Cost tracking and usage monitoring

API Reference: https://elevenlabs.io/docs/api-reference
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from acog.core.config import Settings, get_settings
from acog.core.exceptions import ExternalServiceError, ValidationError
from acog.integrations.base_client import MediaResult, SyncBaseHTTPClient, UsageMetrics
from acog.integrations.storage_client import StorageClient, UploadResult

logger = logging.getLogger(__name__)


# ElevenLabs pricing (as of early 2025)
# Pricing per 1000 characters
ELEVENLABS_PRICING: dict[str, Decimal] = {
    "free": Decimal("0"),
    "starter": Decimal("0.30"),  # $0.30 per 1000 characters
    "creator": Decimal("0.22"),
    "pro": Decimal("0.18"),
    "scale": Decimal("0.11"),
    "business": Decimal("0.07"),
}

# Default pricing tier
DEFAULT_PRICING_TIER = "creator"


class VoiceSettings(BaseModel):
    """
    Voice settings for ElevenLabs speech generation.

    Attributes:
        stability: Voice stability (0.0-1.0). Higher = more consistent
        similarity_boost: Speaker similarity boost (0.0-1.0). Higher = more similar
        style: Style exaggeration (0.0-1.0). Higher = more expressive
        use_speaker_boost: Enable speaker boost for clearer audio
    """

    stability: float = Field(default=0.5, ge=0.0, le=1.0)
    similarity_boost: float = Field(default=0.75, ge=0.0, le=1.0)
    style: float = Field(default=0.0, ge=0.0, le=1.0)
    use_speaker_boost: bool = Field(default=True)

    def to_api_format(self) -> dict[str, Any]:
        """Convert to ElevenLabs API format."""
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "use_speaker_boost": self.use_speaker_boost,
        }


@dataclass
class Voice:
    """
    ElevenLabs voice representation.

    Attributes:
        voice_id: Unique voice identifier
        name: Human-readable voice name
        category: Voice category (premade, cloned, generated)
        description: Voice description
        labels: Voice labels/tags
        preview_url: URL to voice preview audio
        settings: Default voice settings
    """

    voice_id: str
    name: str
    category: str = "premade"
    description: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    preview_url: str | None = None
    settings: VoiceSettings | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "Voice":
        """Create Voice from API response."""
        settings = None
        if "settings" in data:
            settings = VoiceSettings(
                stability=data["settings"].get("stability", 0.5),
                similarity_boost=data["settings"].get("similarity_boost", 0.75),
                style=data["settings"].get("style", 0.0),
                use_speaker_boost=data["settings"].get("use_speaker_boost", True),
            )

        return cls(
            voice_id=data["voice_id"],
            name=data["name"],
            category=data.get("category", "premade"),
            description=data.get("description"),
            labels=data.get("labels", {}),
            preview_url=data.get("preview_url"),
            settings=settings,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "voice_id": self.voice_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "labels": self.labels,
            "preview_url": self.preview_url,
            "settings": self.settings.model_dump() if self.settings else None,
        }


@dataclass
class SpeechResult:
    """
    Result container for speech generation.

    Attributes:
        audio_data: Generated audio as bytes
        content_type: Audio MIME type (typically audio/mpeg)
        character_count: Number of characters processed
        duration_ms: Estimated audio duration in milliseconds
        voice_id: Voice used for generation
        model_id: Model used for generation
        usage: Usage metrics
        storage_result: S3 upload result (if saved)
    """

    audio_data: bytes
    content_type: str = "audio/mpeg"
    character_count: int = 0
    duration_ms: int | None = None
    voice_id: str = ""
    model_id: str = ""
    usage: UsageMetrics | None = None
    storage_result: UploadResult | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Get duration in seconds."""
        if self.duration_ms is not None:
            return self.duration_ms / 1000.0
        return None

    @property
    def file_size_bytes(self) -> int:
        """Get audio file size in bytes."""
        return len(self.audio_data)


class ElevenLabsClient(SyncBaseHTTPClient):
    """
    ElevenLabs API client for text-to-speech synthesis.

    Provides high-quality voice synthesis with:
    - Multiple voice options (premade, cloned, generated)
    - Configurable voice settings (stability, similarity, style)
    - Multiple model options (multilingual, monolingual, turbo)
    - Cost tracking and usage monitoring
    - Automatic S3 upload support

    Example:
        ```python
        client = ElevenLabsClient()

        # List available voices
        voices = client.list_voices()

        # Generate speech
        result = client.generate_speech(
            text="Hello, this is a test.",
            voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel voice
            model_id="eleven_multilingual_v2"
        )

        # Save to S3
        client.generate_speech_and_save(
            text="Hello world!",
            voice_id="21m00Tcm4TlvDq8ikWAM",
            episode_id=uuid,
            storage_client=storage
        )
        ```
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    # Available models
    MODELS = {
        "eleven_multilingual_v2": "Multilingual v2 - Best quality, 29 languages",
        "eleven_multilingual_v1": "Multilingual v1 - Original multilingual",
        "eleven_monolingual_v1": "Monolingual v1 - English only, fastest",
        "eleven_turbo_v2": "Turbo v2 - Low latency, English optimized",
        "eleven_turbo_v2_5": "Turbo v2.5 - Newest turbo model",
    }

    # Default voice IDs for common use cases
    DEFAULT_VOICES = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",  # Female, American, calm
        "drew": "29vD33N1CtxCmqQRPOHJ",  # Male, American, conversational
        "clyde": "2EiwWnXFnvU5JabPnv8n",  # Male, American, war veteran
        "domi": "AZnzlk1XvdvUeBnXmlld",  # Female, American, strong
        "dave": "CYw3kZ02Hs0563khs1Fj",  # Male, British, conversational
        "fin": "D38z5RcWu1voky8WS1ja",  # Male, Irish, conversational
        "bella": "EXAVITQu4vr4xnSDxMaL",  # Female, American, soft
        "antoni": "ErXwobaYiN019PkySvjV",  # Male, American, well-rounded
        "josh": "TxGEqnHWrfWFTfGW9XjX",  # Male, American, deep
        "arnold": "VR6AewLTigWG4xSOukaG",  # Male, American, crisp
        "adam": "pNInz6obpgDQGcFmaJgB",  # Male, American, deep
        "sam": "yoZ06aMxZJJ28mfd3POQ",  # Male, American, raspy
    }

    def __init__(
        self,
        api_key: str | None = None,
        settings: Settings | None = None,
        pricing_tier: str = DEFAULT_PRICING_TIER,
        max_retries: int = 3,
        timeout: float = 120.0,  # Longer timeout for audio generation
    ) -> None:
        """
        Initialize the ElevenLabs client.

        Args:
            api_key: ElevenLabs API key (uses settings if not provided)
            settings: Application settings instance
            pricing_tier: Pricing tier for cost estimation
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self._settings_obj = settings or get_settings()
        api_key = api_key or self._settings_obj.elevenlabs_api_key

        if not api_key:
            raise ValidationError(
                message="ElevenLabs API key is required",
                field="elevenlabs_api_key",
            )

        super().__init__(
            base_url=self.BASE_URL,
            api_key=api_key,
            settings=self._settings_obj,
            max_retries=max_retries,
            timeout=timeout,
        )

        self._pricing_tier = pricing_tier
        self._total_usage = UsageMetrics(
            provider="elevenlabs",
            unit_type="characters",
        )

    @property
    def service_name(self) -> str:
        """Return service name for logging."""
        return "ElevenLabs"

    def _get_headers(self) -> dict[str, str]:
        """Return default headers for API requests."""
        return {
            "xi-api-key": self._api_key or "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _estimate_duration_ms(self, character_count: int) -> int:
        """
        Estimate audio duration from character count.

        Average speaking rate is ~150 words per minute or ~750 chars/min.
        This gives roughly 80ms per character on average.

        Args:
            character_count: Number of characters in text

        Returns:
            Estimated duration in milliseconds
        """
        # Average: ~80ms per character (150 WPM, 5 chars/word)
        return int(character_count * 80)

    def _calculate_cost(self, character_count: int) -> Decimal:
        """
        Calculate cost for character count based on pricing tier.

        Args:
            character_count: Number of characters processed

        Returns:
            Estimated cost in USD
        """
        price_per_1k = ELEVENLABS_PRICING.get(
            self._pricing_tier, ELEVENLABS_PRICING["creator"]
        )
        return (Decimal(str(character_count)) / Decimal("1000")) * price_per_1k

    def list_voices(
        self,
        show_legacy: bool = False,
    ) -> list[Voice]:
        """
        Get list of available voices.

        Args:
            show_legacy: Include legacy voices in the list

        Returns:
            List of Voice objects

        Raises:
            ExternalServiceError: If API request fails
        """
        response = self._get("voices")
        data = response.json()

        voices = []
        for voice_data in data.get("voices", []):
            try:
                voice = Voice.from_api_response(voice_data)
                if show_legacy or voice.category != "legacy":
                    voices.append(voice)
            except Exception as e:
                logger.warning(
                    "Failed to parse voice data",
                    extra={"error": str(e), "voice_data": voice_data},
                )

        logger.info(
            "Listed ElevenLabs voices",
            extra={"voice_count": len(voices)},
        )

        return voices

    def get_voice(self, voice_id: str) -> Voice:
        """
        Get details for a specific voice.

        Args:
            voice_id: Voice identifier

        Returns:
            Voice object with settings

        Raises:
            ExternalServiceError: If voice not found or API fails
        """
        response = self._get(f"voices/{voice_id}")
        data = response.json()

        return Voice.from_api_response(data)

    def get_voice_settings(self, voice_id: str) -> VoiceSettings:
        """
        Get default settings for a voice.

        Args:
            voice_id: Voice identifier

        Returns:
            VoiceSettings for the voice

        Raises:
            ExternalServiceError: If voice not found or API fails
        """
        response = self._get(f"voices/{voice_id}/settings")
        data = response.json()

        return VoiceSettings(
            stability=data.get("stability", 0.5),
            similarity_boost=data.get("similarity_boost", 0.75),
            style=data.get("style", 0.0),
            use_speaker_boost=data.get("use_speaker_boost", True),
        )

    def get_user_subscription_info(self) -> dict[str, Any]:
        """
        Get current user subscription and usage information.

        Returns:
            Dictionary with subscription details
        """
        response = self._get("user/subscription")
        return response.json()

    def generate_speech(
        self,
        text: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        voice_settings: VoiceSettings | None = None,
        output_format: str = "mp3_44100_128",
        optimize_streaming_latency: int = 0,
    ) -> SpeechResult:
        """
        Generate speech from text.

        Args:
            text: Text to convert to speech
            voice_id: Voice identifier
            model_id: Model to use for generation
            voice_settings: Voice settings (uses defaults if not provided)
            output_format: Output audio format
                - mp3_44100_128: MP3 at 44.1kHz, 128kbps (default)
                - mp3_44100_192: MP3 at 44.1kHz, 192kbps
                - pcm_16000: PCM at 16kHz, 16-bit
                - pcm_22050: PCM at 22.05kHz, 16-bit
                - pcm_24000: PCM at 24kHz, 16-bit
                - pcm_44100: PCM at 44.1kHz, 16-bit
            optimize_streaming_latency: Latency optimization (0-4)
                - 0: No optimization (best quality)
                - 4: Max optimization (lowest latency)

        Returns:
            SpeechResult with audio data and metadata

        Raises:
            ValidationError: If text is empty
            ExternalServiceError: If generation fails
        """
        if not text or not text.strip():
            raise ValidationError(
                message="Text cannot be empty",
                field="text",
            )

        # Use default settings if not provided
        if voice_settings is None:
            voice_settings = VoiceSettings()

        # Build request payload
        payload: dict[str, Any] = {
            "text": text,
            "model_id": model_id,
            "voice_settings": voice_settings.to_api_format(),
        }

        # Add optional parameters
        if optimize_streaming_latency > 0:
            payload["optimize_streaming_latency"] = optimize_streaming_latency

        # Request audio with Accept header for audio response
        headers = self._get_headers()
        headers["Accept"] = "audio/mpeg"

        response = self._request(
            "POST",
            f"text-to-speech/{voice_id}",
            json_data=payload,
            headers=headers,
            params={"output_format": output_format},
        )

        # Get audio data
        audio_data = response.content
        character_count = len(text)

        # Calculate metrics
        duration_ms = self._estimate_duration_ms(character_count)
        cost = self._calculate_cost(character_count)

        # Update usage tracking
        usage = UsageMetrics(
            provider="elevenlabs",
            units_used=character_count,
            unit_type="characters",
            estimated_cost_usd=cost,
            request_count=1,
        )
        self._total_usage.add_units(character_count)
        self._total_usage.estimated_cost_usd += cost

        # Determine content type from output format
        content_type = "audio/mpeg" if output_format.startswith("mp3") else "audio/wav"

        logger.info(
            "Generated speech with ElevenLabs",
            extra={
                "voice_id": voice_id,
                "model_id": model_id,
                "character_count": character_count,
                "audio_size_bytes": len(audio_data),
                "estimated_duration_ms": duration_ms,
                "estimated_cost_usd": float(cost),
            },
        )

        return SpeechResult(
            audio_data=audio_data,
            content_type=content_type,
            character_count=character_count,
            duration_ms=duration_ms,
            voice_id=voice_id,
            model_id=model_id,
            usage=usage,
        )

    def generate_speech_and_save(
        self,
        text: str,
        voice_id: str,
        episode_id: UUID,
        storage_client: StorageClient,
        model_id: str = "eleven_multilingual_v2",
        voice_settings: VoiceSettings | None = None,
        version: int = 1,
    ) -> SpeechResult:
        """
        Generate speech and save to S3/MinIO.

        Convenience method that generates speech and uploads to storage
        in a single operation.

        Args:
            text: Text to convert to speech
            voice_id: Voice identifier
            episode_id: Episode UUID for storage path
            storage_client: Storage client instance
            model_id: Model to use for generation
            voice_settings: Voice settings
            version: Asset version number

        Returns:
            SpeechResult with storage_result populated

        Raises:
            ValidationError: If text is empty
            ExternalServiceError: If generation or upload fails
        """
        # Generate the speech
        result = self.generate_speech(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )

        # Upload to S3
        storage_result = storage_client.upload_episode_asset(
            data=result.audio_data,
            episode_id=episode_id,
            asset_type="audio",
            file_extension="mp3",
            content_type=result.content_type,
            version=version,
        )

        result.storage_result = storage_result

        logger.info(
            "Generated and saved speech to S3",
            extra={
                "episode_id": str(episode_id),
                "voice_id": voice_id,
                "storage_uri": storage_result.uri,
            },
        )

        return result

    def generate_speech_stream(
        self,
        text: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        voice_settings: VoiceSettings | None = None,
    ):
        """
        Generate speech with streaming response.

        Yields audio chunks as they are generated. Useful for real-time
        playback or progressive download.

        Args:
            text: Text to convert to speech
            voice_id: Voice identifier
            model_id: Model to use
            voice_settings: Voice settings

        Yields:
            Audio data chunks (bytes)
        """
        if not text or not text.strip():
            raise ValidationError(
                message="Text cannot be empty",
                field="text",
            )

        if voice_settings is None:
            voice_settings = VoiceSettings()

        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": voice_settings.to_api_format(),
        }

        headers = self._get_headers()
        headers["Accept"] = "audio/mpeg"

        # Use streaming request
        with self._client.stream(
            "POST",
            f"{self._base_url}/text-to-speech/{voice_id}/stream",
            json=payload,
            headers=headers,
        ) as response:
            for chunk in response.iter_bytes():
                yield chunk

        # Update usage tracking
        character_count = len(text)
        self._total_usage.add_units(character_count)
        self._total_usage.estimated_cost_usd += self._calculate_cost(character_count)

    def to_media_result(self, speech_result: SpeechResult) -> MediaResult:
        """
        Convert SpeechResult to MediaResult for unified handling.

        Args:
            speech_result: SpeechResult from generate_speech

        Returns:
            MediaResult instance
        """
        return MediaResult(
            data=speech_result.audio_data,
            content_type=speech_result.content_type,
            duration_ms=speech_result.duration_ms,
            file_size_bytes=speech_result.file_size_bytes,
            metadata={
                "voice_id": speech_result.voice_id,
                "model_id": speech_result.model_id,
                "character_count": speech_result.character_count,
            },
            usage=speech_result.usage,
        )


def get_elevenlabs_client(settings: Settings | None = None) -> ElevenLabsClient:
    """
    Factory function to create an ElevenLabs client.

    Can be used as a FastAPI dependency.

    Args:
        settings: Optional settings override

    Returns:
        Configured ElevenLabsClient instance
    """
    return ElevenLabsClient(settings=settings)
