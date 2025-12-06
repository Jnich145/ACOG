"""
Pipeline trigger endpoints.

Provides endpoints for triggering and managing pipeline stage execution.
This module integrates with Celery workers to dispatch tasks.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from acog.core.database import get_db
from acog.core.exceptions import NotFoundError, ValidationError
from acog.models.episode import Episode
from acog.models.job import Job
from acog.models.enums import EpisodeStatus, JobStatus, PipelineStage
from acog.schemas.common import ApiResponse
from acog.schemas.job import PipelineTriggerRequest, PipelineTriggerResponse, RunFromStageRequest

# Import Celery tasks for dispatching
from acog.workers.tasks.pipeline import (
    run_planning_stage,
    run_scripting_stage,
    run_metadata_stage,
    run_audio_stage,
    run_avatar_stage,
    run_broll_stage,
)
from acog.workers.tasks.orchestrator import (
    run_stage_1_pipeline,
    run_full_pipeline,
    run_pipeline_from_stage,
    PIPELINE_STAGE_ORDER,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Map pipeline stages to their Celery task functions
STAGE_TASKS = {
    PipelineStage.PLANNING: run_planning_stage,
    PipelineStage.SCRIPTING: run_scripting_stage,
    PipelineStage.METADATA: run_metadata_stage,
    PipelineStage.AUDIO: run_audio_stage,
    PipelineStage.AVATAR: run_avatar_stage,
    PipelineStage.BROLL: run_broll_stage,
}

# Map pipeline stages to required episode status
STAGE_STATUS_MAP: dict[PipelineStage, EpisodeStatus] = {
    PipelineStage.PLANNING: EpisodeStatus.IDEA,
    PipelineStage.SCRIPTING: EpisodeStatus.PLANNING,
    PipelineStage.SCRIPT_REVIEW: EpisodeStatus.SCRIPTING,
    PipelineStage.METADATA: EpisodeStatus.SCRIPT_REVIEW,
    PipelineStage.AUDIO: EpisodeStatus.SCRIPT_REVIEW,
    PipelineStage.AVATAR: EpisodeStatus.AUDIO,
    PipelineStage.BROLL: EpisodeStatus.AUDIO,
    PipelineStage.ASSEMBLY: EpisodeStatus.AVATAR,  # Requires avatar and broll
    PipelineStage.UPLOAD: EpisodeStatus.READY,
}

# Map pipeline stages to resulting episode status
STAGE_RESULT_STATUS_MAP: dict[PipelineStage, EpisodeStatus] = {
    PipelineStage.PLANNING: EpisodeStatus.PLANNING,
    PipelineStage.SCRIPTING: EpisodeStatus.SCRIPTING,
    PipelineStage.SCRIPT_REVIEW: EpisodeStatus.SCRIPT_REVIEW,
    PipelineStage.METADATA: EpisodeStatus.SCRIPT_REVIEW,
    PipelineStage.AUDIO: EpisodeStatus.AUDIO,
    PipelineStage.AVATAR: EpisodeStatus.AVATAR,
    PipelineStage.BROLL: EpisodeStatus.BROLL,
    PipelineStage.ASSEMBLY: EpisodeStatus.ASSEMBLY,
    PipelineStage.UPLOAD: EpisodeStatus.PUBLISHING,
}


@router.post(
    "/episodes/{episode_id}/trigger",
    response_model=ApiResponse[PipelineTriggerResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Pipeline Stage",
    description="Trigger a specific pipeline stage for an episode.",
)
async def trigger_pipeline_stage(
    episode_id: UUID,
    request: PipelineTriggerRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[PipelineTriggerResponse]:
    """
    Trigger a pipeline stage for an episode.

    Creates a job for the specified stage and queues it for processing.

    Args:
        episode_id: Episode unique identifier
        request: Pipeline trigger request
        db: Database session

    Returns:
        Job creation confirmation

    Raises:
        NotFoundError: If episode not found
        ValidationError: If stage cannot be triggered
    """
    # Get episode
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Check if episode is in valid state for this stage
    stage = request.stage

    # Check if there's already an active job for this stage
    existing_job = (
        db.query(Job)
        .filter(
            Job.episode_id == episode_id,
            Job.stage == stage.value,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .first()
    )
    if existing_job and not request.force:
        raise ValidationError(
            message=f"A job for stage '{stage.value}' is already in progress",
            field="stage",
            details={"job_id": str(existing_job.id)},
        )

    # Check if stage has already completed (unless force is set)
    if not request.force:
        stage_status = episode.get_stage_status(stage.value)
        if stage_status == "completed":
            raise ValidationError(
                message=f"Stage '{stage.value}' has already completed. Use force=true to re-run.",
                field="stage",
            )

    # Create job
    job = Job(
        episode_id=episode_id,
        stage=stage.value,
        status=JobStatus.QUEUED,
        input_params=request.params,
    )
    db.add(job)

    # Update episode pipeline state
    episode.update_pipeline_stage(stage.value, "queued")

    # Update episode status if appropriate
    if stage in STAGE_RESULT_STATUS_MAP:
        episode.status = STAGE_RESULT_STATUS_MAP[stage]

    db.commit()
    db.refresh(job)

    # Dispatch the Celery task
    if stage in STAGE_TASKS:
        task_func = STAGE_TASKS[stage]
        celery_task = task_func.delay(str(episode_id), str(job.id))
        job.celery_task_id = celery_task.id
        db.commit()

        logger.info(
            f"Dispatched Celery task for stage '{stage.value}'",
            extra={
                "episode_id": str(episode_id),
                "job_id": str(job.id),
                "celery_task_id": celery_task.id,
                "stage": stage.value,
            },
        )
    else:
        logger.warning(
            f"No Celery task configured for stage '{stage.value}'",
            extra={
                "episode_id": str(episode_id),
                "job_id": str(job.id),
                "stage": stage.value,
            },
        )

    return ApiResponse(
        data=PipelineTriggerResponse(
            job_id=job.id,
            episode_id=episode_id,
            stage=stage.value,
            status=job.status.value,
            message=f"Job created for stage '{stage.value}'",
        )
    )


@router.post(
    "/episodes/{episode_id}/advance",
    response_model=ApiResponse[PipelineTriggerResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Advance Pipeline",
    description="Automatically advance to the next pipeline stage.",
)
async def advance_pipeline(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[PipelineTriggerResponse]:
    """
    Advance an episode to the next pipeline stage.

    Determines the next stage based on current status and triggers it.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        Job creation confirmation

    Raises:
        NotFoundError: If episode not found
        ValidationError: If cannot advance
    """
    # Get episode
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Determine next stage based on current status
    stage_progression = [
        (EpisodeStatus.IDEA, PipelineStage.PLANNING),
        (EpisodeStatus.PLANNING, PipelineStage.SCRIPTING),
        (EpisodeStatus.SCRIPTING, PipelineStage.SCRIPT_REVIEW),
        (EpisodeStatus.SCRIPT_REVIEW, PipelineStage.AUDIO),
        (EpisodeStatus.AUDIO, PipelineStage.AVATAR),
        (EpisodeStatus.AVATAR, PipelineStage.ASSEMBLY),
        (EpisodeStatus.ASSEMBLY, PipelineStage.UPLOAD),
    ]

    next_stage = None
    for current_status, stage in stage_progression:
        if episode.status == current_status:
            next_stage = stage
            break

    if not next_stage:
        raise ValidationError(
            message=f"Episode with status '{episode.status.value}' cannot be advanced",
            field="status",
        )

    # Create job for next stage
    job = Job(
        episode_id=episode_id,
        stage=next_stage.value,
        status=JobStatus.QUEUED,
        input_params={},
    )
    db.add(job)

    # Update episode pipeline state
    episode.update_pipeline_stage(next_stage.value, "queued")

    # Update episode status
    if next_stage in STAGE_RESULT_STATUS_MAP:
        episode.status = STAGE_RESULT_STATUS_MAP[next_stage]

    db.commit()
    db.refresh(job)

    # Dispatch the Celery task
    if next_stage in STAGE_TASKS:
        task_func = STAGE_TASKS[next_stage]
        celery_task = task_func.delay(str(episode_id), str(job.id))
        job.celery_task_id = celery_task.id
        db.commit()

        logger.info(
            f"Dispatched Celery task for stage '{next_stage.value}'",
            extra={
                "episode_id": str(episode_id),
                "job_id": str(job.id),
                "celery_task_id": celery_task.id,
                "stage": next_stage.value,
            },
        )

    return ApiResponse(
        data=PipelineTriggerResponse(
            job_id=job.id,
            episode_id=episode_id,
            stage=next_stage.value,
            status=job.status.value,
            message=f"Advanced to stage '{next_stage.value}'",
        )
    )


@router.get(
    "/episodes/{episode_id}/status",
    response_model=ApiResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Status",
    description="Get the current pipeline status for an episode.",
)
async def get_pipeline_status(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """
    Get detailed pipeline status for an episode.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        Pipeline status details

    Raises:
        NotFoundError: If episode not found
    """
    # Get episode
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Get all jobs for this episode
    jobs = (
        db.query(Job)
        .filter(Job.episode_id == episode_id)
        .order_by(Job.created_at.desc())
        .all()
    )

    # Build stage status summary for ALL stages (for display)
    # but track progress only for implemented stages
    stage_summary = {}
    implemented_stage_values = {s.value for s in PIPELINE_STAGE_ORDER}

    for stage in PipelineStage:
        stage_jobs = [j for j in jobs if j.stage == stage.value]
        if stage_jobs:
            latest_job = stage_jobs[0]
            stage_summary[stage.value] = {
                "status": latest_job.status.value,
                "job_id": str(latest_job.id),
                "started_at": latest_job.started_at.isoformat() if latest_job.started_at else None,
                "completed_at": latest_job.completed_at.isoformat() if latest_job.completed_at else None,
                "duration_seconds": latest_job.duration_seconds,
                "error": latest_job.error_message,
                "attempts": len(stage_jobs),
            }
        else:
            stage_summary[stage.value] = {
                "status": "pending",
                "job_id": None,
                "started_at": None,
                "completed_at": None,
                "duration_seconds": None,
                "error": None,
                "attempts": 0,
            }

    # Calculate overall progress - only count implemented stages
    # PIPELINE_STAGE_ORDER defines the currently implemented stages
    completed_stages = sum(
        1 for stage in PIPELINE_STAGE_ORDER
        if stage_summary.get(stage.value, {}).get("status") == "completed"
    )
    total_stages = len(PIPELINE_STAGE_ORDER)

    return ApiResponse(
        data={
            "episode_id": str(episode_id),
            "episode_status": episode.status.value,
            "pipeline_progress": {
                "completed_stages": completed_stages,
                "total_stages": total_stages,
                "percent_complete": int((completed_stages / total_stages) * 100),
            },
            "stages": stage_summary,
            "active_jobs": [
                {
                    "id": str(j.id),
                    "stage": j.stage,
                    "status": j.status.value,
                }
                for j in jobs
                if j.status in [JobStatus.QUEUED, JobStatus.RUNNING]
                # Exclude orchestrator pseudo-stages (full_pipeline, stage_1)
                and j.stage in [s.value for s in PipelineStage]
            ],
        }
    )


@router.post(
    "/episodes/{episode_id}/run-stage-1",
    response_model=ApiResponse[PipelineTriggerResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run Stage 1 Pipeline",
    description=(
        "Run the Stage 1 pipeline (planning -> scripting -> metadata) "
        "for an episode. This is the content generation phase only."
    ),
)
async def run_episode_stage_1(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[PipelineTriggerResponse]:
    """
    Run Stage 1 pipeline for an episode.

    Stage 1 executes the content generation stages:
    IDEA -> planning -> scripting -> metadata -> READY

    The episode must be in IDEA, FAILED, or CANCELLED status to start.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        Pipeline trigger confirmation with Celery task ID

    Raises:
        NotFoundError: If episode not found
        ValidationError: If episode is not in valid state
    """
    # Get episode
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Validate episode status
    if episode.status not in [
        EpisodeStatus.IDEA,
        EpisodeStatus.FAILED,
        EpisodeStatus.CANCELLED,
    ]:
        raise ValidationError(
            message=(
                f"Episode must be in 'idea', 'failed', or 'cancelled' status "
                f"to start Stage 1 pipeline. Current status: {episode.status.value}"
            ),
            field="status",
            details={
                "current_status": episode.status.value,
                "allowed_statuses": ["idea", "failed", "cancelled"],
            },
        )

    # Check for any active jobs
    active_jobs = (
        db.query(Job)
        .filter(
            Job.episode_id == episode_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .count()
    )
    if active_jobs > 0:
        raise ValidationError(
            message="Episode has active jobs. Wait for them to complete or cancel them.",
            field="status",
            details={"active_job_count": active_jobs},
        )

    # Create a placeholder job for tracking the overall Stage 1 pipeline
    job = Job(
        episode_id=episode_id,
        stage="stage_1_pipeline",
        status=JobStatus.QUEUED,
        input_params={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch the Stage 1 pipeline Celery task
    celery_task = run_stage_1_pipeline.delay(str(episode_id))
    job.celery_task_id = celery_task.id
    db.commit()

    logger.info(
        f"Dispatched Stage 1 pipeline for episode {episode_id}",
        extra={
            "episode_id": str(episode_id),
            "job_id": str(job.id),
            "celery_task_id": celery_task.id,
        },
    )

    return ApiResponse(
        data=PipelineTriggerResponse(
            job_id=job.id,
            episode_id=episode_id,
            stage="stage_1_pipeline",
            status=job.status.value,
            message="Stage 1 pipeline started (planning -> scripting -> metadata)",
        )
    )


@router.post(
    "/episodes/{episode_id}/run-full",
    response_model=ApiResponse[PipelineTriggerResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run Full Pipeline",
    description=(
        "Run the full pipeline for an episode. "
        "Includes all stages from planning to B-roll."
    ),
)
async def run_episode_full_pipeline(
    episode_id: UUID,
    db: Session = Depends(get_db),
) -> ApiResponse[PipelineTriggerResponse]:
    """
    Run the full pipeline for an episode.

    Full pipeline executes all stages:
    IDEA -> planning -> scripting -> metadata -> audio -> avatar -> broll -> READY

    The episode must be in IDEA, FAILED, or CANCELLED status to start.

    Args:
        episode_id: Episode unique identifier
        db: Database session

    Returns:
        Pipeline trigger confirmation with Celery task ID

    Raises:
        NotFoundError: If episode not found
        ValidationError: If episode is not in valid state
    """
    # Get episode
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Validate episode status
    if episode.status not in [
        EpisodeStatus.IDEA,
        EpisodeStatus.FAILED,
        EpisodeStatus.CANCELLED,
    ]:
        raise ValidationError(
            message=(
                f"Episode must be in 'idea', 'failed', or 'cancelled' status "
                f"to start full pipeline. Current status: {episode.status.value}"
            ),
            field="status",
            details={
                "current_status": episode.status.value,
                "allowed_statuses": ["idea", "failed", "cancelled"],
            },
        )

    # Check for any active jobs
    active_jobs = (
        db.query(Job)
        .filter(
            Job.episode_id == episode_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .count()
    )
    if active_jobs > 0:
        raise ValidationError(
            message="Episode has active jobs. Wait for them to complete or cancel them.",
            field="status",
            details={"active_job_count": active_jobs},
        )

    # Create a placeholder job for tracking the overall pipeline
    job = Job(
        episode_id=episode_id,
        stage="full_pipeline",
        status=JobStatus.QUEUED,
        input_params={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch the full pipeline Celery task
    celery_task = run_full_pipeline.delay(str(episode_id))
    job.celery_task_id = celery_task.id
    db.commit()

    logger.info(
        f"Dispatched full pipeline for episode {episode_id}",
        extra={
            "episode_id": str(episode_id),
            "job_id": str(job.id),
            "celery_task_id": celery_task.id,
        },
    )

    return ApiResponse(
        data=PipelineTriggerResponse(
            job_id=job.id,
            episode_id=episode_id,
            stage="full_pipeline",
            status=job.status.value,
            message="Full pipeline started (all stages)",
        )
    )


@router.post(
    "/episodes/{episode_id}/run-from-stage",
    response_model=ApiResponse[PipelineTriggerResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run Pipeline From Stage",
    description=(
        "Resume the pipeline from a specific stage. "
        "Useful for retrying after failures - runs the specified stage "
        "and continues through remaining stages."
    ),
)
async def run_episode_from_stage(
    episode_id: UUID,
    request: RunFromStageRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[PipelineTriggerResponse]:
    """
    Run pipeline starting from a specific stage.

    This endpoint allows resuming a pipeline from any stage, running that
    stage and all subsequent stages. Useful for:
    - Retrying after a failure (re-run failed stage + continue)
    - Skipping completed stages when resuming

    Args:
        episode_id: Episode unique identifier
        request: Run from stage request with start_stage and optional skip_stages
        db: Database session

    Returns:
        Pipeline trigger confirmation with Celery task ID

    Raises:
        NotFoundError: If episode not found
        ValidationError: If prerequisites not met or invalid state
    """
    # Get episode
    episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .first()
    )
    if not episode:
        raise NotFoundError(resource_type="Episode", resource_id=str(episode_id))

    # Check for any active jobs
    active_jobs = (
        db.query(Job)
        .filter(
            Job.episode_id == episode_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .count()
    )
    if active_jobs > 0:
        raise ValidationError(
            message="Episode has active jobs. Wait for them to complete or cancel them.",
            field="status",
            details={"active_job_count": active_jobs},
        )

    start_stage = request.start_stage.value

    # Create a placeholder job for tracking the pipeline run
    job = Job(
        episode_id=episode_id,
        stage=f"pipeline_from_{start_stage}",
        status=JobStatus.QUEUED,
        input_params={
            "start_stage": start_stage,
            "skip_stages": request.skip_stages,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch the pipeline from stage Celery task
    celery_task = run_pipeline_from_stage.delay(
        str(episode_id),
        start_stage,
        request.skip_stages,
    )
    job.celery_task_id = celery_task.id
    db.commit()

    logger.info(
        f"Dispatched pipeline from stage '{start_stage}' for episode {episode_id}",
        extra={
            "episode_id": str(episode_id),
            "job_id": str(job.id),
            "celery_task_id": celery_task.id,
            "start_stage": start_stage,
            "skip_stages": request.skip_stages,
        },
    )

    return ApiResponse(
        data=PipelineTriggerResponse(
            job_id=job.id,
            episode_id=episode_id,
            stage=f"pipeline_from_{start_stage}",
            status=job.status.value,
            message=f"Pipeline started from '{start_stage}' (continues through remaining stages)",
        )
    )
