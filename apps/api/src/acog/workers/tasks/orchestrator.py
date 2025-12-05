"""
Pipeline orchestration tasks for ACOG episode production.

This module contains Celery tasks for orchestrating the full episode
production pipeline:
- run_full_pipeline: Execute complete pipeline from planning to B-roll
- run_pipeline_from_stage: Resume pipeline from a specific stage
- run_stage_1_pipeline: Execute Stage 1 only (planning -> scripting -> metadata)

The orchestrator uses Celery chains to ensure stages execute in order,
with proper error handling and status tracking.

Stage 1 Pipeline (Content Generation):
    IDEA -> planning -> scripting -> metadata -> READY

Full Pipeline (Future):
    IDEA -> planning -> scripting -> metadata -> audio -> avatar -> broll -> READY
"""

import logging
from typing import Any
from uuid import UUID

from celery import chain, shared_task

from acog.core.exceptions import NotFoundError, ValidationError
from acog.models import EpisodeStatus, PipelineStage
from acog.workers.celery_app import celery_app
from acog.workers.tasks.pipeline import (
    run_audio_stage,
    run_avatar_stage,
    run_broll_stage,
    run_metadata_stage,
    run_planning_stage,
    run_scripting_stage,
)
from acog.workers.utils import (
    format_task_result,
    get_db_session,
    get_episode_with_channel,
    update_episode_status,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Pipeline Stage Order
# =============================================================================

# Define the standard pipeline stage order
PIPELINE_STAGE_ORDER = [
    PipelineStage.PLANNING,
    PipelineStage.SCRIPTING,
    PipelineStage.METADATA,
    PipelineStage.AUDIO,
    PipelineStage.AVATAR,
    PipelineStage.BROLL,
]

# Map stage names to their task functions
STAGE_TASKS = {
    PipelineStage.PLANNING.value: run_planning_stage,
    PipelineStage.SCRIPTING.value: run_scripting_stage,
    PipelineStage.METADATA.value: run_metadata_stage,
    PipelineStage.AUDIO.value: run_audio_stage,
    PipelineStage.AVATAR.value: run_avatar_stage,
    PipelineStage.BROLL.value: run_broll_stage,
}


def get_stages_from(start_stage: str) -> list[PipelineStage]:
    """
    Get list of pipeline stages starting from a given stage.

    Args:
        start_stage: Stage name to start from

    Returns:
        List of PipelineStage enums from start_stage to end

    Raises:
        ValueError: If start_stage is not a valid stage
    """
    try:
        start_stage_enum = PipelineStage(start_stage)
    except ValueError:
        raise ValueError(f"Invalid pipeline stage: {start_stage}")

    start_idx = PIPELINE_STAGE_ORDER.index(start_stage_enum)
    return PIPELINE_STAGE_ORDER[start_idx:]


# =============================================================================
# Full Pipeline Orchestration
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.orchestrator.run_full_pipeline",
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=3600,  # 1 hour total timeout
    soft_time_limit=3540,
)
def run_full_pipeline(
    self,
    episode_id: str,
    skip_stages: list[str] | None = None,
    broll_max_clips: int = 3,
) -> dict[str, Any]:
    """
    Run complete episode production pipeline.

    This task orchestrates the full pipeline:
    IDEA -> planning -> scripting -> metadata -> audio -> avatar -> broll -> READY

    Each stage is executed as a Celery chain, ensuring sequential execution
    with proper error handling.

    Args:
        episode_id: UUID of the episode to process
        skip_stages: Optional list of stage names to skip
        broll_max_clips: Maximum number of B-roll clips to generate

    Returns:
        Result dict with pipeline summary:
        - episode_id: Episode UUID string
        - success: Whether all stages completed
        - stages_completed: List of completed stage names
        - stages_skipped: List of skipped stage names
        - total_cost_usd: Total cost across all stages
        - errors: List of any errors encountered
    """
    skip_stages = skip_stages or []
    skip_stages_set = set(skip_stages)

    logger.info(
        f"Starting full pipeline for episode {episode_id}",
        extra={
            "episode_id": episode_id,
            "skip_stages": skip_stages,
            "broll_max_clips": broll_max_clips,
        },
    )

    with get_db_session() as db:
        # Verify episode exists
        episode = get_episode_with_channel(db, episode_id)
        if not episode:
            raise NotFoundError("Episode", episode_id)

        # Verify episode is in valid starting state
        if episode.status not in [
            EpisodeStatus.IDEA,
            EpisodeStatus.FAILED,
            EpisodeStatus.CANCELLED,
        ]:
            raise ValidationError(
                message=f"Episode cannot start pipeline from status: {episode.status.value}",
                field="status",
                details={
                    "current_status": episode.status.value,
                    "allowed_statuses": ["idea", "failed", "cancelled"],
                },
            )

        # Build the task chain
        tasks_to_chain = []
        stages_to_run = []

        for stage in PIPELINE_STAGE_ORDER:
            if stage.value in skip_stages_set:
                logger.info(
                    f"Skipping stage {stage.value} for episode {episode_id}",
                    extra={"episode_id": episode_id, "stage": stage.value},
                )
                continue

            task_func = STAGE_TASKS[stage.value]

            # Special handling for B-roll stage with max_clips parameter
            if stage == PipelineStage.BROLL:
                tasks_to_chain.append(
                    task_func.s(episode_id, None, broll_max_clips)
                )
            else:
                tasks_to_chain.append(task_func.s(episode_id, None))

            stages_to_run.append(stage.value)

        if not tasks_to_chain:
            logger.warning(
                f"No stages to run for episode {episode_id} (all skipped)",
                extra={"episode_id": episode_id, "skip_stages": skip_stages},
            )
            return format_task_result(
                stage="full_pipeline",
                episode_id=episode_id,
                success=True,
                stages_completed=[],
                stages_skipped=skip_stages,
                message="No stages to run",
            )

        logger.info(
            f"Building pipeline chain with {len(tasks_to_chain)} stages for episode {episode_id}",
            extra={
                "episode_id": episode_id,
                "stages": stages_to_run,
            },
        )

        # Create and execute the chain
        pipeline_chain = chain(*tasks_to_chain)

        # Apply the chain asynchronously
        # The chain will execute each task in sequence, passing results along
        result = pipeline_chain.apply_async()

        logger.info(
            f"Pipeline chain started for episode {episode_id}",
            extra={
                "episode_id": episode_id,
                "chain_id": result.id,
                "stages": stages_to_run,
            },
        )

        return format_task_result(
            stage="full_pipeline",
            episode_id=episode_id,
            success=True,
            chain_id=result.id,
            stages_queued=stages_to_run,
            stages_skipped=skip_stages,
            message="Pipeline chain started",
        )


