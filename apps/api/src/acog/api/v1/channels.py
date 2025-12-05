"""
Channel CRUD endpoints.

Provides endpoints for creating, reading, updating, and deleting channels.
"""

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from acog.core.database import get_db
from acog.core.dependencies import IdempotencyKey, Pagination
from acog.core.exceptions import ConflictError, NotFoundError
from acog.models.channel import Channel
from acog.schemas.channel import (
    ChannelCreate,
    ChannelIdentifier,
    ChannelListResponse,
    ChannelLookupRequest,
    ChannelLookupResponse,
    ChannelResponse,
    ChannelUpdate,
)
from acog.schemas.common import ApiResponse, DeleteResponse, PaginationMeta

router = APIRouter()


def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from channel name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:100]


def channel_to_response(channel: Channel) -> ChannelResponse:
    """Convert Channel model to response schema."""
    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        slug=channel.slug,
        description=channel.description,
        niche=channel.niche,
        persona=channel.persona,
        style_guide=channel.style_guide,
        voice_profile=channel.voice_profile,
        avatar_profile=channel.avatar_profile,
        cadence=channel.cadence,
        platform_config=channel.platform_config,
        youtube_channel_id=channel.youtube_channel_id,
        is_active=channel.is_active,
        episode_count=channel.episode_count,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        deleted_at=channel.deleted_at,
    )


def find_channel_by_identifier(
    db: Session, identifier: ChannelIdentifier
) -> tuple[Channel | None, str | None]:
    """
    Find a channel by one of the provided identifiers.

    Searches in order: slug, youtube_channel_id, youtube_handle (in platform_config).

    Args:
        db: Database session
        identifier: Channel identifier containing one or more lookup values

    Returns:
        Tuple of (Channel if found or None, matched_by identifier name or None)
    """
    # Try slug first (most specific identifier)
    if identifier.slug:
        channel = (
            db.query(Channel)
            .filter(Channel.slug == identifier.slug, Channel.deleted_at.is_(None))
            .first()
        )
        if channel:
            return channel, "slug"

    # Try youtube_channel_id (direct column lookup)
    if identifier.youtube_channel_id:
        channel = (
            db.query(Channel)
            .filter(
                Channel.youtube_channel_id == identifier.youtube_channel_id,
                Channel.deleted_at.is_(None),
            )
            .first()
        )
        if channel:
            return channel, "youtube_channel_id"

    # Try youtube_handle in platform_config JSONB
    if identifier.youtube_handle:
        # Use JSONB containment operator for efficient lookup
        channel = (
            db.query(Channel)
            .filter(
                Channel.platform_config["youtube_handle"].astext == identifier.youtube_handle,
                Channel.deleted_at.is_(None),
            )
            .first()
        )
        if channel:
            return channel, "youtube_handle"

    return None, None


