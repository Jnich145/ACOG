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
from sqlalchemy.orm.attributes import flag_modified

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
    ScriptRevisionRequest,
    ScriptRevisionResponse,
    ScriptAcceptResponse,
    ScriptVersionInfo,
    ScriptRestoreRequest,
    ScriptRestoreResponse,
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


@router.post(
    "/{episode_id}/script/revise",
    response_model=ApiResponse[ScriptRevisionResponse],
    status_code=status.HTTP_200_OK,
    summary="Revise Script",
    description="Generate a revised version of the episode script based on instructions.",
)
async def revise_script(
    episode_id: UUID,
    request: ScriptRevisionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[ScriptRevisionResponse]:
    """
    Generate a script revision based on instructions.

    This endpoint generates a proposed revision but does not automatically
    accept it. Use the accept endpoint to apply the revision.

    Args:
        episode_id: Episode unique identifier
        request: Revision instructions
        db: Database session

    Returns:
        Proposed revision with original script for comparison

    Raises:
        NotFoundError: If episode not found
        ValidationError: If episode has no script
    """
    from acog.core.config import get_settings
    from acog.integrations.openai_client import get_openai_client

    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )

    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    if not episode.script:
        raise ValidationError(
            message="Episode has no script to revise",
            field="script",
        )

    # Get channel for persona context
    channel = (
        db.query(Channel)
        .filter(Channel.id == episode.channel_id, Channel.deleted_at.is_(None))
        .first()
    )

    # Build revision prompt
    settings = get_settings()
    openai_client = get_openai_client(settings)

    persona_context = ""
    if channel and channel.persona:
        persona_context = f"""
Channel Persona:
- Name: {channel.persona.get('name', 'Content Creator')}
- Voice: {channel.persona.get('voice', 'Professional')}
- Values: {', '.join(channel.persona.get('values', []))}
"""

    system_prompt = f"""You are a professional video script editor. Your task is to revise scripts while maintaining:
1. The same production markers ([AVATAR:], [VO:], [BROLL:], [PAUSE:])
2. The original structure and flow
3. The channel's voice and tone

{persona_context}

Apply the requested changes while preserving what works in the original script.
Return ONLY the revised script text, nothing else."""

    user_prompt = f"""Please revise this script according to the following instructions:

## Revision Instructions
{request.instructions}

## Current Script
{episode.script}

Return the complete revised script with all production markers intact."""

    # Generate revision using OpenAI
    result = openai_client.complete(
        messages=[{"role": "user", "content": user_prompt}],
        model=settings.openai_model_scripting,
        system_message=system_prompt,
        temperature=0.7,
        max_tokens=8000,
    )

    proposed_revision = result.content.strip()

    # Store proposed revision in script_metadata for later acceptance
    if not episode.script_metadata:
        episode.script_metadata = {}

    episode.script_metadata["proposed_revision"] = proposed_revision
    episode.script_metadata["revision_instructions"] = request.instructions
    episode.script_metadata["revision_model"] = settings.openai_model_scripting
    episode.script_metadata["revision_pending"] = True

    # Flag the JSONB column as modified so SQLAlchemy persists the changes
    flag_modified(episode, "script_metadata")
    db.commit()

    return ApiResponse(
        data=ScriptRevisionResponse(
            proposed_revision=proposed_revision,
            original_script=episode.script,
            revision_instructions=request.instructions,
            model_used=settings.openai_model_scripting,
        )
    )


@router.post(
    "/{episode_id}/script/accept",
    response_model=ApiResponse[ScriptAcceptResponse],
    status_code=status.HTTP_200_OK,
    summary="Accept Script Revision",
    description="Accept the proposed script revision and update the episode.",
)
async def accept_script_revision(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[ScriptAcceptResponse]:
    """
    Accept a pending script revision.

    This applies the proposed revision from a previous revise call.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        Confirmation with new version number

    Raises:
        NotFoundError: If episode not found
        ValidationError: If no pending revision
    """
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )

    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    if not episode.script_metadata or not episode.script_metadata.get("revision_pending"):
        raise ValidationError(
            message="No pending revision to accept",
            field="script",
        )

    proposed_revision = episode.script_metadata.get("proposed_revision")
    if not proposed_revision:
        raise ValidationError(
            message="Proposed revision not found",
            field="script",
        )

    # Store current version in history
    current_version = episode.script_metadata.get("version", 1)
    version_history = episode.script_metadata.get("version_history", [])

    version_history.append({
        "version": current_version,
        "script": episode.script,
        "word_count": episode.script_metadata.get("word_count", len(episode.script.split())),
        "estimated_duration_seconds": episode.script_metadata.get("estimated_duration_seconds", 0),
        "created_at": episode.script_metadata.get("generated_at", datetime.now(UTC).isoformat()),
        "model_used": episode.script_metadata.get("model_used", "unknown"),
    })

    # Apply the revision
    new_version = current_version + 1
    word_count = len(proposed_revision.split())
    estimated_duration = int((word_count / 150) * 60)  # 150 WPM

    episode.script = proposed_revision
    episode.script_metadata["version"] = new_version
    episode.script_metadata["word_count"] = word_count
    episode.script_metadata["estimated_duration_seconds"] = estimated_duration
    episode.script_metadata["generated_at"] = datetime.now(UTC).isoformat()
    episode.script_metadata["model_used"] = episode.script_metadata.get("revision_model", "unknown")
    episode.script_metadata["version_history"] = version_history

    # Clear pending revision
    episode.script_metadata.pop("proposed_revision", None)
    episode.script_metadata.pop("revision_instructions", None)
    episode.script_metadata.pop("revision_model", None)
    episode.script_metadata["revision_pending"] = False

    # Flag the JSONB column as modified so SQLAlchemy persists the changes
    flag_modified(episode, "script_metadata")
    db.commit()

    return ApiResponse(
        data=ScriptAcceptResponse(
            version=new_version,
            word_count=word_count,
            message=f"Script revision accepted. Now at version {new_version}.",
        )
    )