# =============================================================================
# Resume Pipeline from Stage
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.orchestrator.run_pipeline_from_stage",
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=3600,  # 1 hour total timeout
    soft_time_limit=3540,
)
def run_pipeline_from_stage(
    self,
    episode_id: str,
    start_stage: str,
    skip_stages: list[str] | None = None,
    broll_max_clips: int = 3,
) -> dict[str, Any]:
    """
    Resume pipeline from a specific stage.

    This task allows resuming a pipeline that was interrupted or failed,
    starting from a specific stage rather than from the beginning.

    Args:
        episode_id: UUID of the episode to process
        start_stage: Stage name to start from
        skip_stages: Optional list of stage names to skip
        broll_max_clips: Maximum number of B-roll clips to generate

    Returns:
        Result dict with pipeline summary
    """
    skip_stages = skip_stages or []
    skip_stages_set = set(skip_stages)

    logger.info(
        f"Starting pipeline from stage {start_stage} for episode {episode_id}",
        extra={
            "episode_id": episode_id,
            "start_stage": start_stage,
            "skip_stages": skip_stages,
        },
    )

    with get_db_session() as db:
        # Verify episode exists
        episode = get_episode_with_channel(db, episode_id)
        if not episode:
            raise NotFoundError("Episode", episode_id)

        # Get stages to run
        try:
            stages_from = get_stages_from(start_stage)
        except ValueError as e:
            raise ValidationError(
                message=str(e),
                field="start_stage",
                details={"valid_stages": [s.value for s in PIPELINE_STAGE_ORDER]},
            )

        # Check prerequisites for the start stage
        if start_stage != PipelineStage.PLANNING.value:
            # Verify previous stages are completed
            start_idx = PIPELINE_STAGE_ORDER.index(PipelineStage(start_stage))
            for prev_stage in PIPELINE_STAGE_ORDER[:start_idx]:
                if not episode.is_stage_complete(prev_stage.value):
                    # Check if it's in the skip list
                    if prev_stage.value not in skip_stages_set:
                        raise ValidationError(
                            message=f"Cannot start from {start_stage}: prerequisite stage {prev_stage.value} not completed",
                            field="start_stage",
                            details={
                                "incomplete_prerequisite": prev_stage.value,
                                "stage_status": episode.get_stage_status(prev_stage.value),
                            },
                        )

        # Clear any failed status if resuming
        if episode.status == EpisodeStatus.FAILED:
            # Reset status to the appropriate stage status
            stage_to_status = {
                PipelineStage.PLANNING.value: EpisodeStatus.PLANNING,
                PipelineStage.SCRIPTING.value: EpisodeStatus.SCRIPTING,
                PipelineStage.METADATA.value: EpisodeStatus.SCRIPT_REVIEW,
                PipelineStage.AUDIO.value: EpisodeStatus.AUDIO,
                PipelineStage.AVATAR.value: EpisodeStatus.AVATAR,
                PipelineStage.BROLL.value: EpisodeStatus.BROLL,
            }
            new_status = stage_to_status.get(start_stage, EpisodeStatus.IDEA)
            episode.status = new_status
            episode.last_error = None
            db.commit()

        # Build the task chain starting from the specified stage
        tasks_to_chain = []
        stages_to_run = []

        for stage in stages_from:
            if stage.value in skip_stages_set:
                logger.info(
                    f"Skipping stage {stage.value} for episode {episode_id}",
                    extra={"episode_id": episode_id, "stage": stage.value},
                )
                continue

            task_func = STAGE_TASKS[stage.value]

            # Special handling for B-roll stage
            if stage == PipelineStage.BROLL:
                tasks_to_chain.append(
                    task_func.s(episode_id, None, broll_max_clips)
                )
            else:
                tasks_to_chain.append(task_func.s(episode_id, None))

            stages_to_run.append(stage.value)

        if not tasks_to_chain:
            logger.warning(
                f"No stages to run for episode {episode_id} (all skipped)",
                extra={"episode_id": episode_id, "skip_stages": skip_stages},
            )
            return format_task_result(
                stage="pipeline_from_stage",
                episode_id=episode_id,
                success=True,
                start_stage=start_stage,
                stages_completed=[],
                stages_skipped=skip_stages,
                message="No stages to run",
            )

        logger.info(
            f"Building pipeline chain from {start_stage} with {len(tasks_to_chain)} stages",
            extra={
                "episode_id": episode_id,
                "start_stage": start_stage,
                "stages": stages_to_run,
            },
        )

        # Create and execute the chain
        pipeline_chain = chain(*tasks_to_chain)
        result = pipeline_chain.apply_async()

        logger.info(
            f"Pipeline chain started from {start_stage} for episode {episode_id}",
            extra={
                "episode_id": episode_id,
                "chain_id": result.id,
                "start_stage": start_stage,
                "stages": stages_to_run,
            },
        )

        return format_task_result(
            stage="pipeline_from_stage",
            episode_id=episode_id,
            success=True,
            chain_id=result.id,
            start_stage=start_stage,
            stages_queued=stages_to_run,
            stages_skipped=skip_stages,
            message=f"Pipeline chain started from {start_stage}",
        )