@router.put(
    "/lookup",
    response_model=ChannelLookupResponse,
    responses={
        200: {"description": "Channel found"},
        201: {"description": "Channel created"},
        400: {"description": "No identifier provided"},
        404: {"description": "Channel not found and create_data not provided"},
    },
    summary="Lookup or Create Channel",
    description="Find a channel by identifier (slug, youtube_channel_id, or youtube_handle). "
                "If not found and create_data is provided, creates a new channel.",
)
async def lookup_or_create_channel(
    request: ChannelLookupRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> ChannelLookupResponse:
    """
    Get-or-create channel by identifier.

    Searches for a channel using the provided identifier(s) in this order:
    1. slug
    2. youtube_channel_id
    3. youtube_handle (in platform_config)

    If found, returns the channel with meta.created=false and meta.matched_by.
    If not found and create_data is provided, creates the channel.
    If not found and create_data is None, returns 404.

    Args:
        request: Lookup request with identifier and optional create_data
        response: FastAPI response object for status code
        db: Database session

    Returns:
        Channel lookup response with created flag and matched_by identifier

    Raises:
        HTTPException: 400 if no identifier provided, 404 if not found without create_data
    """
    # Find existing channel
    channel, matched_by = find_channel_by_identifier(db, request.identifier)

    if channel:
        # Channel found - return 200
        response.status_code = status.HTTP_200_OK
        return ChannelLookupResponse.create(
            channel=channel_to_response(channel),
            created=False,
            matched_by=matched_by,
        )

    # Channel not found - check if we should create
    if request.create_data is None:
        raise NotFoundError(
            resource_type="Channel",
            resource_id=f"identifier={request.identifier.model_dump(exclude_none=True)}",
        )

    # Create new channel
    channel_data = request.create_data
    slug = generate_slug(channel_data.name)

    # Check for slug conflict
    existing = (
        db.query(Channel)
        .filter(Channel.slug == slug, Channel.deleted_at.is_(None))
        .first()
    )
    if existing:
        raise ConflictError(
            message=f"Channel with slug '{slug}' already exists",
            resource_type="Channel",
        )

    # Create the channel
    channel = Channel(
        name=channel_data.name,
        slug=slug,
        description=channel_data.description,
        niche=channel_data.niche,
        persona=channel_data.persona.model_dump() if channel_data.persona else {},
        style_guide=channel_data.style_guide.model_dump() if channel_data.style_guide else {},
        voice_profile=channel_data.voice_profile.model_dump() if channel_data.voice_profile else {},
        avatar_profile=channel_data.avatar_profile.model_dump() if channel_data.avatar_profile else {},
        cadence=str(channel_data.cadence.videos_per_week) + "_per_week" if channel_data.cadence else None,
        is_active=channel_data.is_active,
    )

    # Set YouTube channel ID if provided
    if channel_data.youtube_channel_id:
        channel.youtube_channel_id = channel_data.youtube_channel_id

    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Return 201 Created
    response.status_code = status.HTTP_201_CREATED
    return ChannelLookupResponse.create(
        channel=channel_to_response(channel),
        created=True,
        matched_by=None,
    )


@router.get(
    "/by-slug/{slug}",
    response_model=ApiResponse[ChannelResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Channel by Slug",
    description="Get a channel by its URL-friendly slug identifier.",
)
async def get_channel_by_slug(
    slug: str,
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelResponse]:
    """
    Get a channel by slug.

    Args:
        slug: URL-friendly channel identifier
        db: Database session

    Returns:
        Channel data

    Raises:
        NotFoundError: If channel not found
    """
    channel = (
        db.query(Channel)
        .filter(Channel.slug == slug, Channel.deleted_at.is_(None))
        .first()
    )

    if not channel:
        raise NotFoundError(resource_type="Channel", resource_id=slug)

    return ApiResponse(data=channel_to_response(channel))


@router.post(
    "",
    response_model=ApiResponse[ChannelResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Channel",
    description="Create a new content channel with persona and style configuration.",
)
async def create_channel(
    channel_data: ChannelCreate,
    db: Session = Depends(get_db),
    idempotency_key: IdempotencyKey = None,
) -> ApiResponse[ChannelResponse]:
    """
    Create a new channel.

    Args:
        channel_data: Channel creation data
        db: Database session
        idempotency_key: Optional idempotency key

    Returns:
        Created channel data

    Raises:
        ConflictError: If channel with same name already exists
    """
    # Generate slug from name
    slug = generate_slug(channel_data.name)

    # Check for existing channel with same slug
    existing = (
        db.query(Channel)
        .filter(Channel.slug == slug, Channel.deleted_at.is_(None))
        .first()
    )
    if existing:
        raise ConflictError(
            message=f"Channel with slug '{slug}' already exists",
            resource_type="Channel",
        )

    # Create channel
    channel = Channel(
        name=channel_data.name,
        slug=slug,
        description=channel_data.description,
        niche=channel_data.niche,
        persona=channel_data.persona.model_dump() if channel_data.persona else {},
        style_guide=channel_data.style_guide.model_dump() if channel_data.style_guide else {},
        voice_profile=channel_data.voice_profile.model_dump() if channel_data.voice_profile else {},
        avatar_profile=channel_data.avatar_profile.model_dump() if channel_data.avatar_profile else {},
        cadence=str(channel_data.cadence.videos_per_week) + "_per_week" if channel_data.cadence else None,
        is_active=channel_data.is_active,
    )

    # Set YouTube channel ID if provided
    if channel_data.youtube_channel_id:
        channel.youtube_channel_id = channel_data.youtube_channel_id

    db.add(channel)
    db.commit()
    db.refresh(channel)

    return ApiResponse(
        data=channel_to_response(channel),
        meta={"request_id": idempotency_key} if idempotency_key else {},
    )


@router.get(
    "",
    response_model=ChannelListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Channels",
    description="Get a paginated list of all channels.",
)
async def list_channels(
    pagination: Pagination,
    db: Session = Depends(get_db),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    niche: str | None = Query(default=None, description="Filter by niche"),
    search: str | None = Query(default=None, description="Search in name and description"),
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", description="Sort order: asc or desc"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted channels"),
) -> ChannelListResponse:
    """
    List all channels with optional filtering and pagination.

    Args:
        pagination: Pagination parameters
        db: Database session
        is_active: Filter by active status
        niche: Filter by content niche
        search: Search term for name/description
        sort_by: Field to sort by
        sort_order: Sort direction
        include_deleted: Whether to include deleted channels

    Returns:
        Paginated list of channels
    """
    # Build query
    query = db.query(Channel)

    # Apply soft delete filter
    if not include_deleted:
        query = query.filter(Channel.deleted_at.is_(None))

    # Apply filters
    if is_active is not None:
        query = query.filter(Channel.is_active == is_active)
    if niche:
        query = query.filter(Channel.niche == niche)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Channel.name.ilike(search_filter)) | (Channel.description.ilike(search_filter))
        )

    # Get total count
    total_items = query.count()

    # Apply sorting
    sort_column = getattr(Channel, sort_by, Channel.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    channels = query.offset(pagination.offset).limit(pagination.limit).all()

    # Build response
    channel_responses = [channel_to_response(c) for c in channels]
    pagination_meta = PaginationMeta.create(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
    )

    return ChannelListResponse.create(
        channels=channel_responses,
        pagination=pagination_meta,
    )


@router.get(
    "/{channel_id}",
    response_model=ApiResponse[ChannelResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Channel",
    description="Get detailed information about a specific channel.",
)
async def get_channel(
    channel_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelResponse]:
    """
    Get a channel by ID.

    Args:
        channel_id: Channel unique identifier
        db: Database session

    Returns:
        Channel data

    Raises:
        NotFoundError: If channel not found
    """
    channel = (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.deleted_at.is_(None))
        .first()
    )

    if not channel:
        raise NotFoundError(resource_type="Channel", resource_id=str(channel_id))

    return ApiResponse(data=channel_to_response(channel))


@router.put(
    "/{channel_id}",
    response_model=ApiResponse[ChannelResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Channel",
    description="Update an existing channel. Supports partial updates.",
)
async def update_channel(
    channel_id: UUID,
    channel_data: ChannelUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelResponse]:
    """
    Update a channel.

    Args:
        channel_id: Channel unique identifier
        channel_data: Fields to update
        db: Database session

    Returns:
        Updated channel data

    Raises:
        NotFoundError: If channel not found
        ConflictError: If name change would create duplicate
    """
    channel = (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.deleted_at.is_(None))
        .first()
    )

    if not channel:
        raise NotFoundError(resource_type="Channel", resource_id=str(channel_id))

    # Update provided fields
    if channel_data.name is not None:
        new_slug = generate_slug(channel_data.name)
        # Check for conflict
        existing = (
            db.query(Channel)
            .filter(
                Channel.slug == new_slug,
                Channel.id != channel_id,
                Channel.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            raise ConflictError(
                message=f"Channel with slug '{new_slug}' already exists",
                resource_type="Channel",
            )
        channel.name = channel_data.name
        channel.slug = new_slug

    if channel_data.description is not None:
        channel.description = channel_data.description
    if channel_data.niche is not None:
        channel.niche = channel_data.niche
    if channel_data.persona is not None:
        channel.persona = channel_data.persona.model_dump()
    if channel_data.style_guide is not None:
        channel.style_guide = channel_data.style_guide.model_dump()
    if channel_data.voice_profile is not None:
        channel.voice_profile = channel_data.voice_profile.model_dump()
    if channel_data.avatar_profile is not None:
        channel.avatar_profile = channel_data.avatar_profile.model_dump()
    if channel_data.cadence is not None:
        channel.cadence = str(channel_data.cadence.videos_per_week) + "_per_week"
    if channel_data.youtube_channel_id is not None:
        channel.youtube_channel_id = channel_data.youtube_channel_id
    if channel_data.is_active is not None:
        channel.is_active = channel_data.is_active

    db.commit()
    db.refresh(channel)

    return ApiResponse(data=channel_to_response(channel))


@router.delete(
    "/{channel_id}",
    response_model=ApiResponse[DeleteResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete Channel",
    description="Soft delete a channel.",
)
async def delete_channel(
    channel_id: UUID,
    db: Session = Depends(get_db),
    cascade_episodes: bool = Query(
        default=False,
        description="Also soft-delete all episodes in the channel",
    ),
) -> ApiResponse[DeleteResponse]:
    """
    Soft delete a channel.

    Args:
        channel_id: Channel unique identifier
        db: Database session
        cascade_episodes: Whether to also delete episodes

    Returns:
        Deletion confirmation

    Raises:
        NotFoundError: If channel not found
        ConflictError: If channel has in-progress episodes and cascade=False
    """
    from acog.models.episode import Episode
    from acog.models.enums import EpisodeStatus

    channel = (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.deleted_at.is_(None))
        .first()
    )

    if not channel:
        raise NotFoundError(resource_type="Channel", resource_id=str(channel_id))

    # Check for in-progress episodes
    in_progress_statuses = [
        EpisodeStatus.PLANNING,
        EpisodeStatus.SCRIPTING,
        EpisodeStatus.SCRIPT_REVIEW,
        EpisodeStatus.AUDIO,
        EpisodeStatus.AVATAR,
        EpisodeStatus.BROLL,
        EpisodeStatus.ASSEMBLY,
        EpisodeStatus.PUBLISHING,
    ]
    in_progress_count = (
        db.query(func.count(Episode.id))
        .filter(
            Episode.channel_id == channel_id,
            Episode.status.in_(in_progress_statuses),
            Episode.deleted_at.is_(None),
        )
        .scalar()
    )

    if in_progress_count > 0 and not cascade_episodes:
        raise ConflictError(
            message=f"Channel has {in_progress_count} episodes in progress. Use cascade_episodes=true to delete anyway.",
            resource_type="Channel",
        )

    # Soft delete
    now = datetime.now(UTC)
    channel.deleted_at = now
    channel.is_active = False

    episodes_deleted = 0
    if cascade_episodes:
        # Soft delete all episodes
        episodes_deleted = (
            db.query(Episode)
            .filter(Episode.channel_id == channel_id, Episode.deleted_at.is_(None))
            .update({"deleted_at": now})
        )

    db.commit()

    return ApiResponse(
        data=DeleteResponse(id=channel.id, deleted_at=now),
        meta={"episodes_deleted": episodes_deleted},
    )


@router.get(
    "/{channel_id}/episodes",
    status_code=status.HTTP_200_OK,
    summary="List Channel Episodes",
    description="Get all episodes for a specific channel.",
)
async def list_channel_episodes(
    channel_id: UUID,
    pagination: Pagination,
    db: Session = Depends(get_db),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (comma-separated)",
    ),
) -> dict[str, Any]:
    """
    List episodes for a channel.

    This endpoint is a convenience wrapper - the full episode
    list endpoint is at /api/v1/episodes with channel_id filter.

    Args:
        channel_id: Channel unique identifier
        pagination: Pagination parameters
        db: Database session
        status_filter: Status filter

    Returns:
        Paginated list of episodes
    """
    from acog.models.episode import Episode
    from acog.models.enums import EpisodeStatus
    from acog.schemas.episode import EpisodeResponse

    # Verify channel exists
    channel = (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.deleted_at.is_(None))
        .first()
    )
    if not channel:
        raise NotFoundError(resource_type="Channel", resource_id=str(channel_id))

    # Build query
    query = db.query(Episode).filter(
        Episode.channel_id == channel_id,
        Episode.deleted_at.is_(None),
    )

    # Apply status filter
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",")]
        status_enums = []
        for s in statuses:
            try:
                status_enums.append(EpisodeStatus(s))
            except ValueError:
                pass
        if status_enums:
            query = query.filter(Episode.status.in_(status_enums))

    # Get total and paginate
    total_items = query.count()
    episodes = (
        query.order_by(Episode.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
        .all()
    )

    # Build response
    pagination_meta = PaginationMeta.create(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
    )

    return {
        "data": [EpisodeResponse.from_model(e) for e in episodes],
        "meta": {"pagination": pagination_meta.model_dump()},
    }
