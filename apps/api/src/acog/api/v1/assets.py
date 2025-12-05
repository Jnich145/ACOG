"""
Asset endpoints.

Provides endpoints for retrieving and managing episode assets.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from acog.core.config import get_settings
from acog.core.database import get_db
from acog.core.dependencies import Pagination
from acog.core.exceptions import NotFoundError
from acog.models.asset import Asset
from acog.models.enums import AssetType
from acog.models.episode import Episode
from acog.schemas.asset import (
    AssetDownloadResponse,
    AssetListResponse,
    AssetResponse,
    AssetUpdate,
)
from acog.schemas.common import ApiResponse, DeleteResponse, PaginationMeta

router = APIRouter()


@router.get(
    "",
    response_model=AssetListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Assets",
    description="Get a paginated list of assets with filtering.",
)
async def list_assets(
    pagination: Pagination,
    db: Session = Depends(get_db),
    episode_id: UUID | None = Query(default=None, description="Filter by episode"),
    asset_type: AssetType | None = Query(
        default=None,
        alias="type",
        description="Filter by asset type",
    ),
    provider: str | None = Query(default=None, description="Filter by provider"),
    is_primary: bool | None = Query(default=None, description="Filter by primary status"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted assets"),
) -> AssetListResponse:
    """
    List assets with filtering and pagination.

    Args:
        pagination: Pagination parameters
        db: Database session
        episode_id: Filter by episode
        asset_type: Filter by asset type
        provider: Filter by provider
        is_primary: Filter by primary status
        include_deleted: Whether to include deleted assets

    Returns:
        Paginated list of assets
    """
    # Build query
    query = db.query(Asset)

    # Apply soft delete filter
    if not include_deleted:
        query = query.filter(Asset.deleted_at.is_(None))

    # Apply filters
    if episode_id:
        query = query.filter(Asset.episode_id == episode_id)
    if asset_type:
        query = query.filter(Asset.type == asset_type)
    if provider:
        query = query.filter(Asset.provider == provider)
    if is_primary is not None:
        query = query.filter(Asset.is_primary == is_primary)

    # Get total count
    total_items = query.count()

    # Apply pagination
    assets = (
        query.order_by(Asset.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
        .all()
    )

    # Build response
    asset_responses = [AssetResponse.from_model(a) for a in assets]
    pagination_meta = PaginationMeta.create(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
    )

    return AssetListResponse.create(
        assets=asset_responses,
        pagination=pagination_meta,
    )


@router.get(
    "/{asset_id}",
    response_model=ApiResponse[AssetResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Asset",
    description="Get detailed information about a specific asset.",
)
async def get_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[AssetResponse]:
    """
    Get an asset by ID.

    Args:
        asset_id: Asset unique identifier
        db: Database session

    Returns:
        Asset data

    Raises:
        NotFoundError: If asset not found
    """
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.deleted_at.is_(None))
        .first()
    )

    if not asset:
        raise NotFoundError(resource_type="Asset", resource_id=str(asset_id))

    return ApiResponse(data=AssetResponse.from_model(asset))


@router.get(
    "/{asset_id}/download",
    response_model=AssetDownloadResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Asset Download URL",
    description="Get a pre-signed download URL for an asset.",
)
async def get_asset_download_url(
    asset_id: UUID,
    db: Session = Depends(get_db),
    expires_in: int = Query(
        default=3600,
        ge=60,
        le=86400,
        description="URL expiration in seconds (1 min to 24 hours)",
    ),
) -> AssetDownloadResponse:
    """
    Get a pre-signed download URL for an asset.

    Args:
        asset_id: Asset unique identifier
        db: Database session
        expires_in: URL expiration in seconds

    Returns:
        Pre-signed download URL and metadata

    Raises:
        NotFoundError: If asset not found
    """
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.deleted_at.is_(None))
        .first()
    )

    if not asset:
        raise NotFoundError(resource_type="Asset", resource_id=str(asset_id))

    # Generate pre-signed URL
    settings = get_settings()
    download_url = asset.uri  # Default to URI

    if asset.storage_bucket and asset.storage_key:
        try:
            import boto3
            from botocore.config import Config

            config = Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            )

            s3_client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
                config=config,
            )

            download_url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": asset.storage_bucket,
                    "Key": asset.storage_key,
                },
                ExpiresIn=expires_in,
            )
        except Exception:
            # Fall back to URI if pre-signing fails
            pass

    return AssetDownloadResponse(
        id=asset.id,
        download_url=download_url,
        expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        filename=asset.name,
        mime_type=asset.mime_type,
        size_bytes=asset.file_size_bytes,
    )


@router.put(
    "/{asset_id}",
    response_model=ApiResponse[AssetResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Asset",
    description="Update asset metadata.",
)
async def update_asset(
    asset_id: UUID,
    asset_data: AssetUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[AssetResponse]:
    """
    Update an asset.

    Args:
        asset_id: Asset unique identifier
        asset_data: Fields to update
        db: Database session

    Returns:
        Updated asset data

    Raises:
        NotFoundError: If asset not found
    """
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.deleted_at.is_(None))
        .first()
    )

    if not asset:
        raise NotFoundError(resource_type="Asset", resource_id=str(asset_id))

    # Update provided fields
    if asset_data.name is not None:
        asset.name = asset_data.name
    if asset_data.metadata is not None:
        asset.metadata = asset_data.metadata
    if asset_data.is_primary is not None:
        # If setting as primary, unset other primaries of same type
        if asset_data.is_primary:
            db.query(Asset).filter(
                Asset.episode_id == asset.episode_id,
                Asset.type == asset.type,
                Asset.id != asset.id,
                Asset.deleted_at.is_(None),
            ).update({"is_primary": False})
        asset.is_primary = asset_data.is_primary

    db.commit()
    db.refresh(asset)

    return ApiResponse(data=AssetResponse.from_model(asset))


@router.delete(
    "/{asset_id}",
    response_model=ApiResponse[DeleteResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete Asset",
    description="Soft delete an asset.",
)
async def delete_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResponse]:
    """
    Soft delete an asset.

    Args:
        asset_id: Asset unique identifier
        db: Database session

    Returns:
        Deletion confirmation

    Raises:
        NotFoundError: If asset not found
    """
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.deleted_at.is_(None))
        .first()
    )

    if not asset:
        raise NotFoundError(resource_type="Asset", resource_id=str(asset_id))

    # Soft delete
    now = datetime.now(UTC)
    asset.deleted_at = now

    db.commit()

    return ApiResponse(data=DeleteResponse(id=asset.id, deleted_at=now))


@router.get(
    "/episode/{episode_id}",
    response_model=AssetListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Episode Assets",
    description="Get all assets for a specific episode.",
)
async def list_episode_assets(
    episode_id: UUID,
    db: Session = Depends(get_db),
    asset_type: AssetType | None = Query(
        default=None,
        alias="type",
        description="Filter by asset type",
    ),
) -> AssetListResponse:
    """
    List all assets for an episode.

    Args:
        episode_id: Episode unique identifier
        db: Database session
        asset_type: Optional asset type filter

    Returns:
        List of assets

    Raises:
        NotFoundError: If episode not found
    """
    # Verify episode exists
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Build query
    query = db.query(Asset).filter(
        Asset.episode_id == episode_id,
        Asset.deleted_at.is_(None),
    )

    if asset_type:
        query = query.filter(Asset.type == asset_type)

    assets = query.order_by(Asset.created_at.desc()).all()

    return AssetListResponse.create(
        assets=[AssetResponse.from_model(a) for a in assets],
    )
