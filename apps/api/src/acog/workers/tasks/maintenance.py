"""
Maintenance tasks for ACOG.

This module contains tasks for:
- Cleaning up orphaned jobs (jobs stuck in running/queued state)
- Synchronizing job state with Celery task state
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from celery.result import AsyncResult

from acog.models import Job, JobStatus
from acog.workers.celery_app import celery_app
from acog.workers.utils import get_db_session

logger = logging.getLogger(__name__)


# Maximum age in minutes before a job is considered "orphaned"
DEFAULT_MAX_AGE_MINUTES = 15


def check_celery_task_exists(celery_task_id: str) -> tuple[bool, str | None]:
    """
    Check if a Celery task exists and get its state.

    Args:
        celery_task_id: The Celery task ID to check

    Returns:
        Tuple of (exists, state) where:
        - exists: True if task is known to Celery
        - state: Task state (PENDING, STARTED, SUCCESS, FAILURE, REVOKED, etc.)
    """
    if not celery_task_id:
        return False, None

    try:
        result = AsyncResult(celery_task_id, app=celery_app)
        state = result.state

        # PENDING can mean either:
        # 1. Task is truly pending (in queue)
        # 2. Task ID is unknown (never existed or result expired)
        # We can't reliably distinguish these cases without task_track_started

        # If state is PENDING and we have task_track_started enabled,
        # we can check if the task was ever started
        return True, state
    except Exception as e:
        logger.warning(
            f"Error checking Celery task {celery_task_id}: {e}",
            extra={"celery_task_id": celery_task_id, "error": str(e)},
        )
        return False, None


def is_task_actually_running(job: Job) -> bool:
    """
    Check if a job's Celery task is actually running.

    A task is considered "actually running" if:
    1. It has a celery_task_id AND
    2. That task is in PENDING, STARTED, or RETRY state in Celery

    Args:
        job: The Job record to check

    Returns:
        True if the task appears to be running
    """
    if not job.celery_task_id:
        # No Celery task associated - definitely not running
        return False

    exists, state = check_celery_task_exists(job.celery_task_id)

    if not exists:
        return False

    # These states indicate the task is active
    active_states = {"PENDING", "STARTED", "RETRY", "RECEIVED"}
    return state in active_states


@shared_task(
    bind=True,
    name="acog.workers.tasks.maintenance.cleanup_orphaned_jobs",
    acks_late=True,
)
def cleanup_orphaned_jobs(
    self,
    max_age_minutes: int = DEFAULT_MAX_AGE_MINUTES,
) -> dict[str, Any]:
    """
    Clean up orphaned jobs that are stuck in running/queued state.

    A job is considered orphaned if:
    1. Status is 'queued' or 'running'
    2. Job age exceeds max_age_minutes
    3. The associated Celery task is not actually running

    This task should be run periodically via Celery Beat to ensure
    stuck jobs don't block pipeline execution.

    Args:
        max_age_minutes: Maximum age in minutes before marking as orphaned

    Returns:
        Summary of cleanup operation
    """
    logger.info(
        f"Starting orphaned job cleanup (max_age={max_age_minutes} minutes)",
    )

    threshold = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
    cleaned_jobs: list[dict[str, Any]] = []

    with get_db_session() as db:
        # Find potentially stuck jobs
        stuck_jobs = db.query(Job).filter(
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            Job.created_at < threshold,
        ).all()

        if not stuck_jobs:
            logger.info("No stuck jobs found")
            return {
                "checked_count": 0,
                "cleaned_count": 0,
                "cleaned_jobs": [],
            }

        logger.info(f"Found {len(stuck_jobs)} potentially stuck jobs")

        for job in stuck_jobs:
            # Check if the Celery task is actually running
            if is_task_actually_running(job):
                logger.debug(
                    f"Job {job.id} task is still running, skipping",
                    extra={"job_id": str(job.id), "celery_task_id": job.celery_task_id},
                )
                continue

            # Job is orphaned - mark as failed
            age_minutes = (datetime.now(UTC) - job.created_at).total_seconds() / 60
            error_message = (
                f"Job orphaned: stuck in {job.status.value} state for "
                f"{age_minutes:.1f} minutes. Celery task not found or completed."
            )

            job.status = JobStatus.CANCELLED
            job.error_message = error_message
            job.completed_at = datetime.now(UTC)

            cleaned_jobs.append({
                "job_id": str(job.id),
                "episode_id": str(job.episode_id),
                "stage": job.stage,
                "original_status": job.status.value,
                "age_minutes": round(age_minutes, 1),
            })

            logger.info(
                f"Cleaned up orphaned job {job.id}",
                extra={
                    "job_id": str(job.id),
                    "episode_id": str(job.episode_id),
                    "stage": job.stage,
                    "age_minutes": age_minutes,
                },
            )

        if cleaned_jobs:
            db.commit()

    logger.info(
        f"Orphaned job cleanup complete: {len(cleaned_jobs)} jobs cleaned",
    )

    return {
        "checked_count": len(stuck_jobs),
        "cleaned_count": len(cleaned_jobs),
        "cleaned_jobs": cleaned_jobs,
    }


@shared_task(
    bind=True,
    name="acog.workers.tasks.maintenance.sync_job_states",
)
def sync_job_states(self) -> dict[str, Any]:
    """
    Synchronize database job states with Celery task states.

    This task checks all running/queued jobs and updates their status
    based on the actual Celery task state.

    Returns:
        Summary of sync operation
    """
    logger.info("Starting job state synchronization")

    synced_count = 0

    with get_db_session() as db:
        # Find all jobs in active states
        active_jobs = db.query(Job).filter(
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        ).all()

        for job in active_jobs:
            if not job.celery_task_id:
                continue

            exists, state = check_celery_task_exists(job.celery_task_id)

            if not exists:
                continue

            # Map Celery states to job actions
            if state in {"SUCCESS", "FAILURE", "REVOKED"}:
                if job.status == JobStatus.RUNNING:
                    # Task finished but job wasn't updated - sync it
                    if state == "SUCCESS":
                        # We don't have the result here, just mark sync needed
                        logger.warning(
                            f"Job {job.id} Celery task completed but job still running",
                            extra={"job_id": str(job.id), "celery_state": state},
                        )
                    elif state == "FAILURE":
                        job.status = JobStatus.FAILED
                        job.error_message = "Task failed (detected during sync)"
                        job.completed_at = datetime.now(UTC)
                        synced_count += 1
                    elif state == "REVOKED":
                        job.status = JobStatus.CANCELLED
                        job.error_message = "Task revoked"
                        job.completed_at = datetime.now(UTC)
                        synced_count += 1

        if synced_count > 0:
            db.commit()

    logger.info(f"Job state sync complete: {synced_count} jobs synced")

    return {
        "active_jobs_checked": len(active_jobs),
        "synced_count": synced_count,
    }


__all__ = [
    "cleanup_orphaned_jobs",
    "sync_job_states",
    "check_celery_task_exists",
    "is_task_actually_running",
]
