"""
Runway API client for AI video generation.

This module provides integration with Runway's Gen-2/Gen-3 API for:
- Text-to-video generation
- Image-to-video generation
- Async job status polling
- Video download

API Reference: https://docs.runwayml.com/
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


# Runway pricing (approximate, as of early 2025)
# Gen-3 Alpha: ~$0.05 per second of video
RUNWAY_COST_PER_SECOND_USD = Decimal("0.05")


class GenerationStatus(str, Enum):
    """Runway generation status values."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AspectRatio(str, Enum):
    """
    Supported aspect ratios for video generation.

    Note: Runway API accepts both formats:
    - Simple ratio strings: "16:9", "9:16", "1:1"
    - Resolution format: "1280:720", "720:1280", "1024:1024"

    This enum uses the simple format which the API normalizes internally.
    """

    LANDSCAPE = "16:9"  # Also accepts "1280:720"
    PORTRAIT = "9:16"  # Also accepts "720:1280"
    SQUARE = "1:1"  # Also accepts "1024:1024"
    CINEMATIC = "21:9"  # Also accepts "1280:549"


class RunwayModel(str, Enum):
    """Available Runway generation models."""

    GEN4_TURBO = "gen4_turbo"  # Latest Gen-4 fast model
    GEN3A_TURBO = "gen3a_turbo"  # Gen-3 Alpha fast model
    GEN3 = "gen3"  # Standard Gen-3
    GEN2 = "gen2"  # Legacy Gen-2


