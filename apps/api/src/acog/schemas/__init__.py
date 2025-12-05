"""
Pydantic schemas for API request/response validation.

This module exports all schemas used for data validation and serialization
in the ACOG API endpoints.
"""

from acog.schemas.asset import (
    AssetCreate,
    AssetDownloadResponse,
    AssetResponse,
    AssetUpdate,
)
from acog.schemas.channel import (
    AvatarProfile,
    ChannelCreate,
    ChannelListResponse,
    ChannelResponse,
    ChannelUpdate,
    Persona,
    StyleGuide,
    VoiceProfile,
)
from acog.schemas.common import (
    ApiResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginationMeta,
    PaginationParams,
)
from acog.schemas.episode import (
    EpisodeCreate,
    EpisodeListResponse,
    EpisodeResponse,
    EpisodeUpdate,
    PipelineState,
    StageStatus,
)
from acog.schemas.job import (
    JobCreate,
    JobListResponse,
    JobProgress,
    JobResponse,
)

__all__ = [
    # Common
    "ApiResponse",
    "ErrorResponse",
    "ErrorDetail",
    "PaginationMeta",
    "PaginationParams",
    "HealthResponse",
    # Channel
    "Persona",
    "StyleGuide",
    "VoiceProfile",
    "AvatarProfile",
    "ChannelCreate",
    "ChannelUpdate",
    "ChannelResponse",
    "ChannelListResponse",
    # Episode
    "PipelineState",
    "StageStatus",
    "EpisodeCreate",
    "EpisodeUpdate",
    "EpisodeResponse",
    "EpisodeListResponse",
    # Asset
    "AssetCreate",
    "AssetUpdate",
    "AssetResponse",
    "AssetDownloadResponse",
    # Job
    "JobCreate",
    "JobResponse",
    "JobListResponse",
    "JobProgress",
]