# =============================================================================
# Single Stage Execution
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.orchestrator.run_single_stage",
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_single_stage(
    self,
    episode_id: str,
    stage: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Run a single pipeline stage.

    This is a convenience task that dispatches to the appropriate stage task.
    Useful for running individual stages without the full pipeline.

    Args:
        episode_id: UUID of the episode to process
        stage: Stage name to run
        **kwargs: Additional arguments to pass to the stage task

    Returns:
        Result dict from the stage task
    """
    logger.info(
        f"Running single stage {stage} for episode {episode_id}",
        extra={"episode_id": episode_id, "stage": stage, "kwargs": kwargs},
    )

    if stage not in STAGE_TASKS:
        raise ValidationError(
            message=f"Invalid pipeline stage: {stage}",
            field="stage",
            details={"valid_stages": list(STAGE_TASKS.keys())},
        )

    task_func = STAGE_TASKS[stage]

    # Handle B-roll specific parameter
    if stage == PipelineStage.BROLL.value:
        max_clips = kwargs.pop("max_clips", 3)
        return task_func.delay(episode_id, None, max_clips).get()

    return task_func.delay(episode_id, None).get()


# =============================================================================
# Pipeline Status Check
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.orchestrator.check_pipeline_status",
)
def check_pipeline_status(
    self,
    episode_id: str,
) -> dict[str, Any]:
    """
    Check the current status of an episode's pipeline.

    Returns detailed information about which stages are completed,
    in progress, failed, or pending.

    Args:
        episode_id: UUID of the episode

    Returns:
        Pipeline status dict with stage-by-stage breakdown
    """
    logger.info(
        f"Checking pipeline status for episode {episode_id}",
        extra={"episode_id": episode_id},
    )

    with get_db_session() as db:
        episode = get_episode_with_channel(db, episode_id)
        if not episode:
            raise NotFoundError("Episode", episode_id)

        stages_status = {}
        completed_stages = []
        failed_stages = []
        pending_stages = []

        for stage in PIPELINE_STAGE_ORDER:
            stage_name = stage.value
            status = episode.get_stage_status(stage_name)
            stage_data = episode.pipeline_state.get(stage_name, {})

            stages_status[stage_name] = {
                "status": status,
                "started_at": stage_data.get("started_at"),
                "completed_at": stage_data.get("completed_at"),
                "error": stage_data.get("error"),
                "attempts": stage_data.get("attempts", 0),
                "cost_usd": stage_data.get("cost_usd"),
                "tokens_used": stage_data.get("tokens_used"),
            }

            if status == "completed":
                completed_stages.append(stage_name)
            elif status == "failed":
                failed_stages.append(stage_name)
            else:
                pending_stages.append(stage_name)

        return {
            "episode_id": episode_id,
            "overall_status": episode.status.value,
            "stages": stages_status,
            "completed_stages": completed_stages,
            "failed_stages": failed_stages,
            "pending_stages": pending_stages,
            "progress_percentage": len(completed_stages) / len(PIPELINE_STAGE_ORDER) * 100,
            "last_error": episode.last_error,
        }


# =============================================================================
# Finalize Pipeline
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.orchestrator.finalize_pipeline",
)
def finalize_pipeline(
    self,
    episode_id: str,
) -> dict[str, Any]:
    """
    Finalize the pipeline after all stages complete.

    This task:
    1. Verifies all required stages are completed
    2. Updates episode status to READY
    3. Calculates total costs
    4. Generates summary report

    Args:
        episode_id: UUID of the episode

    Returns:
        Pipeline completion summary
    """
    logger.info(
        f"Finalizing pipeline for episode {episode_id}",
        extra={"episode_id": episode_id},
    )

    with get_db_session() as db:
        episode = get_episode_with_channel(db, episode_id)
        if not episode:
            raise NotFoundError("Episode", episode_id)

        # Check all required stages are complete
        incomplete_stages = []
        total_cost = 0.0
        total_tokens = 0

        for stage in PIPELINE_STAGE_ORDER:
            stage_name = stage.value
            if not episode.is_stage_complete(stage_name):
                incomplete_stages.append(stage_name)
            else:
                stage_data = episode.pipeline_state.get(stage_name, {})
                total_cost += stage_data.get("cost_usd", 0) or 0
                total_tokens += stage_data.get("tokens_used", 0) or 0

        if incomplete_stages:
            logger.warning(
                f"Pipeline not complete for episode {episode_id}: incomplete stages",
                extra={
                    "episode_id": episode_id,
                    "incomplete_stages": incomplete_stages,
                },
            )
            return format_task_result(
                stage="finalize",
                episode_id=episode_id,
                success=False,
                error=f"Incomplete stages: {', '.join(incomplete_stages)}",
                incomplete_stages=incomplete_stages,
            )

        # Update episode status to READY
        episode.status = EpisodeStatus.READY
        episode.last_error = None
        db.commit()

        logger.info(
            f"Pipeline finalized for episode {episode_id}",
            extra={
                "episode_id": episode_id,
                "total_cost": total_cost,
                "total_tokens": total_tokens,
            },
        )

        return format_task_result(
            stage="finalize",
            episode_id=episode_id,
            success=True,
            cost_usd=total_cost,
            tokens_used=total_tokens,
            message="Pipeline completed successfully",
            final_status="ready",
        )


# =============================================================================
# Stage 1 Pipeline (Content Generation Only)
# =============================================================================


# Stage 1 includes only content generation stages (no audio/video)
STAGE_1_STAGES = [
    PipelineStage.PLANNING,
    PipelineStage.SCRIPTING,
    PipelineStage.METADATA,
]


@shared_task(
    bind=True,
    name="acog.workers.tasks.orchestrator.run_stage_1_pipeline",
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=1800,  # 30 minute total timeout for Stage 1
    soft_time_limit=1740,
)
def run_stage_1_pipeline(
    self,
    episode_id: str,
) -> dict[str, Any]:
    """
    Run Stage 1 pipeline: planning -> scripting -> metadata.

    This task executes the content generation portion of the pipeline:
    IDEA -> planning -> scripting -> metadata -> READY

    Each stage is executed sequentially. If any stage fails, the pipeline
    stops and the episode status is set to FAILED.

    Unlike run_full_pipeline which uses Celery chains, this task executes
    stages synchronously to ensure proper error handling and status tracking.

    Args:
        episode_id: UUID of the episode to process

    Returns:
        Result dict with pipeline summary:
        - episode_id: Episode UUID string
        - success: Whether all stages completed
        - stages_completed: List of completed stage names
        - total_cost_usd: Total cost across all stages
        - total_tokens_used: Total tokens used across all stages
        - error: Error message if failed
    """
    logger.info(
        f"[Stage 1 Pipeline] Starting for episode {episode_id}",
        extra={
            "episode_id": episode_id,
            "stages": [s.value for s in STAGE_1_STAGES],
        },
    )

    with get_db_session() as db:
        # Verify episode exists and is in valid state
        episode = get_episode_with_channel(db, episode_id)
        if not episode:
            raise NotFoundError("Episode", episode_id)

        if episode.status not in [
            EpisodeStatus.IDEA,
            EpisodeStatus.FAILED,
            EpisodeStatus.CANCELLED,
        ]:
            raise ValidationError(
                message=f"Episode cannot start Stage 1 pipeline from status: {episode.status.value}",
                field="status",
                details={
                    "current_status": episode.status.value,
                    "allowed_statuses": ["idea", "failed", "cancelled"],
                },
            )

        # Reset episode state if retrying from failed
        if episode.status in [EpisodeStatus.FAILED, EpisodeStatus.CANCELLED]:
            episode.status = EpisodeStatus.IDEA
            episode.last_error = None
            db.commit()
            logger.info(
                f"[Stage 1 Pipeline] Reset episode {episode_id} status to IDEA for retry",
                extra={"episode_id": episode_id},
            )

    # Track results
    stages_completed: list[str] = []
    total_cost_usd: float = 0.0
    total_tokens_used: int = 0
    all_asset_ids: list[str] = []

    # Execute each stage sequentially
    for stage in STAGE_1_STAGES:
        stage_name = stage.value
        task_func = STAGE_TASKS[stage_name]

        logger.info(
            f"[Stage 1 Pipeline] Starting stage '{stage_name}' for episode {episode_id}",
            extra={
                "episode_id": episode_id,
                "stage": stage_name,
                "stages_completed": stages_completed,
            },
        )

        try:
            # Execute the stage task synchronously
            # Note: We call the task directly (not .delay()) to run synchronously
            # This ensures proper sequential execution and error handling
            result = task_func(episode_id, None)

            if not result.get("success", False):
                # Stage failed - stop pipeline
                error_msg = result.get("error", f"Stage {stage_name} failed")
                logger.error(
                    f"[Stage 1 Pipeline] Stage '{stage_name}' failed for episode {episode_id}",
                    extra={
                        "episode_id": episode_id,
                        "stage": stage_name,
                        "error": error_msg,
                    },
                )

                return format_task_result(
                    stage="stage_1_pipeline",
                    episode_id=episode_id,
                    success=False,
                    stages_completed=stages_completed,
                    failed_stage=stage_name,
                    cost_usd=total_cost_usd,
                    tokens_used=total_tokens_used,
                    error=error_msg,
                )

            # Stage succeeded - track results
            stages_completed.append(stage_name)
            total_cost_usd += result.get("cost_usd", 0)
            total_tokens_used += result.get("tokens_used", 0)
            all_asset_ids.extend(result.get("asset_ids", []))

            logger.info(
                f"[Stage 1 Pipeline] Stage '{stage_name}' completed for episode {episode_id}",
                extra={
                    "episode_id": episode_id,
                    "stage": stage_name,
                    "stage_cost_usd": result.get("cost_usd", 0),
                    "stage_tokens": result.get("tokens_used", 0),
                },
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"[Stage 1 Pipeline] Exception in stage '{stage_name}' for episode {episode_id}",
                extra={
                    "episode_id": episode_id,
                    "stage": stage_name,
                    "error": error_msg,
                },
                exc_info=True,
            )

            # Update episode status to failed
            with get_db_session() as db:
                update_episode_status(
                    db, episode_id, EpisodeStatus.FAILED, last_error=error_msg
                )
                db.commit()

            return format_task_result(
                stage="stage_1_pipeline",
                episode_id=episode_id,
                success=False,
                stages_completed=stages_completed,
                failed_stage=stage_name,
                cost_usd=total_cost_usd,
                tokens_used=total_tokens_used,
                error=error_msg,
            )

    # All stages completed successfully
    logger.info(
        f"[Stage 1 Pipeline] Completed successfully for episode {episode_id}",
        extra={
            "episode_id": episode_id,
            "stages_completed": stages_completed,
            "total_cost_usd": total_cost_usd,
            "total_tokens_used": total_tokens_used,
            "asset_ids": all_asset_ids,
        },
    )

    return format_task_result(
        stage="stage_1_pipeline",
        episode_id=episode_id,
        success=True,
        stages_completed=stages_completed,
        asset_ids=all_asset_ids,
        cost_usd=total_cost_usd,
        tokens_used=total_tokens_used,
        message="Stage 1 pipeline completed successfully",
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "run_full_pipeline",
    "run_pipeline_from_stage",
    "run_single_stage",
    "run_stage_1_pipeline",
    "check_pipeline_status",
    "finalize_pipeline",
    "get_stages_from",
    "PIPELINE_STAGE_ORDER",
    "STAGE_1_STAGES",
    "STAGE_TASKS",
]