@dataclass
class GenerationJob:
    """
    Runway generation job.

    Attributes:
        generation_id: Unique generation identifier
        status: Current job status
        progress: Generation progress (0-100)
        video_url: URL to download video (when succeeded)
        thumbnail_url: URL to video thumbnail
        duration_seconds: Video duration in seconds
        created_at: Job creation timestamp
        error_message: Error details if failed
        credits_used: Credits consumed
    """

    generation_id: str
    status: GenerationStatus = GenerationStatus.PENDING
    progress: int = 0
    video_url: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: float | None = None
    created_at: str | None = None
    error_message: str | None = None
    credits_used: int | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "GenerationJob":
        """Create GenerationJob from API response."""
        status = GenerationStatus.PENDING
        status_str = (data.get("status") or "pending").lower()

        status_mapping = {
            "pending": GenerationStatus.PENDING,
            "queued": GenerationStatus.QUEUED,
            "processing": GenerationStatus.PROCESSING,
            "in_progress": GenerationStatus.PROCESSING,
            "running": GenerationStatus.PROCESSING,
            "succeeded": GenerationStatus.SUCCEEDED,
            "completed": GenerationStatus.SUCCEEDED,
            "done": GenerationStatus.SUCCEEDED,
            "failed": GenerationStatus.FAILED,
            "error": GenerationStatus.FAILED,
            "cancelled": GenerationStatus.CANCELLED,
            "canceled": GenerationStatus.CANCELLED,
        }
        status = status_mapping.get(status_str, GenerationStatus.PENDING)

        # Extract video URL from output
        output = data.get("output", [])
        video_url = None
        if isinstance(output, list) and len(output) > 0:
            video_url = output[0] if isinstance(output[0], str) else output[0].get("url")
        elif isinstance(output, str):
            video_url = output

        return cls(
            generation_id=data.get("id") or data.get("generation_id", ""),
            status=status,
            progress=data.get("progress", 0),
            video_url=video_url,
            thumbnail_url=data.get("thumbnail_url"),
            duration_seconds=data.get("duration"),
            created_at=data.get("created_at") or data.get("createdAt"),
            error_message=data.get("error") or data.get("failure_reason"),
            credits_used=data.get("credits_used"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "generation_id": self.generation_id,
            "status": self.status.value,
            "progress": self.progress,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at,
            "error_message": self.error_message,
            "credits_used": self.credits_used,
        }


class GenerationSettings(BaseModel):
    """
    Video generation settings.

    Attributes:
        duration: Target video duration in seconds (4 or 10)
        aspect_ratio: Video aspect ratio
        watermark: Include Runway watermark
        seed: Random seed for reproducibility
        motion_amount: Amount of motion (1-10)
        style_prompt: Additional style guidance
    """

    duration: int = Field(default=4, ge=4, le=10)
    aspect_ratio: AspectRatio = Field(default=AspectRatio.LANDSCAPE)
    watermark: bool = Field(default=False)
    seed: int | None = Field(default=None)
    motion_amount: int | None = Field(default=None, ge=1, le=10)
    style_prompt: str | None = Field(default=None)


@dataclass
class VideoResult:
    """
    Result container for video generation.

    Attributes:
        video_data: Video content as bytes
        content_type: Video MIME type
        duration_ms: Video duration in milliseconds
        generation_id: Runway generation ID
        thumbnail_url: URL to thumbnail
        prompt: Original prompt used
        usage: Usage metrics
        storage_result: S3 upload result (if saved)
    """

    video_data: bytes
    content_type: str = "video/mp4"
    duration_ms: int | None = None
    generation_id: str = ""
    thumbnail_url: str | None = None
    prompt: str = ""
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


class RunwayClient(SyncBaseHTTPClient):
    """
    Runway API client for AI video generation.

    Provides B-roll video generation with:
    - Text-to-video generation
    - Image-to-video generation
    - Multiple aspect ratios
    - Async job processing
    - Video download and S3 upload

    Example:
        ```python
        client = RunwayClient()

        # Generate video from text
        job = client.generate_video(
            prompt="A beautiful sunset over mountains, cinematic",
            duration=4,
            aspect_ratio=AspectRatio.LANDSCAPE
        )

        # Wait for completion
        result = client.wait_for_generation(job.generation_id)

        # Download the video
        video_result = client.download_video(result.generation_id)
        ```
    """

    BASE_URL = "https://api.runwayml.com/v1"

    def __init__(
        self,
        api_key: str | None = None,
        settings: Settings | None = None,
        model: RunwayModel = RunwayModel.GEN3A_TURBO,
        max_retries: int = 3,
        timeout: float = 60.0,
        poll_interval: float = 10.0,
        max_poll_time: float = 600.0,  # 10 minutes max
    ) -> None:
        """
        Initialize the Runway client.

        Args:
            api_key: Runway API key (uses settings if not provided)
            settings: Application settings instance
            model: Default model to use for generation
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            poll_interval: Interval between status polls (seconds)
            max_poll_time: Maximum time to poll for completion
        """
        self._settings_obj = settings or get_settings()
        api_key = api_key or self._settings_obj.runway_api_key

        if not api_key:
            raise ValidationError(
                message="Runway API key is required",
                field="runway_api_key",
            )

        super().__init__(
            base_url=self.BASE_URL,
            api_key=api_key,
            settings=self._settings_obj,
            max_retries=max_retries,
            timeout=timeout,
        )

        self._model = model
        self._poll_interval = poll_interval
        self._max_poll_time = max_poll_time
        self._total_usage = UsageMetrics(
            provider="runway",
            unit_type="credits",
        )

    @property
    def service_name(self) -> str:
        """Return service name for logging."""
        return "Runway"

    def _get_headers(self) -> dict[str, str]:
        """Return default headers for API requests."""
        return {
            "Authorization": f"Bearer {self._api_key or ''}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Runway-Version": "2024-11-06",  # API version
        }

    def _calculate_cost(self, duration_seconds: float) -> Decimal:
        """Calculate cost based on video duration."""
        return Decimal(str(duration_seconds)) * RUNWAY_COST_PER_SECOND_USD

    def generate_video(
        self,
        prompt: str,
        duration: int = 4,
        aspect_ratio: AspectRatio | str = AspectRatio.LANDSCAPE,
        model: RunwayModel | None = None,
        settings: GenerationSettings | None = None,
    ) -> GenerationJob:
        """
        Generate video from text prompt.

        Submits a text-to-video generation job. Use get_generation_status()
        or wait_for_generation() to check completion.

        Args:
            prompt: Text description of desired video
            duration: Video duration in seconds (4 or 10)
            aspect_ratio: Video aspect ratio
            model: Model to use (overrides default)
            settings: Additional generation settings

        Returns:
            GenerationJob with job ID for status tracking

        Raises:
            ValidationError: If prompt is empty
            ExternalServiceError: If job submission fails
        """
        if not prompt or not prompt.strip():
            raise ValidationError(
                message="Prompt cannot be empty",
                field="prompt",
            )

        if isinstance(aspect_ratio, str):
            aspect_ratio = AspectRatio(aspect_ratio)

        model = model or self._model

        # Build request payload
        payload: dict[str, Any] = {
            "promptText": prompt,
            "model": model.value,
            "duration": duration,
            "ratio": aspect_ratio.value,
        }

        # Add optional settings
        if settings:
            if settings.watermark:
                payload["watermark"] = True
            if settings.seed is not None:
                payload["seed"] = settings.seed

        logger.info(
            "Creating Runway video generation",
            extra={
                "prompt_preview": prompt[:100],
                "duration": duration,
                "aspect_ratio": aspect_ratio.value,
                "model": model.value,
            },
        )

        # Use text_to_video endpoint for text-only prompts
        response = self._post("text_to_video", json_data=payload)
        data = response.json()

        # Extract generation ID
        generation_id = data.get("id", "")
        if not generation_id:
            raise ExternalServiceError(
                service="Runway",
                message="No generation ID returned from Runway API",
                original_error=str(data),
            )

        job = GenerationJob(
            generation_id=generation_id,
            status=GenerationStatus.PENDING,
        )

        logger.info(
            "Runway generation job created",
            extra={"generation_id": generation_id},
        )

        return job

    def generate_video_from_image(
        self,
        image_url: str,
        prompt: str,
        duration: int = 4,
        aspect_ratio: AspectRatio | str = AspectRatio.LANDSCAPE,
        model: RunwayModel | None = None,
        settings: GenerationSettings | None = None,
    ) -> GenerationJob:
        """
        Generate video from image with motion guidance.

        Creates a video that animates the provided image based on the prompt.

        Args:
            image_url: URL to source image
            prompt: Motion/animation description
            duration: Video duration in seconds (4 or 10)
            aspect_ratio: Video aspect ratio
            model: Model to use (overrides default)
            settings: Additional generation settings

        Returns:
            GenerationJob with job ID for status tracking

        Raises:
            ValidationError: If image_url or prompt is empty
            ExternalServiceError: If job submission fails
        """
        if not image_url or not image_url.strip():
            raise ValidationError(
                message="Image URL cannot be empty",
                field="image_url",
            )

        if not prompt or not prompt.strip():
            raise ValidationError(
                message="Prompt cannot be empty",
                field="prompt",
            )

        if isinstance(aspect_ratio, str):
            aspect_ratio = AspectRatio(aspect_ratio)

        model = model or self._model

        # Build request payload
        payload: dict[str, Any] = {
            "promptImage": image_url,
            "promptText": prompt,
            "model": model.value,
            "duration": duration,
            "ratio": aspect_ratio.value,
        }

        # Add optional settings
        if settings:
            if settings.watermark:
                payload["watermark"] = True
            if settings.seed is not None:
                payload["seed"] = settings.seed

        logger.info(
            "Creating Runway image-to-video generation",
            extra={
                "image_url": image_url[:100],
                "prompt_preview": prompt[:100],
                "duration": duration,
                "aspect_ratio": aspect_ratio.value,
                "model": model.value,
            },
        )

        response = self._post("image_to_video", json_data=payload)
        data = response.json()

        generation_id = data.get("id", "")
        if not generation_id:
            raise ExternalServiceError(
                service="Runway",
                message="No generation ID returned from Runway API",
                original_error=str(data),
            )

        job = GenerationJob(
            generation_id=generation_id,
            status=GenerationStatus.PENDING,
        )

        logger.info(
            "Runway image-to-video job created",
            extra={"generation_id": generation_id},
        )

        return job

    def get_generation_status(self, generation_id: str) -> GenerationJob:
        """
        Get status of a generation job.

        Args:
            generation_id: Generation identifier

        Returns:
            GenerationJob with current status

        Raises:
            ExternalServiceError: If status check fails
        """
        response = self._get(f"tasks/{generation_id}")
        data = response.json()

        job = GenerationJob.from_api_response(data)
        job.generation_id = generation_id  # Ensure ID is set

        logger.debug(
            "Runway generation status",
            extra={
                "generation_id": generation_id,
                "status": job.status.value,
                "progress": job.progress,
            },
        )

        return job

    def wait_for_generation(
        self,
        generation_id: str,
        poll_interval: float | None = None,
        max_poll_time: float | None = None,
    ) -> GenerationJob:
        """
        Wait for generation to complete.

        Polls the API until the generation is complete or times out.

        Args:
            generation_id: Generation identifier
            poll_interval: Override default poll interval
            max_poll_time: Override default max poll time

        Returns:
            GenerationJob with final status

        Raises:
            ExternalServiceError: If generation fails or times out
        """
        interval = poll_interval or self._poll_interval
        max_time = max_poll_time or self._max_poll_time
        start_time = time.time()

        logger.info(
            "Waiting for Runway generation completion",
            extra={
                "generation_id": generation_id,
                "max_poll_time": max_time,
            },
        )

        while True:
            job = self.get_generation_status(generation_id)

            if job.status == GenerationStatus.SUCCEEDED:
                logger.info(
                    "Runway generation completed",
                    extra={
                        "generation_id": generation_id,
                        "duration_seconds": job.duration_seconds,
                        "video_url": job.video_url,
                        "credits_used": job.credits_used,
                    },
                )
                return job

            if job.status == GenerationStatus.FAILED:
                raise ExternalServiceError(
                    service="Runway",
                    message=f"Video generation failed: {job.error_message}",
                    original_error=job.error_message,
                )

            if job.status == GenerationStatus.CANCELLED:
                raise ExternalServiceError(
                    service="Runway",
                    message="Video generation was cancelled",
                )

            elapsed = time.time() - start_time
            if elapsed >= max_time:
                raise ExternalServiceError(
                    service="Runway",
                    message=f"Video generation timed out after {elapsed:.0f} seconds",
                )

            logger.debug(
                "Runway generation still processing",
                extra={
                    "generation_id": generation_id,
                    "status": job.status.value,
                    "progress": job.progress,
                    "elapsed_seconds": elapsed,
                },
            )

            time.sleep(interval)

    def download_video(
        self,
        generation_id: str,
        video_url: str | None = None,
        prompt: str = "",
    ) -> VideoResult:
        """
        Download a completed video.

        Args:
            generation_id: Generation identifier
            video_url: Direct video URL (fetches from status if not provided)
            prompt: Original prompt (for metadata)

        Returns:
            VideoResult with video data

        Raises:
            ExternalServiceError: If download fails
        """
        # Get video URL if not provided
        if not video_url:
            job = self.get_generation_status(generation_id)
            if job.status != GenerationStatus.SUCCEEDED:
                raise ExternalServiceError(
                    service="Runway",
                    message=f"Video not ready for download (status: {job.status.value})",
                )
            video_url = job.video_url
            duration_seconds = job.duration_seconds
            thumbnail_url = job.thumbnail_url
            credits_used = job.credits_used
        else:
            duration_seconds = None
            thumbnail_url = None
            credits_used = None

        if not video_url:
            raise ExternalServiceError(
                service="Runway",
                message="No video URL available for download",
            )

        logger.info(
            "Downloading Runway video",
            extra={"generation_id": generation_id, "video_url": video_url},
        )

        # Download the video directly
        with httpx.Client(timeout=300.0) as download_client:
            response = download_client.get(video_url)
            response.raise_for_status()
            video_data = response.content

        # Calculate usage
        duration_ms = int(duration_seconds * 1000) if duration_seconds else None

        if duration_seconds:
            cost = self._calculate_cost(duration_seconds)
        else:
            cost = self._calculate_cost(4)  # Default 4 seconds

        usage = UsageMetrics(
            provider="runway",
            units_used=credits_used or int(duration_seconds or 4),
            unit_type="credits",
            estimated_cost_usd=cost,
            request_count=1,
        )

        self._total_usage.add_units(credits_used or 1)
        self._total_usage.estimated_cost_usd += cost

        logger.info(
            "Downloaded Runway video",
            extra={
                "generation_id": generation_id,
                "size_bytes": len(video_data),
                "duration_seconds": duration_seconds,
                "cost_usd": float(cost),
            },
        )

        return VideoResult(
            video_data=video_data,
            content_type="video/mp4",
            duration_ms=duration_ms,
            generation_id=generation_id,
            thumbnail_url=thumbnail_url,
            prompt=prompt,
            usage=usage,
        )

    def generate_video_and_wait(
        self,
        prompt: str,
        duration: int = 4,
        aspect_ratio: AspectRatio | str = AspectRatio.LANDSCAPE,
        model: RunwayModel | None = None,
        settings: GenerationSettings | None = None,
        download: bool = True,
    ) -> VideoResult | GenerationJob:
        """
        Generate video and wait for completion.

        Convenience method that creates a video, waits for completion,
        and optionally downloads the result.

        Args:
            prompt: Text description of desired video
            duration: Video duration in seconds
            aspect_ratio: Video aspect ratio
            model: Model to use
            settings: Generation settings
            download: Whether to download the completed video

        Returns:
            VideoResult if download=True, GenerationJob otherwise

        Raises:
            ExternalServiceError: If generation or download fails
        """
        # Create the generation job
        job = self.generate_video(
            prompt=prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            model=model,
            settings=settings,
        )

        # Wait for completion
        completed_job = self.wait_for_generation(job.generation_id)

        if download:
            return self.download_video(
                generation_id=completed_job.generation_id,
                video_url=completed_job.video_url,
                prompt=prompt,
            )

        return completed_job

    def generate_video_and_save(
        self,
        prompt: str,
        episode_id: UUID,
        storage_client: StorageClient,
        duration: int = 4,
        aspect_ratio: AspectRatio | str = AspectRatio.LANDSCAPE,
        model: RunwayModel | None = None,
        settings: GenerationSettings | None = None,
        version: int = 1,
        asset_suffix: str = "",
    ) -> VideoResult:
        """
        Generate video, wait for completion, and save to S3.

        Complete workflow for B-roll video generation with storage.

        Args:
            prompt: Text description of desired video
            episode_id: Episode UUID for storage path
            storage_client: Storage client instance
            duration: Video duration in seconds
            aspect_ratio: Video aspect ratio
            model: Model to use
            settings: Generation settings
            version: Asset version number
            asset_suffix: Optional suffix for multiple B-roll clips

        Returns:
            VideoResult with storage_result populated

        Raises:
            ExternalServiceError: If any step fails
        """
        # Generate and download the video
        result = self.generate_video_and_wait(
            prompt=prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            model=model,
            settings=settings,
            download=True,
        )

        # Type check
        if not isinstance(result, VideoResult):
            raise ExternalServiceError(
                service="Runway",
                message="Unexpected result type from video generation",
            )

        # Determine asset type name
        asset_type = f"b_roll{asset_suffix}" if asset_suffix else "b_roll"

        # Upload to S3
        storage_result = storage_client.upload_episode_asset(
            data=result.video_data,
            episode_id=episode_id,
            asset_type=asset_type,
            file_extension="mp4",
            content_type=result.content_type,
            version=version,
        )

        result.storage_result = storage_result

        logger.info(
            "Generated and saved Runway video to S3",
            extra={
                "episode_id": str(episode_id),
                "generation_id": result.generation_id,
                "storage_uri": storage_result.uri,
            },
        )

        return result

    def generate_image_video_and_save(
        self,
        image_url: str,
        prompt: str,
        episode_id: UUID,
        storage_client: StorageClient,
        duration: int = 4,
        aspect_ratio: AspectRatio | str = AspectRatio.LANDSCAPE,
        model: RunwayModel | None = None,
        settings: GenerationSettings | None = None,
        version: int = 1,
        asset_suffix: str = "",
    ) -> VideoResult:
        """
        Generate image-to-video, wait for completion, and save to S3.

        Args:
            image_url: URL to source image
            prompt: Motion/animation description
            episode_id: Episode UUID for storage path
            storage_client: Storage client instance
            duration: Video duration in seconds
            aspect_ratio: Video aspect ratio
            model: Model to use
            settings: Generation settings
            version: Asset version number
            asset_suffix: Optional suffix for multiple B-roll clips

        Returns:
            VideoResult with storage_result populated

        Raises:
            ExternalServiceError: If any step fails
        """
        # Create the generation job
        job = self.generate_video_from_image(
            image_url=image_url,
            prompt=prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            model=model,
            settings=settings,
        )

        # Wait for completion
        completed_job = self.wait_for_generation(job.generation_id)

        # Download the video
        result = self.download_video(
            generation_id=completed_job.generation_id,
            video_url=completed_job.video_url,
            prompt=prompt,
        )

        # Determine asset type name
        asset_type = f"b_roll{asset_suffix}" if asset_suffix else "b_roll"

        # Upload to S3
        storage_result = storage_client.upload_episode_asset(
            data=result.video_data,
            episode_id=episode_id,
            asset_type=asset_type,
            file_extension="mp4",
            content_type=result.content_type,
            version=version,
        )

        result.storage_result = storage_result

        logger.info(
            "Generated and saved Runway image-to-video to S3",
            extra={
                "episode_id": str(episode_id),
                "generation_id": result.generation_id,
                "storage_uri": storage_result.uri,
            },
        )

        return result

    def cancel_generation(self, generation_id: str) -> bool:
        """
        Cancel a pending or processing generation.

        Args:
            generation_id: Generation identifier

        Returns:
            True if cancellation was successful

        Raises:
            ExternalServiceError: If cancellation fails
        """
        try:
            response = self._delete(f"tasks/{generation_id}")

            logger.info(
                "Cancelled Runway generation",
                extra={"generation_id": generation_id},
            )

            return response.status_code in (200, 204)

        except Exception as e:
            logger.warning(
                "Failed to cancel Runway generation",
                extra={
                    "generation_id": generation_id,
                    "error": str(e),
                },
            )
            return False

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
            provider_job_id=video_result.generation_id,
            metadata={
                "generation_id": video_result.generation_id,
                "thumbnail_url": video_result.thumbnail_url,
                "prompt": video_result.prompt,
            },
            usage=video_result.usage,
        )


def get_runway_client(settings: Settings | None = None) -> RunwayClient:
    """
    Factory function to create a Runway client.

    Can be used as a FastAPI dependency.

    Args:
        settings: Optional settings override

    Returns:
        Configured RunwayClient instance
    """
    return RunwayClient(settings=settings)
