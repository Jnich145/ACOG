"""
Pydantic schemas for Asset endpoints.

Defines request and response schemas for asset retrieval and management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acog.models.enums import AssetType
from acog.schemas.common import ApiResponse, PaginationMeta


class AssetCreate(BaseModel):
    """
    Schema for creating a new asset.

    Assets are typically created by pipeline workers, not directly via API.

    Attributes:
        episode_id: Parent episode identifier
        type: Asset type
        name: Human-readable name
        uri: Storage URI
        storage_bucket: S3 bucket name
        storage_key: S3 object key
        provider: Service that generated the asset
        provider_job_id: External job ID
        metadata: Provider-specific metadata
        mime_type: MIME type
        file_size_bytes: File size
        duration_ms: Duration in milliseconds
        is_primary: Whether this is the primary asset of its type
    """

    episode_id: UUID = Field(description="Parent episode identifier")
    type: AssetType = Field(description="Asset type")
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Human-readable name",
    )
    uri: str = Field(
        max_length=1000,
        description="Storage URI",
    )
    storage_bucket: str | None = Field(
        default=None,
        max_length=255,
        description="S3 bucket name",
    )
    storage_key: str | None = Field(
        default=None,
        max_length=500,
        description="S3 object key",
    )
    provider: str | None = Field(
        default=None,
        max_length=100,
        description="Service that generated the asset",
    )
    provider_job_id: str | None = Field(
        default=None,
        max_length=255,
        description="External job ID",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific metadata",
    )
    mime_type: str | None = Field(
        default=None,
        max_length=100,
        description="MIME type",
    )
    file_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="File size in bytes",
    )
    duration_ms: int | None = Field(
        default=None,
        ge=0,
        description="Duration in milliseconds",
    )
    is_primary: bool = Field(
        default=False,
        description="Whether this is the primary asset of its type",
    )


class AssetUpdate(BaseModel):
    """
    Schema for updating an existing asset.

    All fields are optional.
    """

    name: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None
    is_primary: bool | None = None


class AssetResponse(BaseModel):
    """
    Schema for asset response data.

    Attributes:
        id: Asset unique identifier
        episode_id: Parent episode identifier
        type: Asset type
        filename: Original or generated filename
        uri: Storage URI
        mime_type: MIME type
        size_bytes: File size in bytes
        duration_seconds: Duration in seconds
        provider: Service that generated the asset
        version: Version number
        metadata: Provider-specific metadata
        checksum: File checksum
        is_primary: Whether this is the primary asset
        created_at: Creation timestamp
        deleted_at: Deletion timestamp
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Asset unique identifier")
    episode_id: UUID = Field(description="Parent episode identifier")
    type: AssetType = Field(description="Asset type")
    filename: str | None = Field(
        default=None,
        description="Original or generated filename",
    )
    uri: str = Field(description="Storage URI")
    storage_bucket: str | None = Field(description="S3 bucket name")
    storage_key: str | None = Field(description="S3 object key")
    mime_type: str | None = Field(description="MIME type")
    size_bytes: int | None = Field(description="File size in bytes")
    duration_seconds: float | None = Field(description="Duration in seconds")
    provider: str | None = Field(description="Service that generated the asset")
    provider_job_id: str | None = Field(description="External job ID")
    version: int = Field(default=1, description="Version number")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific metadata",
    )
    checksum: str | None = Field(
        default=None,
        description="File checksum (MD5 or SHA256)",
    )
    is_primary: bool = Field(description="Whether this is the primary asset")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    deleted_at: datetime | None = Field(description="Deletion timestamp")

    @classmethod
    def from_model(cls, asset: Any) -> "AssetResponse":
        """Create response from asset model."""
        return cls(
            id=asset.id,
            episode_id=asset.episode_id,
            type=asset.type,
            filename=asset.name,
            uri=asset.uri,
            storage_bucket=asset.storage_bucket,
            storage_key=asset.storage_key,
            mime_type=asset.mime_type,
            size_bytes=asset.file_size_bytes,
            duration_seconds=asset.duration_seconds,
            provider=asset.provider,
            provider_job_id=asset.provider_job_id,
            metadata=asset.metadata,
            checksum=asset.metadata.get("checksum"),
            is_primary=asset.is_primary,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            deleted_at=asset.deleted_at,
        )


class AssetDownloadResponse(BaseModel):
    """
    Schema for asset download URL response.

    Provides a pre-signed URL for direct download.

    Attributes:
        id: Asset identifier
        download_url: Pre-signed download URL
        expires_at: URL expiration timestamp
        filename: Suggested filename for download
        mime_type: MIME type
        size_bytes: File size
    """

    id: UUID = Field(description="Asset identifier")
    download_url: str = Field(description="Pre-signed download URL")
    expires_at: datetime = Field(description="URL expiration timestamp")
    filename: str | None = Field(description="Suggested filename")
    mime_type: str | None = Field(description="MIME type")
    size_bytes: int | None = Field(description="File size in bytes")


class AssetListResponse(ApiResponse[list[AssetResponse]]):
    """Response schema for asset list endpoint."""

    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        assets: list[AssetResponse],
        pagination: PaginationMeta | None = None,
        request_id: str | None = None,
    ) -> "AssetListResponse":
        """Create an asset list response."""
        meta: dict[str, Any] = {}
        if pagination:
            meta["pagination"] = pagination.model_dump()
        if request_id:
            meta["request_id"] = request_id
        return cls(data=assets, meta=meta)
