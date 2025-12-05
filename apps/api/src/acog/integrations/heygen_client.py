"""
HeyGen API client for avatar video generation.

This module provides integration with HeyGen's API for:
- Avatar listing and management
- Talking head video generation
- Async job status polling
- Video download

API Reference: https://docs.heygen.com/reference
"""

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

from acog.core.config import Settings, get_settings
from acog.core.exceptions import ExternalServiceError, ValidationError
from acog.integrations.base_client import MediaResult, SyncBaseHTTPClient, UsageMetrics
from acog.integrations.storage_client import StorageClient, UploadResult

logger = logging.getLogger(__name__)


# HeyGen pricing (approximate, as of early 2025)
# Credits per minute of video
HEYGEN_CREDITS_PER_MINUTE = 1
HEYGEN_COST_PER_CREDIT_USD = Decimal("1.00")  # Varies by plan


class VideoStatus(str, Enum):
    """HeyGen video generation status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AvatarType(str, Enum):
    """Types of HeyGen avatars."""

    TALKING_PHOTO = "talking_photo"
    AVATAR = "avatar"
    STUDIO = "studio"


@dataclass
class Avatar:
    """
    HeyGen avatar representation.

    Attributes:
        avatar_id: Unique avatar identifier
        name: Human-readable avatar name
        avatar_type: Type of avatar (talking_photo, avatar, studio)
        preview_image_url: URL to avatar preview image
        preview_video_url: URL to avatar preview video
        gender: Avatar gender if specified
    """

    avatar_id: str
    name: str
    avatar_type: AvatarType = AvatarType.AVATAR
    preview_image_url: str | None = None
    preview_video_url: str | None = None
    gender: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "Avatar":
        """Create Avatar from API response."""
        avatar_type = AvatarType.AVATAR
        if data.get("avatar_type"):
            try:
                avatar_type = AvatarType(data["avatar_type"])
            except ValueError:
                pass

        return cls(
            avatar_id=data.get("avatar_id") or data.get("id", ""),
            name=data.get("avatar_name") or data.get("name", "Unknown"),
            avatar_type=avatar_type,
            preview_image_url=data.get("preview_image_url"),
            preview_video_url=data.get("preview_video_url"),
            gender=data.get("gender"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "avatar_id": self.avatar_id,
            "name": self.name,
            "avatar_type": self.avatar_type.value,
            "preview_image_url": self.preview_image_url,
            "preview_video_url": self.preview_video_url,
            "gender": self.gender,
        }


@dataclass
class HeyGenVoice:
    """
    HeyGen voice for avatar speech.

    Attributes:
        voice_id: Unique voice identifier
        name: Human-readable voice name
        language: Voice language code
        gender: Voice gender
        preview_audio_url: URL to voice preview
    """

    voice_id: str
    name: str
    language: str = "en-US"
    gender: str | None = None
    preview_audio_url: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "HeyGenVoice":
        """Create HeyGenVoice from API response."""
        return cls(
            voice_id=data.get("voice_id") or data.get("id", ""),
            name=data.get("name", "Unknown"),
            language=data.get("language", "en-US"),
            gender=data.get("gender"),
            preview_audio_url=data.get("preview_audio"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "voice_id": self.voice_id,
            "name": self.name,
            "language": self.language,
            "gender": self.gender,
            "preview_audio_url": self.preview_audio_url,
        }


@dataclass
class VideoGenerationJob:
    """
    HeyGen video generation job.

    Attributes:
        video_id: Unique video/job identifier
        status: Current job status
        video_url: URL to download video (when completed)
        thumbnail_url: URL to video thumbnail
        duration_seconds: Video duration in seconds
        created_at: Job creation timestamp
        error_message: Error details if failed
    """

    video_id: str
    status: VideoStatus = VideoStatus.PENDING
    video_url: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: float | None = None
    created_at: str | None = None
    error_message: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "VideoGenerationJob":
        """Create VideoGenerationJob from API response."""
        status = VideoStatus.PENDING
        status_str = data.get("status", "pending").lower()
        if status_str in ("completed", "complete", "done"):
            status = VideoStatus.COMPLETED
        elif status_str in ("processing", "in_progress", "running"):
            status = VideoStatus.PROCESSING
        elif status_str in ("failed", "error"):
            status = VideoStatus.FAILED

        return cls(
            video_id=data.get("video_id") or data.get("id", ""),
            status=status,
            video_url=data.get("video_url"),
            thumbnail_url=data.get("thumbnail_url"),
            duration_seconds=data.get("duration"),
            created_at=data.get("created_at"),
            error_message=data.get("error") or data.get("message"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "video_id": self.video_id,
            "status": self.status.value,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at,
            "error_message": self.error_message,
        }


class VideoSettings(BaseModel):
    """
    Video generation settings.

    Attributes:
        width: Video width in pixels
        height: Video height in pixels
        aspect_ratio: Aspect ratio (16:9, 9:16, 1:1)
        background_color: Background color (hex)
        test: Generate test video (faster, watermarked)
    """

    width: int = Field(default=1920, ge=480, le=4096)
    height: int = Field(default=1080, ge=480, le=4096)
    aspect_ratio: str = Field(default="16:9")
    background_color: str = Field(default="#ffffff")
    test: bool = Field(default=False)


@dataclass
class VideoResult:
    """
    Result container for video generation.

    Attributes:
        video_data: Video content as bytes
        content_type: Video MIME type
        duration_ms: Video duration in milliseconds
        video_id: HeyGen video ID
        thumbnail_url: URL to thumbnail
        usage: Usage metrics
        storage_result: S3 upload result (if saved)
    """

    video_data: bytes
    content_type: str = "video/mp4"
    duration_ms: int | None = None
    video_id: str = ""
    thumbnail_url: str | None = None
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
        """Get video file size in bytes."""
        return len(self.video_data)


class HeyGenClient(SyncBaseHTTPClient):
    """
    HeyGen API client for avatar video generation.

    Provides talking head video generation with:
    - Multiple avatar options
    - Custom voice selection
    - Async job processing
    - Video download and S3 upload

    Example:
        ```python
        client = HeyGenClient()

        # List available avatars
        avatars = client.list_avatars()

        # Create a talking head video
        job = client.create_video(
            script_text="Hello, welcome to our channel!",
            avatar_id="josh_lite3_20230714",
            voice_id="en-US-JennyNeural"
        )

        # Wait for completion
        result = client.wait_for_video(job.video_id)

        # Download the video
        video_result = client.download_video(result.video_id)
        ```
    """

    BASE_URL = "https://api.heygen.com/v2"

    # Common avatar IDs (these may vary)
    DEFAULT_AVATARS = {
        "josh": "josh_lite3_20230714",
        "anna": "Anna_public_3_20240108",
        "susan": "Susan_public_2_20240328",
        "wayne": "Wayne_public_3_20240328",
    }

    def __init__(
        self,
        api_key: str | None = None,
        settings: Settings | None = None,
        max_retries: int = 3,
        timeout: float = 60.0,
        poll_interval: float = 10.0,
        max_poll_time: float = 600.0,  # 10 minutes max
    ) -> None:
        """
        Initialize the HeyGen client.

        Args:
            api_key: HeyGen API key (uses settings if not provided)
            settings: Application settings instance
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            poll_interval: Interval between status polls (seconds)
            max_poll_time: Maximum time to poll for completion
        """
        self._settings_obj = settings or get_settings()
        api_key = api_key or self._settings_obj.heygen_api_key

        if not api_key:
            raise ValidationError(
                message="HeyGen API key is required",
                field="heygen_api_key",
            )

        super().__init__(
            base_url=self.BASE_URL,
            api_key=api_key,
            settings=self._settings_obj,
            max_retries=max_retries,
            timeout=timeout,
        )

        self._poll_interval = poll_interval
        self._max_poll_time = max_poll_time
        self._total_usage = UsageMetrics(
            provider="heygen",
            unit_type="credits",
        )

    @property
    def service_name(self) -> str:
        """Return service name for logging."""
        return "HeyGen"

    def _get_headers(self) -> dict[str, str]:
        """Return default headers for API requests."""
        return {
            "X-Api-Key": self._api_key or "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _calculate_credits(self, duration_seconds: float) -> int:
        """Calculate credits used based on video duration."""
        minutes = duration_seconds / 60.0
        return max(1, int(minutes * HEYGEN_CREDITS_PER_MINUTE))

    def _calculate_cost(self, credits: int) -> Decimal:
        """Calculate cost from credits used."""
        return Decimal(str(credits)) * HEYGEN_COST_PER_CREDIT_USD

    def list_avatars(self) -> list[Avatar]:
        """
        Get list of available avatars.

        Returns:
            List of Avatar objects

        Raises:
            ExternalServiceError: If API request fails
        """
        response = self._get("avatars")
        data = response.json()

        avatars = []
        avatar_list = data.get("data", {}).get("avatars", [])
        if isinstance(avatar_list, list):
            for avatar_data in avatar_list:
                try:
                    avatar = Avatar.from_api_response(avatar_data)
                    avatars.append(avatar)
                except Exception as e:
                    logger.warning(
                        "Failed to parse avatar data",
                        extra={"error": str(e), "avatar_data": avatar_data},
                    )

        logger.info(
            "Listed HeyGen avatars",
            extra={"avatar_count": len(avatars)},
        )

        return avatars

    def list_voices(self) -> list[HeyGenVoice]:
        """
        Get list of available voices.

        Returns:
            List of HeyGenVoice objects

        Raises:
            ExternalServiceError: If API request fails
        """
        response = self._get("voices")
        data = response.json()

        voices = []
        voice_list = data.get("data", {}).get("voices", [])
        if isinstance(voice_list, list):
            for voice_data in voice_list:
                try:
                    voice = HeyGenVoice.from_api_response(voice_data)
                    voices.append(voice)
                except Exception as e:
                    logger.warning(
                        "Failed to parse voice data",
                        extra={"error": str(e), "voice_data": voice_data},
                    )

        logger.info(
            "Listed HeyGen voices",
            extra={"voice_count": len(voices)},
        )

        return voices

    def create_video(
        self,
        script_text: str,
        avatar_id: str,
        voice_id: str | None = None,
        video_settings: VideoSettings | None = None,
        background_url: str | None = None,
        title: str | None = None,
    ) -> VideoGenerationJob:
        """
        Create a talking head video.

        Submits a video generation job to HeyGen. Use get_video_status()
        or wait_for_video() to check completion.

        Args:
            script_text: Text for the avatar to speak
            avatar_id: Avatar identifier
            voice_id: Voice identifier (uses avatar's default if not specified)
            video_settings: Video generation settings
            background_url: URL to custom background image
            title: Video title for organization

        Returns:
            VideoGenerationJob with job ID for status tracking

        Raises:
            ValidationError: If script is empty
            ExternalServiceError: If job submission fails
        """
        if not script_text or not script_text.strip():
            raise ValidationError(
                message="Script text cannot be empty",
                field="script_text",
            )

        if video_settings is None:
            video_settings = VideoSettings()

        # Build the video input
        video_input = {
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal",
            },
            "voice": {
                "type": "text",
                "input_text": script_text,
            },
        }

        # Add voice ID if specified
        if voice_id:
            video_input["voice"]["voice_id"] = voice_id

        # Build request payload
        payload: dict[str, Any] = {
            "video_inputs": [video_input],
            "dimension": {
                "width": video_settings.width,
                "height": video_settings.height,
            },
        }

        # Add optional settings
        if video_settings.test:
            payload["test"] = True

        if background_url:
            payload["background"] = {"type": "image", "url": background_url}

        if title:
            payload["title"] = title

        logger.info(
            "Creating HeyGen video",
            extra={
                "avatar_id": avatar_id,
                "voice_id": voice_id,
                "script_length": len(script_text),
                "test_mode": video_settings.test,
            },
        )

        response = self._post("video/generate", json_data=payload)
        data = response.json()

        # Extract video ID from response
        video_id = data.get("data", {}).get("video_id", "")
        if not video_id:
            raise ExternalServiceError(
                service="HeyGen",
                message="No video ID returned from HeyGen API",
                original_error=str(data),
            )

        job = VideoGenerationJob(
            video_id=video_id,
            status=VideoStatus.PENDING,
        )

        logger.info(
            "HeyGen video job created",
            extra={"video_id": video_id},
        )

        return job

    def get_video_status(self, video_id: str) -> VideoGenerationJob:
        """
        Get status of a video generation job.

        Args:
            video_id: Video/job identifier

        Returns:
            VideoGenerationJob with current status

        Raises:
            ExternalServiceError: If status check fails
        """
        response = self._get(f"video_status.get", params={"video_id": video_id})
        data = response.json()

        job_data = data.get("data", {})
        job = VideoGenerationJob.from_api_response(job_data)
        job.video_id = video_id  # Ensure video_id is set

        logger.debug(
            "HeyGen video status",
            extra={
                "video_id": video_id,
                "status": job.status.value,
            },
        )

        return job

    def wait_for_video(
        self,
        video_id: str,
        poll_interval: float | None = None,
        max_poll_time: float | None = None,
    ) -> VideoGenerationJob:
        """
        Wait for video generation to complete.

        Polls the API until the video is complete or times out.

        Args:
            video_id: Video/job identifier
            poll_interval: Override default poll interval
            max_poll_time: Override default max poll time

        Returns:
            VideoGenerationJob with final status

        Raises:
            ExternalServiceError: If video generation fails or times out
        """
        interval = poll_interval or self._poll_interval
        max_time = max_poll_time or self._max_poll_time
        start_time = time.time()

        logger.info(
            "Waiting for HeyGen video completion",
            extra={
                "video_id": video_id,
                "max_poll_time": max_time,
            },
        )

        while True:
            job = self.get_video_status(video_id)

            if job.status == VideoStatus.COMPLETED:
                logger.info(
                    "HeyGen video completed",
                    extra={
                        "video_id": video_id,
                        "duration_seconds": job.duration_seconds,
                        "video_url": job.video_url,
                    },
                )
                return job

            if job.status == VideoStatus.FAILED:
                raise ExternalServiceError(
                    service="HeyGen",
                    message=f"Video generation failed: {job.error_message}",
                    original_error=job.error_message,
                )

            elapsed = time.time() - start_time
            if elapsed >= max_time:
                raise ExternalServiceError(
                    service="HeyGen",
                    message=f"Video generation timed out after {elapsed:.0f} seconds",
                )

            logger.debug(
                "HeyGen video still processing",
                extra={
                    "video_id": video_id,
                    "status": job.status.value,
                    "elapsed_seconds": elapsed,
                },
            )

            time.sleep(interval)

    def download_video(
        self,
        video_id: str,
        video_url: str | None = None,
    ) -> VideoResult:
        """
        Download a completed video.

        Args:
            video_id: Video identifier
            video_url: Direct video URL (fetches from status if not provided)

        Returns:
            VideoResult with video data

        Raises:
            ExternalServiceError: If download fails
        """
        # Get video URL if not provided
        if not video_url:
            job = self.get_video_status(video_id)
            if job.status != VideoStatus.COMPLETED:
                raise ExternalServiceError(
                    service="HeyGen",
                    message=f"Video not ready for download (status: {job.status.value})",
                )
            video_url = job.video_url
            duration_seconds = job.duration_seconds
            thumbnail_url = job.thumbnail_url
        else:
            duration_seconds = None
            thumbnail_url = None

        if not video_url:
            raise ExternalServiceError(
                service="HeyGen",
                message="No video URL available for download",
            )

        logger.info(
            "Downloading HeyGen video",
            extra={"video_id": video_id, "video_url": video_url},
        )

        # Download the video directly
        with httpx.Client(timeout=300.0) as download_client:
            response = download_client.get(video_url)
            response.raise_for_status()
            video_data = response.content

        # Calculate usage
        duration_ms = int(duration_seconds * 1000) if duration_seconds else None
        if duration_seconds:
            credits = self._calculate_credits(duration_seconds)
            cost = self._calculate_cost(credits)
        else:
            credits = 1
            cost = HEYGEN_COST_PER_CREDIT_USD

        usage = UsageMetrics(
            provider="heygen",
            units_used=credits,
            unit_type="credits",
            estimated_cost_usd=cost,
            request_count=1,
        )

        self._total_usage.add_units(credits)
        self._total_usage.estimated_cost_usd += cost

        logger.info(
            "Downloaded HeyGen video",
            extra={
                "video_id": video_id,
                "size_bytes": len(video_data),
                "duration_seconds": duration_seconds,
                "credits_used": credits,
            },
        )

        return VideoResult(
            video_data=video_data,
            content_type="video/mp4",
            duration_ms=duration_ms,
            video_id=video_id,
            thumbnail_url=thumbnail_url,
            usage=usage,
        )

    def create_video_and_wait(
        self,
        script_text: str,
        avatar_id: str,
        voice_id: str | None = None,
        video_settings: VideoSettings | None = None,
        download: bool = True,
    ) -> VideoResult | VideoGenerationJob:
        """
        Create video and wait for completion.

        Convenience method that creates a video, waits for completion,
        and optionally downloads the result.

        Args:
            script_text: Text for the avatar to speak
            avatar_id: Avatar identifier
            voice_id: Voice identifier
            video_settings: Video generation settings
            download: Whether to download the completed video

        Returns:
            VideoResult if download=True, VideoGenerationJob otherwise

        Raises:
            ExternalServiceError: If generation or download fails
        """
        # Create the video job
        job = self.create_video(
            script_text=script_text,
            avatar_id=avatar_id,
            voice_id=voice_id,
            video_settings=video_settings,
        )

        # Wait for completion
        completed_job = self.wait_for_video(job.video_id)

        if download:
            return self.download_video(
                video_id=completed_job.video_id,
                video_url=completed_job.video_url,
            )

        return completed_job

    def create_video_and_save(
        self,
        script_text: str,
        avatar_id: str,
        episode_id: UUID,
        storage_client: StorageClient,
        voice_id: str | None = None,
        video_settings: VideoSettings | None = None,
        version: int = 1,
    ) -> VideoResult:
        """
        Create video, wait for completion, and save to S3.

        Complete workflow for avatar video generation with storage.

        Args:
            script_text: Text for the avatar to speak
            avatar_id: Avatar identifier
            episode_id: Episode UUID for storage path
            storage_client: Storage client instance
            voice_id: Voice identifier
            video_settings: Video generation settings
            version: Asset version number

        Returns:
            VideoResult with storage_result populated

        Raises:
            ExternalServiceError: If any step fails
        """
        # Generate and download the video
        result = self.create_video_and_wait(
            script_text=script_text,
            avatar_id=avatar_id,
            voice_id=voice_id,
            video_settings=video_settings,
            download=True,
        )

        # Type check - should be VideoResult when download=True
        if not isinstance(result, VideoResult):
            raise ExternalServiceError(
                service="HeyGen",
                message="Unexpected result type from video generation",
            )

        # Upload to S3
        storage_result = storage_client.upload_episode_asset(
            data=result.video_data,
            episode_id=episode_id,
            asset_type="avatar_video",
            file_extension="mp4",
            content_type=result.content_type,
            version=version,
        )

        result.storage_result = storage_result

        logger.info(
            "Generated and saved HeyGen video to S3",
            extra={
                "episode_id": str(episode_id),
                "video_id": result.video_id,
                "storage_uri": storage_result.uri,
            },
        )

        return result

    def to_media_result(self, video_result: VideoResult) -> MediaResult:
        """
        Convert VideoResult to MediaResult for unified handling.

        Args:
            video_result: VideoResult from download_video

        Returns:
            MediaResult instance
        """
        return MediaResult(
            data=video_result.video_data,
            content_type=video_result.content_type,
            duration_ms=video_result.duration_ms,
            file_size_bytes=video_result.file_size_bytes,
            provider_job_id=video_result.video_id,
            metadata={
                "video_id": video_result.video_id,
                "thumbnail_url": video_result.thumbnail_url,
            },
            usage=video_result.usage,
        )


def get_heygen_client(settings: Settings | None = None) -> HeyGenClient:
    """
    Factory function to create a HeyGen client.

    Can be used as a FastAPI dependency.

    Args:
        settings: Optional settings override

    Returns:
        Configured HeyGenClient instance
    """
    return HeyGenClient(settings=settings)