@router.get(
    "/{episode_id}/script/versions",
    response_model=ApiResponse[list[ScriptVersionInfo]],
    status_code=status.HTTP_200_OK,
    summary="Get Script Versions",
    description="Get the version history of an episode's script.",
)
async def get_script_versions(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[list[ScriptVersionInfo]]:
    """
    Get script version history.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        List of script version information

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

    versions = []

    # Add current version
    if episode.script and episode.script_metadata:
        versions.append(
            ScriptVersionInfo(
                version=episode.script_metadata.get("version", 1),
                word_count=episode.script_metadata.get("word_count", len(episode.script.split())),
                estimated_duration_seconds=episode.script_metadata.get("estimated_duration_seconds", 0),
                created_at=episode.script_metadata.get("generated_at", episode.updated_at.isoformat()),
                model_used=episode.script_metadata.get("model_used", "unknown"),
            )
        )

    # Add historical versions
    version_history = episode.script_metadata.get("version_history", []) if episode.script_metadata else []
    for v in version_history:
        versions.append(
            ScriptVersionInfo(
                version=v.get("version", 0),
                word_count=v.get("word_count", 0),
                estimated_duration_seconds=v.get("estimated_duration_seconds", 0),
                created_at=v.get("created_at", ""),
                model_used=v.get("model_used", "unknown"),
            )
        )

    # Sort by version descending (newest first)
    versions.sort(key=lambda x: x.version, reverse=True)

    return ApiResponse(data=versions)


@router.post(
    "/{episode_id}/script/restore",
    response_model=ApiResponse[ScriptRestoreResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore Script Version",
    description="Restore a previous version of the script.",
)
async def restore_script_version(
    episode_id: UUID,
    request: ScriptRestoreRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[ScriptRestoreResponse]:
    """
    Restore a previous script version.

    This creates a new version with the content from the specified old version.

    Args:
        episode_id: Episode unique identifier
        request: Version to restore
        db: Database session

    Returns:
        Confirmation with version numbers

    Raises:
        NotFoundError: If episode or version not found
    """
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )

    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    if not episode.script_metadata:
        raise ValidationError(
            message="No script versions available",
            field="script",
        )

    version_history = episode.script_metadata.get("version_history", [])

    # Find the version to restore
    version_to_restore = None
    for v in version_history:
        if v.get("version") == request.version:
            version_to_restore = v
            break

    if not version_to_restore:
        raise NotFoundError(
            resource_type="Script version",
            resource_id=str(request.version),
        )

    # Store current version in history
    current_version = episode.script_metadata.get("version", 1)
    version_history.append({
        "version": current_version,
        "script": episode.script,
        "word_count": episode.script_metadata.get("word_count", len(episode.script.split()) if episode.script else 0),
        "estimated_duration_seconds": episode.script_metadata.get("estimated_duration_seconds", 0),
        "created_at": episode.script_metadata.get("generated_at", datetime.now(UTC).isoformat()),
        "model_used": episode.script_metadata.get("model_used", "unknown"),
    })

    # Restore the old version as a new version
    new_version = current_version + 1
    restored_script = version_to_restore.get("script", "")
    word_count = len(restored_script.split())
    estimated_duration = int((word_count / 150) * 60)

    episode.script = restored_script
    episode.script_metadata["version"] = new_version
    episode.script_metadata["word_count"] = word_count
    episode.script_metadata["estimated_duration_seconds"] = estimated_duration
    episode.script_metadata["generated_at"] = datetime.now(UTC).isoformat()
    episode.script_metadata["model_used"] = f"restored_from_v{request.version}"
    episode.script_metadata["version_history"] = version_history

    # Flag the JSONB column as modified so SQLAlchemy persists the changes
    flag_modified(episode, "script_metadata")
    db.commit()

    return ApiResponse(
        data=ScriptRestoreResponse(
            restored_version=request.version,
            new_version=new_version,
            message=f"Script version {request.version} restored as version {new_version}.",
        )
    )
