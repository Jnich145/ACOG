"""
Episode CRUD endpoints.

Provides endpoints for creating, reading, updating, and deleting episodes.
"""

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from acog.core.database import get_db
from acog.core.dependencies import IdempotencyKey, Pagination
from acog.core.exceptions import ConflictError, NotFoundError, ValidationError
from acog.models.channel import Channel
from acog.models.episode import Episode
from acog.models.enums import EpisodeStatus, IdeaSource, Priority
from acog.schemas.common import ApiResponse, DeleteResponse, PaginationMeta
from acog.schemas.episode import (
    EpisodeCreate,
    EpisodeListResponse,
    EpisodeResponse,
    EpisodeUpdate,
)

router = APIRouter()


def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from episode title."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:200]


@router.post(
    "",
    response_model=ApiResponse[EpisodeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Episode",
    description="Create a new episode for a channel.",
)
async def create_episode(
    episode_data: EpisodeCreate,
    db: Session = Depends(get_db),
    channel_id: UUID = Query(description="Parent channel ID"),
    idempotency_key: IdempotencyKey = None,
) -> ApiResponse[EpisodeResponse]:
    """
    Create a new episode.

    Args:
        episode_data: Episode creation data
        db: Database session
        channel_id: Parent channel identifier
        idempotency_key: Optional idempotency key

    Returns:
        Created episode data

    Raises:
        NotFoundError: If channel not found
        ConflictError: If episode with same title exists in channel
    """
    # Verify channel exists
    channel = (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.deleted_at.is_(None))
        .first()
    )
    if not channel:
        raise NotFoundError(resource_type="Channel", resource_id=str(channel_id))

    # Generate slug from title
    slug = generate_slug(episode_data.title)

    # Check for existing episode with same slug in channel
    existing = (
        db.query(Episode)
        .filter(
            Episode.channel_id == channel_id,
            Episode.slug == slug,
            Episode.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise ConflictError(
            message=f"Episode with slug '{slug}' already exists in this channel",
            resource_type="Episode",
        )

    # Build idea JSONB
    idea = {
        "brief": episode_data.idea_brief,
        "target_length_minutes": episode_data.target_length_minutes,
        "tags": episode_data.tags,
        "notes": episode_data.notes,
        "auto_advance": episode_data.auto_advance,
    }

    # Convert priority enum to integer for database storage
    priority = episode_data.priority.to_int()

    # Create episode
    episode = Episode(
        channel_id=channel_id,
        title=episode_data.title,
        slug=slug,
        status=EpisodeStatus.IDEA,
        idea_source=episode_data.idea_source,
        pulse_event_id=episode_data.pulse_event_id,
        idea=idea,
        priority=priority,
    )

    db.add(episode)
    db.commit()
    db.refresh(episode)

    return ApiResponse(
        data=EpisodeResponse.from_model(episode),
        meta={"request_id": idempotency_key} if idempotency_key else {},
    )


@router.get(
    "",
    response_model=EpisodeListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Episodes",
    description="Get a paginated list of episodes with filtering.",
)
async def list_episodes(
    pagination: Pagination,
    db: Session = Depends(get_db),
    channel_id: UUID | None = Query(default=None, description="Filter by channel"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (comma-separated)",
    ),
    priority: Priority | None = Query(default=None, description="Filter by priority"),
    idea_source: IdeaSource | None = Query(default=None, description="Filter by idea source"),
    search: str | None = Query(default=None, description="Search in title"),
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", description="Sort order: asc or desc"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted episodes"),
) -> EpisodeListResponse:
    """
    List episodes with filtering and pagination.

    Args:
        pagination: Pagination parameters
        db: Database session
        channel_id: Filter by channel
        status_filter: Filter by status (comma-separated)
        priority: Filter by priority
        idea_source: Filter by idea source
        search: Search term for title
        sort_by: Field to sort by
        sort_order: Sort direction
        include_deleted: Whether to include deleted episodes

    Returns:
        Paginated list of episodes
    """
    # Build query
    query = db.query(Episode)

    # Apply soft delete filter
    if not include_deleted:
        query = query.filter(Episode.deleted_at.is_(None))

    # Apply filters
    if channel_id:
        query = query.filter(Episode.channel_id == channel_id)

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

    if priority:
        query = query.filter(Episode.priority == priority.to_int())

    if idea_source:
        query = query.filter(Episode.idea_source == idea_source)

    if search:
        query = query.filter(Episode.title.ilike(f"%{search}%"))

    # Get total count
    total_items = query.count()

    # Apply sorting
    sort_column = getattr(Episode, sort_by, Episode.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    episodes = query.offset(pagination.offset).limit(pagination.limit).all()

    # Build response
    episode_responses = [EpisodeResponse.from_model(e) for e in episodes]
    pagination_meta = PaginationMeta.create(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
    )

    filters_applied: dict[str, Any] = {}
    if channel_id:
        filters_applied["channel_id"] = str(channel_id)
    if status_filter:
        filters_applied["status"] = status_filter.split(",")
    if priority:
        filters_applied["priority"] = priority.value

    return EpisodeListResponse.create(
        episodes=episode_responses,
        pagination=pagination_meta,
        filters_applied=filters_applied if filters_applied else None,
    )


@router.get(
    "/{episode_id}",
    response_model=ApiResponse[EpisodeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Episode",
    description="Get detailed information about a specific episode.",
)
async def get_episode(
    episode_id: UUID,
    db: Session = Depends(get_db),
    include_assets: bool = Query(default=True, description="Include asset list"),
    include_plan: bool = Query(default=True, description="Include full plan"),
    include_script: bool = Query(default=True, description="Include full script"),
) -> ApiResponse[EpisodeResponse]:
    """
    Get an episode by ID.

    Args:
        episode_id: Episode unique identifier
        db: Database session
        include_assets: Whether to include assets
        include_plan: Whether to include plan
        include_script: Whether to include script

    Returns:
        Episode data

    Raises:
        NotFoundError: If episode not found
    """
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )

    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    return ApiResponse(
        data=EpisodeResponse.from_model(
            episode,
            include_plan=include_plan,
            include_script=include_script,
            include_assets=include_assets,
        )
    )


@router.put(
    "/{episode_id}",
    response_model=ApiResponse[EpisodeResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Episode",
    description="Update an existing episode.",
)
async def update_episode(
    episode_id: UUID,
    episode_data: EpisodeUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[EpisodeResponse]:
    """
    Update an episode.

    Args:
        episode_id: Episode unique identifier
        episode_data: Fields to update
        db: Database session

    Returns:
        Updated episode data

    Raises:
        NotFoundError: If episode not found
        ValidationError: If status transition is invalid
    """
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )

    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Update provided fields
    if episode_data.title is not None:
        episode.title = episode_data.title
        episode.slug = generate_slug(episode_data.title)

    if episode_data.idea_brief is not None:
        episode.idea["brief"] = episode_data.idea_brief

    if episode_data.target_length_minutes is not None:
        episode.idea["target_length_minutes"] = episode_data.target_length_minutes

    if episode_data.priority is not None:
        episode.priority = episode_data.priority.to_int()

    if episode_data.tags is not None:
        episode.idea["tags"] = episode_data.tags

    if episode_data.notes is not None:
        episode.idea["notes"] = episode_data.notes

    if episode_data.status is not None:
        # Validate status transition
        if not episode.can_advance_to(episode_data.status):
            raise ValidationError(
                message=f"Cannot transition from {episode.status.value} to {episode_data.status.value}",
                field="status",
            )
        episode.status = episode_data.status

    db.commit()
    db.refresh(episode)

    return ApiResponse(data=EpisodeResponse.from_model(episode))


@router.delete(
    "/{episode_id}",
    response_model=ApiResponse[DeleteResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete Episode",
    description="Soft delete an episode.",
)
async def delete_episode(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResponse]:
    """
    Soft delete an episode.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        Deletion confirmation

    Raises:
        NotFoundError: If episode not found
    """
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )

    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Soft delete
    now = datetime.now(UTC)
    episode.deleted_at = now

    db.commit()

    return ApiResponse(data=DeleteResponse(id=episode.id, deleted_at=now))


@router.post(
    "/{episode_id}/cancel",
    response_model=ApiResponse[EpisodeResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel Episode",
    description="Cancel an in-progress episode.",
)
async def cancel_episode(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[EpisodeResponse]:
    """
    Cancel an episode's pipeline execution.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        Updated episode data

    Raises:
        NotFoundError: If episode not found
        ValidationError: If episode cannot be cancelled
    """
    from acog.models.job import Job
    from acog.models.enums import JobStatus

    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )

    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Check if can be cancelled
    non_cancellable = [EpisodeStatus.PUBLISHED, EpisodeStatus.CANCELLED]
    if episode.status in non_cancellable:
        raise ValidationError(
            message=f"Episode with status '{episode.status.value}' cannot be cancelled",
            field="status",
        )

    # Cancel any active jobs
    db.query(Job).filter(
        Job.episode_id == episode_id,
        Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
    ).update({"status": JobStatus.CANCELLED, "completed_at": datetime.now(UTC)})

    # Update episode status
    episode.status = EpisodeStatus.CANCELLED

    db.commit()
    db.refresh(episode)

    return ApiResponse(data=EpisodeResponse.from_model(episode))


# =============================================================================
# Script Revision Endpoints
# =============================================================================


from pydantic import BaseModel as PydanticBaseModel


class ScriptRevisionRequest(PydanticBaseModel):
    """Request body for script revision."""
    instruction: str


class ScriptAcceptRequest(PydanticBaseModel):
    """Request body for accepting script revision."""
    revised_script: str


@router.post(
    "/{episode_id}/script/revise",
    response_model=ApiResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Request Script Revision",
    description="Request a revision of the episode's script based on user instruction.",
)
async def revise_script(
    episode_id: UUID,
    request: ScriptRevisionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """
    Request an AI-powered revision of the script.

    This generates a revision proposal but does NOT automatically save it.
    The user must call the accept endpoint to apply the changes.

    Args:
        episode_id: Episode unique identifier
        instruction: User's instruction for what to revise
        db: Database session

    Returns:
        Original script, revised script, and changes summary

    Raises:
        NotFoundError: If episode not found
        ValidationError: If episode has no script
    """
    from acog.services.script_revision import get_script_revision_service

    service = get_script_revision_service(db)
    result = service.revise_script(episode_id, request.instruction)

    return ApiResponse(
        data={
            "original_script": result.original_script,
            "revised_script": result.revised_script,
            "changes_summary": result.changes_summary,
            "sections_modified": result.sections_modified,
            "tokens_used": result.usage.total_tokens,
            "cost_usd": float(result.usage.estimated_cost_usd),
        }
    )


@router.post(
    "/{episode_id}/script/accept",
    response_model=ApiResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Accept Script Revision",
    description="Accept a proposed script revision and save it.",
)
async def accept_script_revision(
    episode_id: UUID,
    request: ScriptAcceptRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """
    Accept and save a script revision.

    This saves the current script to version history and applies the new script.

    Args:
        episode_id: Episode unique identifier
        revised_script: The revised script content to save
        db: Database session

    Returns:
        Version info after accepting

    Raises:
        NotFoundError: If episode not found
    """
    from acog.services.script_revision import get_script_revision_service

    service = get_script_revision_service(db)
    result = service.accept_revision(episode_id, request.revised_script)

    return ApiResponse(data=result)


@router.get(
    "/{episode_id}/script/versions",
    response_model=ApiResponse[list[dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="Get Script Versions",
    description="Get version history for an episode's script.",
)
async def get_script_versions(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict[str, Any]]]:
    """
    Get script version history.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        List of script versions

    Raises:
        NotFoundError: If episode not found
    """
    from acog.services.script_revision import get_script_revision_service

    service = get_script_revision_service(db)
    versions = service.get_script_versions(episode_id)

    return ApiResponse(data=versions)


@router.post(
    "/{episode_id}/script/restore",
    response_model=ApiResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Restore Script Version",
    description="Restore a previous version of the script.",
)
async def restore_script_version(
    episode_id: UUID,
    version: int = Query(description="Version number to restore"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """
    Restore a previous script version.

    Args:
        episode_id: Episode unique identifier
        version: Version number to restore
        db: Database session

    Returns:
        Info about the restoration

    Raises:
        NotFoundError: If episode not found
        ValidationError: If version not found
    """
    from acog.services.script_revision import get_script_revision_service

    service = get_script_revision_service(db)
    result = service.restore_version(episode_id, version)

    return ApiResponse(data=result)
