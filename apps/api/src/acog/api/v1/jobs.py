"""
Job endpoints.

Provides endpoints for monitoring and managing pipeline jobs.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from acog.core.database import get_db
from acog.core.dependencies import Pagination
from acog.core.exceptions import NotFoundError, ValidationError
from acog.models.episode import Episode
from acog.models.job import Job
from acog.models.enums import JobStatus
from acog.schemas.common import ApiResponse, PaginationMeta
from acog.schemas.job import JobListResponse, JobResponse

router = APIRouter()


@router.get(
    "",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Jobs",
    description="Get a paginated list of jobs with filtering.",
)
async def list_jobs(
    pagination: Pagination,
    db: Session = Depends(get_db),
    episode_id: UUID | None = Query(default=None, description="Filter by episode"),
    stage: str | None = Query(default=None, description="Filter by stage"),
    status_filter: JobStatus | None = Query(
        default=None,
        alias="status",
        description="Filter by status",
    ),
    active_only: bool = Query(default=False, description="Only show active jobs"),
) -> JobListResponse:
    """
    List jobs with filtering and pagination.

    Args:
        pagination: Pagination parameters
        db: Database session
        episode_id: Filter by episode
        stage: Filter by pipeline stage
        status_filter: Filter by job status
        active_only: Show only queued/running jobs

    Returns:
        Paginated list of jobs
    """
    # Build query
    query = db.query(Job)

    # Apply filters
    if episode_id:
        query = query.filter(Job.episode_id == episode_id)
    if stage:
        query = query.filter(Job.stage == stage)
    if status_filter:
        query = query.filter(Job.status == status_filter)
    if active_only:
        query = query.filter(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))

    # Get total count
    total_items = query.count()

    # Apply pagination
    jobs = (
        query.order_by(Job.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
        .all()
    )

    # Build response
    job_responses = [JobResponse.from_model(j) for j in jobs]
    pagination_meta = PaginationMeta.create(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
    )

    return JobListResponse.create(
        jobs=job_responses,
        pagination=pagination_meta,
    )


@router.get(
    "/{job_id}",
    response_model=ApiResponse[JobResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Job",
    description="Get detailed information about a specific job.",
)
async def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[JobResponse]:
    """
    Get a job by ID.

    Args:
        job_id: Job unique identifier
        db: Database session

    Returns:
        Job data

    Raises:
        NotFoundError: If job not found
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise NotFoundError(resource_type="Job", resource_id=str(job_id))

    return ApiResponse(data=JobResponse.from_model(job))


@router.post(
    "/{job_id}/cancel",
    response_model=ApiResponse[JobResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel Job",
    description="Cancel a queued or running job.",
)
async def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[JobResponse]:
    """
    Cancel a job.

    Args:
        job_id: Job unique identifier
        db: Database session

    Returns:
        Updated job data

    Raises:
        NotFoundError: If job not found
        ValidationError: If job cannot be cancelled
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise NotFoundError(resource_type="Job", resource_id=str(job_id))

    # Check if can be cancelled
    if job.status not in [JobStatus.QUEUED, JobStatus.RUNNING]:
        raise ValidationError(
            message=f"Job with status '{job.status.value}' cannot be cancelled",
            field="status",
        )

    # Cancel the job
    job.cancel()

    # Try to revoke the Celery task if running
    if job.celery_task_id:
        try:
            from celery import current_app
            current_app.control.revoke(job.celery_task_id, terminate=True)
        except Exception:
            pass  # Best effort

    db.commit()
    db.refresh(job)

    return ApiResponse(data=JobResponse.from_model(job))


@router.post(
    "/{job_id}/retry",
    response_model=ApiResponse[JobResponse],
    status_code=status.HTTP_200_OK,
    summary="Retry Job",
    description="Retry a failed job.",
)
async def retry_job(
    job_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[JobResponse]:
    """
    Retry a failed job.

    Args:
        job_id: Job unique identifier
        db: Database session

    Returns:
        Updated job data

    Raises:
        NotFoundError: If job not found
        ValidationError: If job cannot be retried
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise NotFoundError(resource_type="Job", resource_id=str(job_id))

    # Try to retry
    if not job.retry():
        raise ValidationError(
            message=f"Job cannot be retried (status: {job.status.value}, retries: {job.retry_count}/{job.max_retries})",
            field="status",
        )

    db.commit()
    db.refresh(job)

    # Note: In production, this would also re-queue the Celery task
    # That logic would be in a service layer

    return ApiResponse(data=JobResponse.from_model(job))


@router.get(
    "/episode/{episode_id}",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Episode Jobs",
    description="Get all jobs for a specific episode.",
)
async def list_episode_jobs(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> JobListResponse:
    """
    List all jobs for an episode.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        List of jobs

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

    jobs = (
        db.query(Job)
        .filter(Job.episode_id == episode_id)
        .order_by(Job.created_at.desc())
        .all()
    )

    return JobListResponse.create(
        jobs=[JobResponse.from_model(j) for j in jobs],
    )


@router.get(
    "/active",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Active Jobs",
    description="Get all currently active (queued or running) jobs.",
)
async def list_active_jobs(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum jobs to return"),
) -> JobListResponse:
    """
    List all active jobs across all episodes.

    Args:
        db: Database session
        limit: Maximum number of jobs to return

    Returns:
        List of active jobs
    """
    jobs = (
        db.query(Job)
        .filter(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
        .order_by(Job.created_at.asc())
        .limit(limit)
        .all()
    )

    return JobListResponse.create(
        jobs=[JobResponse.from_model(j) for j in jobs],
    )
