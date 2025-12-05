"""
Utility functions for Celery workers.

This module provides helper functions for:
- Creating standalone database sessions for workers
- Updating job status records
- Updating episode pipeline state
- Creating asset records
- Common worker operations

Workers operate outside of the FastAPI request lifecycle, so they need
their own database session management.
"""

import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Generator
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from acog.core.config import get_settings
from acog.models import Asset, AssetType, Episode, EpisodeStatus, Job, JobStatus

logger = logging.getLogger(__name__)

# =============================================================================
# Database Session Management for Workers
# =============================================================================

# Worker-specific engine and session factory
# Separate from the FastAPI sessions to avoid sharing connections
_worker_engine = None
_WorkerSessionLocal = None


def _get_worker_engine():
    """
    Get or create the worker-specific SQLAlchemy engine.

    Uses a separate engine for workers to avoid connection pooling issues
    with the main FastAPI application.
    """
    global _worker_engine
    if _worker_engine is None:
        settings = get_settings()
        _worker_engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=3,  # Smaller pool for workers
            max_overflow=5,
            pool_recycle=1800,  # Recycle connections every 30 minutes
        )
    return _worker_engine


def _get_worker_session_factory():
    """Get or create the worker session factory."""
    global _WorkerSessionLocal
    if _WorkerSessionLocal is None:
        _WorkerSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_get_worker_engine(),
        )
    return _WorkerSessionLocal


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Create a standalone database session for worker tasks.

    This is a context manager that automatically handles session
    lifecycle including commit/rollback and cleanup.

    Yields:
        SQLAlchemy Session object

    Example:
        ```python
        with get_db_session() as db:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            episode.status = EpisodeStatus.PLANNING
            db.commit()
        ```
    """
    SessionLocal = _get_worker_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# =============================================================================
# Job Status Helpers
# =============================================================================


def update_job_status(
    db: Session,
    job_id: UUID | str,
    status: JobStatus,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    cost_usd: float | None = None,
    tokens_used: int | None = None,
) -> Job | None:
    """
    Update a job record with new status and metadata.

    Args:
        db: Database session
        job_id: Job UUID or string
        status: New job status
        result: Optional result data to store
        error_message: Optional error message (for failed status)
        cost_usd: Optional cost in USD
        tokens_used: Optional token count (for LLM jobs)

    Returns:
        Updated Job object or None if not found
    """
    if isinstance(job_id, str):
        job_id = UUID(job_id)

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        logger.warning(f"Job {job_id} not found for status update")
        return None

    # Update status-dependent fields
    if status == JobStatus.RUNNING:
        job.start()
    elif status == JobStatus.COMPLETED:
        job.complete(result=result)
    elif status == JobStatus.FAILED:
        job.fail(error_message or "Unknown error")
    elif status == JobStatus.CANCELLED:
        job.cancel()
    else:
        job.status = status

    # Update cost tracking
    if cost_usd is not None:
        job.cost_usd = Decimal(str(cost_usd))
    if tokens_used is not None:
        job.tokens_used = tokens_used

    logger.info(
        f"Updated job {job_id} status to {status.value}",
        extra={
            "job_id": str(job_id),
            "status": status.value,
            "has_result": result is not None,
            "has_error": error_message is not None,
        },
    )

    return job


def create_job_record(
    db: Session,
    episode_id: UUID | str,
    stage: str,
    celery_task_id: str | None = None,
    input_params: dict[str, Any] | None = None,
) -> Job:
    """
    Create a new job record for a pipeline stage.

    Args:
        db: Database session
        episode_id: Episode UUID or string
        stage: Pipeline stage name
        celery_task_id: Celery task ID for tracking
        input_params: Optional input parameters

    Returns:
        Created Job object
    """
    if isinstance(episode_id, str):
        episode_id = UUID(episode_id)

    job = Job(
        episode_id=episode_id,
        stage=stage,
        status=JobStatus.QUEUED,
        celery_task_id=celery_task_id,
        input_params=input_params or {},
    )
    db.add(job)
    db.flush()  # Get the job ID without committing

    logger.info(
        f"Created job {job.id} for episode {episode_id} stage {stage}",
        extra={
            "job_id": str(job.id),
            "episode_id": str(episode_id),
            "stage": stage,
            "celery_task_id": celery_task_id,
        },
    )

    return job


# =============================================================================
# Episode Pipeline State Helpers
# =============================================================================


def update_episode_pipeline_state(
    db: Session,
    episode_id: UUID | str,
    stage: str,
    status: str,
    error: str | None = None,
    **extra: Any,
) -> Episode | None:
    """
    Update the pipeline state for a specific stage in an episode.

    Args:
        db: Database session
        episode_id: Episode UUID or string
        stage: Pipeline stage name
        status: Stage status (pending, running, completed, failed)
        error: Optional error message
        **extra: Additional fields to store (tokens_used, cost_usd, etc.)

    Returns:
        Updated Episode object or None if not found
    """
    if isinstance(episode_id, str):
        episode_id = UUID(episode_id)

    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.deleted_at.is_(None),
    ).first()

    if not episode:
        logger.warning(f"Episode {episode_id} not found for pipeline state update")
        return None

    # Use the episode's built-in method
    episode.update_pipeline_stage(
        stage=stage,
        status=status,
        error=error,
        **extra,
    )

    logger.debug(
        f"Updated episode {episode_id} pipeline stage {stage} to {status}",
        extra={
            "episode_id": str(episode_id),
            "stage": stage,
            "status": status,
            "has_error": error is not None,
        },
    )

    return episode


def update_episode_status(
    db: Session,
    episode_id: UUID | str,
    status: EpisodeStatus,
    last_error: str | None = None,
) -> Episode | None:
    """
    Update the overall status of an episode.

    Args:
        db: Database session
        episode_id: Episode UUID or string
        status: New episode status
        last_error: Optional error message

    Returns:
        Updated Episode object or None if not found
    """
    if isinstance(episode_id, str):
        episode_id = UUID(episode_id)

    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.deleted_at.is_(None),
    ).first()

    if not episode:
        logger.warning(f"Episode {episode_id} not found for status update")
        return None

    episode.status = status
    if last_error:
        episode.last_error = last_error

    logger.info(
        f"Updated episode {episode_id} status to {status.value}",
        extra={
            "episode_id": str(episode_id),
            "status": status.value,
            "has_error": last_error is not None,
        },
    )

    return episode


# =============================================================================
# Asset Creation Helpers
# =============================================================================


def create_asset_record(
    db: Session,
    episode_id: UUID | str,
    asset_type: AssetType | str,
    uri: str,
    storage_bucket: str | None = None,
    storage_key: str | None = None,
    provider: str | None = None,
    provider_job_id: str | None = None,
    mime_type: str | None = None,
    file_size_bytes: int | None = None,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
    is_primary: bool = False,
    name: str | None = None,
) -> Asset:
    """
    Create an asset record for a generated artifact.

    Args:
        db: Database session
        episode_id: Episode UUID or string
        asset_type: Type of asset (audio, avatar_video, b_roll, etc.)
        uri: Full URI to the asset (s3://bucket/key or https://...)
        storage_bucket: S3 bucket name
        storage_key: S3 object key
        provider: Service that generated the asset
        provider_job_id: External job/task ID
        mime_type: MIME type of the asset
        file_size_bytes: File size in bytes
        duration_ms: Duration in milliseconds (for audio/video)
        metadata: Additional asset metadata
        is_primary: Whether this is the primary asset of this type
        name: Human-readable name for the asset

    Returns:
        Created Asset object
    """
    if isinstance(episode_id, str):
        episode_id = UUID(episode_id)

    if isinstance(asset_type, str):
        asset_type = AssetType(asset_type)

    # If this is marked as primary, unmark any existing primary assets of this type
    if is_primary:
        db.query(Asset).filter(
            Asset.episode_id == episode_id,
            Asset.type == asset_type,
            Asset.is_primary == True,  # noqa: E712
            Asset.deleted_at.is_(None),
        ).update({"is_primary": False})

    asset = Asset(
        episode_id=episode_id,
        type=asset_type,
        name=name,
        uri=uri,
        storage_bucket=storage_bucket,
        storage_key=storage_key,
        provider=provider,
        provider_job_id=provider_job_id,
        asset_meta=metadata or {},
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        duration_ms=duration_ms,
        is_primary=is_primary,
    )
    db.add(asset)
    db.flush()  # Get the asset ID

    logger.info(
        f"Created {asset_type.value} asset {asset.id} for episode {episode_id}",
        extra={
            "asset_id": str(asset.id),
            "episode_id": str(episode_id),
            "asset_type": asset_type.value,
            "uri": uri,
            "provider": provider,
            "is_primary": is_primary,
        },
    )

    return asset


# =============================================================================
# Episode Query Helpers
# =============================================================================


def get_episode_with_channel(
    db: Session,
    episode_id: UUID | str,
) -> Episode | None:
    """
    Fetch an episode with its channel eagerly loaded.

    Args:
        db: Database session
        episode_id: Episode UUID or string

    Returns:
        Episode object with channel relationship loaded, or None
    """
    if isinstance(episode_id, str):
        episode_id = UUID(episode_id)

    from sqlalchemy.orm import joinedload

    return db.query(Episode).options(
        joinedload(Episode.channel)
    ).filter(
        Episode.id == episode_id,
        Episode.deleted_at.is_(None),
    ).first()


# =============================================================================
# Stage Validation Helpers
# =============================================================================


STAGE_PREREQUISITES: dict[str, tuple[list[str], list["EpisodeStatus"]]] = {
    # Planning stage: requires episode to be in IDEA state
    "planning": ([], [EpisodeStatus.IDEA]),
    # Scripting stage: requires planning to be complete, episode in PLANNING state
    "scripting": (["planning"], [EpisodeStatus.PLANNING, EpisodeStatus.SCRIPTING]),
    # Metadata stage: requires scripting to be complete, episode in SCRIPTING or SCRIPT_REVIEW state
    "metadata": (["scripting"], [EpisodeStatus.SCRIPTING, EpisodeStatus.SCRIPT_REVIEW]),
    # Audio stage: requires scripting, episode in SCRIPT_REVIEW or later
    "audio": (["scripting", "metadata"], [EpisodeStatus.SCRIPT_REVIEW, EpisodeStatus.READY, EpisodeStatus.AUDIO]),
    # Avatar stage: requires scripting (audio is parallel, not sequential)
    "avatar": (["scripting", "metadata"], [EpisodeStatus.AUDIO, EpisodeStatus.AVATAR]),
    # B-roll stage: requires planning (audio/avatar can be parallel)
    "broll": (["planning", "metadata"], [EpisodeStatus.AVATAR, EpisodeStatus.BROLL]),
}


def validate_episode_for_stage(
    db: Session,
    episode_id: UUID | str,
    stage: str,
) -> tuple[bool, str | None]:
    """
    Validate that an episode can proceed to a specific pipeline stage.

    Checks:
    1. Episode exists and is not deleted
    2. Episode is in a valid state for this stage
    3. Required prerequisite stages are completed

    Args:
        db: Database session
        episode_id: Episode UUID or string
        stage: Pipeline stage to validate for

    Returns:
        Tuple of (is_valid, error_message)
        - If valid: (True, None)
        - If invalid: (False, "error description")
    """
    if isinstance(episode_id, str):
        episode_id = UUID(episode_id)

    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.deleted_at.is_(None),
    ).first()

    if not episode:
        return False, f"Episode {episode_id} not found or has been deleted"

    # Check if episode is in a terminal state
    if episode.status in [EpisodeStatus.FAILED, EpisodeStatus.CANCELLED]:
        return False, f"Episode is in terminal state: {episode.status.value}"

    # Get prerequisites for this stage
    prereqs = STAGE_PREREQUISITES.get(stage)
    if prereqs:
        required_stages, valid_statuses = prereqs

        # Check prerequisite stages are complete
        for prereq_stage in required_stages:
            if not episode.is_stage_complete(prereq_stage):
                return False, f"Prerequisite stage '{prereq_stage}' not completed"

        # Check episode is in valid status (allow some flexibility)
        if valid_statuses and episode.status not in valid_statuses:
            # If already past this stage, it's ok
            stage_order = [
                EpisodeStatus.IDEA,
                EpisodeStatus.PLANNING,
                EpisodeStatus.SCRIPTING,
                EpisodeStatus.SCRIPT_REVIEW,
                EpisodeStatus.AUDIO,
                EpisodeStatus.AVATAR,
                EpisodeStatus.BROLL,
                EpisodeStatus.ASSEMBLY,
                EpisodeStatus.READY,
            ]
            current_idx = stage_order.index(episode.status) if episode.status in stage_order else -1
            max_valid_idx = max(
                (stage_order.index(s) for s in valid_statuses if s in stage_order),
                default=-1
            )

            if current_idx <= max_valid_idx:
                return False, (
                    f"Episode status '{episode.status.value}' is not valid for stage '{stage}'. "
                    f"Expected one of: {[s.value for s in valid_statuses]}"
                )

    return True, None


# =============================================================================
# Idempotency Helpers
# =============================================================================


def stage_already_completed(
    db: Session,
    episode_id: UUID | str,
    stage: str,
) -> bool:
    """
    Check if a pipeline stage has already been completed for an episode.

    Used to ensure idempotency - if a task is retried after completion,
    it should return early.

    Args:
        db: Database session
        episode_id: Episode UUID or string
        stage: Pipeline stage name

    Returns:
        True if stage is already completed, False otherwise
    """
    if isinstance(episode_id, str):
        episode_id = UUID(episode_id)

    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.deleted_at.is_(None),
    ).first()

    if not episode:
        return False

    return episode.is_stage_complete(stage)


def get_latest_job_for_stage(
    db: Session,
    episode_id: UUID | str,
    stage: str,
) -> Job | None:
    """
    Get the most recent job for a specific episode stage.

    Args:
        db: Database session
        episode_id: Episode UUID or string
        stage: Pipeline stage name

    Returns:
        Most recent Job object or None
    """
    if isinstance(episode_id, str):
        episode_id = UUID(episode_id)

    return db.query(Job).filter(
        Job.episode_id == episode_id,
        Job.stage == stage,
    ).order_by(Job.created_at.desc()).first()


# =============================================================================
# Result Formatting Helpers
# =============================================================================


def format_task_result(
    stage: str,
    episode_id: str,
    job_id: str | None = None,
    success: bool = True,
    asset_ids: list[str] | None = None,
    cost_usd: float = 0.0,
    tokens_used: int | None = None,
    duration_seconds: float | None = None,
    error: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """
    Format a standardized task result dictionary.

    Args:
        stage: Pipeline stage name
        episode_id: Episode UUID string
        job_id: Job UUID string
        success: Whether the task succeeded
        asset_ids: List of created asset UUIDs
        cost_usd: Total cost in USD
        tokens_used: Total tokens used (for LLM tasks)
        duration_seconds: Duration of media asset
        error: Error message if failed
        **extra: Additional result fields

    Returns:
        Formatted result dictionary
    """
    result = {
        "stage": stage,
        "episode_id": episode_id,
        "job_id": job_id,
        "success": success,
        "asset_ids": asset_ids or [],
        "cost_usd": cost_usd,
        "completed_at": datetime.now(UTC).isoformat(),
    }

    if tokens_used is not None:
        result["tokens_used"] = tokens_used

    if duration_seconds is not None:
        result["duration_seconds"] = duration_seconds

    if error:
        result["error"] = error

    result.update(extra)

    return result


__all__ = [
    "get_db_session",
    "update_job_status",
    "create_job_record",
    "update_episode_pipeline_state",
    "update_episode_status",
    "create_asset_record",
    "get_episode_with_channel",
    "validate_episode_for_stage",
    "stage_already_completed",
    "get_latest_job_for_stage",
    "format_task_result",
]
