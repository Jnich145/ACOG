"""
Pipeline stage tasks for ACOG episode production.

This module contains Celery tasks for each pipeline stage:
- Planning: Generate episode plan using OpenAI
- Scripting: Generate script from plan using OpenAI
- Metadata: Generate video metadata (titles, descriptions, tags)
- Audio: Generate audio using ElevenLabs
- Avatar: Generate avatar video using HeyGen
- B-roll: Generate B-roll clips using Runway

Each task:
- Is idempotent (safe to retry)
- Creates/updates Job records with status
- Updates Episode.pipeline_state
- Updates Episode.status
- Handles errors and updates Job.error_message
- Returns a result dict with asset_ids, cost, duration
"""

import logging
from typing import Any
from uuid import UUID

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from acog.core.config import get_settings
from acog.core.exceptions import NotFoundError, PipelineError, ValidationError
from acog.integrations import (
    ElevenLabsClient,
    HeyGenClient,
    RunwayClient,
    StorageClient,
    VoiceSettings,
)
from acog.models import AssetType, EpisodeStatus, JobStatus, PipelineStage
from acog.services import MetadataService, PlanningService, ScriptService
from acog.workers.celery_app import calculate_retry_countdown, celery_app, get_retry_policy
from acog.workers.utils import (
    create_asset_record,
    create_job_record,
    format_task_result,
    get_db_session,
    get_episode_with_channel,
    stage_already_completed,
    update_episode_pipeline_state,
    update_episode_status,
    update_job_status,
    validate_episode_for_stage,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Planning Stage Task
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.pipeline.run_planning_stage",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def run_planning_stage(
    self,
    episode_id: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Generate episode plan using OpenAI.

    This task:
    1. Fetches the episode and channel information
    2. Generates a structured plan using PlanningService
    3. Stores the plan in the episode record
    4. Updates pipeline state and job status

    Args:
        episode_id: UUID of the episode to plan
        job_id: Optional UUID of the job record for tracking

    Returns:
        Result dict with:
        - stage: "planning"
        - episode_id: Episode UUID string
        - job_id: Job UUID string
        - success: Whether planning succeeded
        - cost_usd: Cost of the planning operation
        - tokens_used: Number of tokens used
        - plan_summary: Brief summary of the generated plan
    """
    stage = PipelineStage.PLANNING.value
    settings = get_settings()

    logger.info(
        f"Starting planning stage for episode {episode_id}",
        extra={"episode_id": episode_id, "job_id": job_id},
    )

    with get_db_session() as db:
        try:
            # Validate episode can proceed to this stage
            is_valid, validation_error = validate_episode_for_stage(db, episode_id, stage)
            if not is_valid:
                logger.warning(
                    f"Validation failed for planning stage: {validation_error}",
                    extra={"episode_id": episode_id, "error": validation_error},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=False,
                    error=validation_error,
                )

            # Check idempotency - if already completed, return early
            if stage_already_completed(db, episode_id, stage):
                logger.info(
                    f"Planning stage already completed for episode {episode_id}",
                    extra={"episode_id": episode_id},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=True,
                    already_completed=True,
                )

            # Create job record if not provided
            if not job_id:
                job = create_job_record(
                    db=db,
                    episode_id=episode_id,
                    stage=stage,
                    celery_task_id=self.request.id,
                )
                job_id = str(job.id)
                db.commit()

            # Update job status to running
            update_job_status(db, job_id, JobStatus.RUNNING)
            db.commit()

            # Update episode pipeline state
            update_episode_pipeline_state(
                db, episode_id, stage, "running"
            )
            update_episode_status(db, episode_id, EpisodeStatus.PLANNING)
            db.commit()

            # Get episode with channel
            episode = get_episode_with_channel(db, episode_id)
            if not episode:
                raise NotFoundError("Episode", episode_id)

            # Extract topic from idea
            topic = episode.idea.get("topic") or episode.title
            if not topic:
                raise ValidationError(
                    message="Episode has no topic or title for planning",
                    field="topic",
                )

            additional_context = episode.idea.get("additional_context")

            # Create planning service and generate plan
            planning_service = PlanningService(db=db)
            result = planning_service.generate_plan(
                episode_id=UUID(episode_id),
                topic=topic,
                additional_context=additional_context,
                job_id=UUID(job_id) if job_id else None,
            )

            # Create plan asset record
            plan_content = result.plan.model_dump_json(indent=2).encode("utf-8")
            storage = StorageClient(settings=settings)
            storage_result = storage.upload_episode_asset(
                data=plan_content,
                episode_id=UUID(episode_id),
                asset_type="plan",
                file_extension="json",
                content_type="application/json",
            )

            # Create asset record
            asset = create_asset_record(
                db=db,
                episode_id=episode_id,
                asset_type=AssetType.PLAN,
                uri=storage_result.uri,
                storage_bucket=storage_result.bucket,
                storage_key=storage_result.key,
                provider="openai",
                mime_type="application/json",
                file_size_bytes=storage_result.file_size_bytes,
                metadata={
                    "model_used": result.model_used,
                    "tokens_used": result.usage.total_tokens,
                    "cost_usd": float(result.usage.estimated_cost_usd),
                },
                is_primary=True,
                name=f"Episode Plan - {result.plan.title_suggestion[:50]}",
            )

            # Update job with success
            update_job_status(
                db=db,
                job_id=job_id,
                status=JobStatus.COMPLETED,
                result={
                    "plan_generated": True,
                    "estimated_duration_seconds": result.plan.estimated_total_duration_seconds,
                    "section_count": len(result.plan.sections),
                    "asset_id": str(asset.id),
                },
                cost_usd=float(result.usage.estimated_cost_usd),
                tokens_used=result.usage.total_tokens,
            )

            # Update pipeline state to completed
            update_episode_pipeline_state(
                db=db,
                episode_id=episode_id,
                stage=stage,
                status="completed",
                model_used=result.model_used,
                tokens_used=result.usage.total_tokens,
                cost_usd=float(result.usage.estimated_cost_usd),
            )

            # Ensure episode status is set to PLANNING (indicates plan is ready)
            # This allows the next stage (scripting) to proceed
            update_episode_status(db, episode_id, EpisodeStatus.PLANNING)

            db.commit()

            logger.info(
                f"Planning stage completed for episode {episode_id}",
                extra={
                    "episode_id": episode_id,
                    "job_id": job_id,
                    "tokens_used": result.usage.total_tokens,
                    "cost_usd": float(result.usage.estimated_cost_usd),
                    "new_status": "planning",
                    "sections_count": len(result.plan.sections),
                },
            )

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=True,
                asset_ids=[str(asset.id)],
                cost_usd=float(result.usage.estimated_cost_usd),
                tokens_used=result.usage.total_tokens,
                plan_summary=result.plan.topic_summary,
            )

        except MaxRetriesExceededError:
            error_msg = f"Planning stage failed after max retries for episode {episode_id}"
            logger.error(error_msg, extra={"episode_id": episode_id})

            if job_id:
                update_job_status(db, job_id, JobStatus.FAILED, error_message=error_msg)
            update_episode_pipeline_state(db, episode_id, stage, "failed", error=error_msg)
            update_episode_status(db, episode_id, EpisodeStatus.FAILED, last_error=error_msg)
            db.commit()

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=False,
                error=error_msg,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Planning stage failed for episode {episode_id}: {error_msg}",
                extra={"episode_id": episode_id, "error": error_msg},
                exc_info=True,
            )

            # Check if we should retry
            retry_policy = get_retry_policy(stage)
            if self.request.retries < retry_policy["max_retries"]:
                countdown = calculate_retry_countdown(stage, self.request.retries)
                logger.info(
                    f"Retrying planning stage for episode {episode_id} in {countdown}s",
                    extra={
                        "episode_id": episode_id,
                        "retry_count": self.request.retries,
                        "countdown": countdown,
                    },
                )

                # Update pipeline state to indicate retry
                update_episode_pipeline_state(
                    db, episode_id, stage, "running",
                    error=f"Retry {self.request.retries + 1}: {error_msg}",
                )
                db.commit()

                raise self.retry(countdown=countdown, exc=e)

            # Max retries exceeded - mark as failed
            if job_id:
                update_job_status(db, job_id, JobStatus.FAILED, error_message=error_msg)
            update_episode_pipeline_state(db, episode_id, stage, "failed", error=error_msg)
            update_episode_status(db, episode_id, EpisodeStatus.FAILED, last_error=error_msg)
            db.commit()

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=False,
                error=error_msg,
            )


# =============================================================================
# Scripting Stage Task
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.pipeline.run_scripting_stage",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def run_scripting_stage(
    self,
    episode_id: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Generate script from plan using OpenAI.

    This task:
    1. Fetches the episode with its plan
    2. Generates a full script using ScriptService
    3. Stores the script in the episode record
    4. Updates pipeline state and job status

    Args:
        episode_id: UUID of the episode
        job_id: Optional UUID of the job record for tracking

    Returns:
        Result dict with script metadata
    """
    stage = PipelineStage.SCRIPTING.value
    settings = get_settings()

    logger.info(
        f"Starting scripting stage for episode {episode_id}",
        extra={"episode_id": episode_id, "job_id": job_id},
    )

    with get_db_session() as db:
        try:
            # Validate episode can proceed to this stage
            is_valid, validation_error = validate_episode_for_stage(db, episode_id, stage)
            if not is_valid:
                logger.warning(
                    f"Validation failed for scripting stage: {validation_error}",
                    extra={"episode_id": episode_id, "error": validation_error},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=False,
                    error=validation_error,
                )

            # Check idempotency
            if stage_already_completed(db, episode_id, stage):
                logger.info(
                    f"Scripting stage already completed for episode {episode_id}",
                    extra={"episode_id": episode_id},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=True,
                    already_completed=True,
                )

            # Create job record if not provided
            if not job_id:
                job = create_job_record(
                    db=db,
                    episode_id=episode_id,
                    stage=stage,
                    celery_task_id=self.request.id,
                )
                job_id = str(job.id)
                db.commit()

            # Update job status to running
            update_job_status(db, job_id, JobStatus.RUNNING)
            db.commit()

            # Update episode pipeline state
            update_episode_pipeline_state(db, episode_id, stage, "running")
            update_episode_status(db, episode_id, EpisodeStatus.SCRIPTING)
            db.commit()

            # Verify episode has a plan
            episode = get_episode_with_channel(db, episode_id)
            if not episode:
                raise NotFoundError("Episode", episode_id)

            if not episode.plan:
                raise ValidationError(
                    message="Episode has no plan. Run planning stage first.",
                    field="plan",
                )

            # Create script service and generate script
            script_service = ScriptService(db=db)
            result = script_service.generate_script(
                episode_id=UUID(episode_id),
                job_id=UUID(job_id) if job_id else None,
            )

            # Upload script to storage
            script_content = result.formatted_script.encode("utf-8")
            storage = StorageClient(settings=settings)
            storage_result = storage.upload_episode_asset(
                data=script_content,
                episode_id=UUID(episode_id),
                asset_type="script",
                file_extension="md",
                content_type="text/markdown",
            )

            # Create asset record
            asset = create_asset_record(
                db=db,
                episode_id=episode_id,
                asset_type=AssetType.SCRIPT,
                uri=storage_result.uri,
                storage_bucket=storage_result.bucket,
                storage_key=storage_result.key,
                provider="openai",
                mime_type="text/markdown",
                file_size_bytes=storage_result.file_size_bytes,
                metadata={
                    "model_used": result.model_used,
                    "tokens_used": result.usage.total_tokens,
                    "cost_usd": float(result.usage.estimated_cost_usd),
                    "word_count": result.word_count,
                    "estimated_duration_seconds": result.estimated_duration_seconds,
                },
                is_primary=True,
                name=f"Episode Script - {result.script.title[:50]}",
            )

            # Update job with success
            update_job_status(
                db=db,
                job_id=job_id,
                status=JobStatus.COMPLETED,
                result={
                    "script_generated": True,
                    "word_count": result.word_count,
                    "estimated_duration_seconds": result.estimated_duration_seconds,
                    "section_count": len(result.script.main_sections),
                    "asset_id": str(asset.id),
                },
                cost_usd=float(result.usage.estimated_cost_usd),
                tokens_used=result.usage.total_tokens,
            )

            # Update pipeline state to completed
            update_episode_pipeline_state(
                db=db,
                episode_id=episode_id,
                stage=stage,
                status="completed",
                model_used=result.model_used,
                tokens_used=result.usage.total_tokens,
                cost_usd=float(result.usage.estimated_cost_usd),
                word_count=result.word_count,
            )

            # Transition episode to SCRIPT_REVIEW after scripting completes
            update_episode_status(db, episode_id, EpisodeStatus.SCRIPT_REVIEW)

            db.commit()

            logger.info(
                f"Scripting stage completed for episode {episode_id}",
                extra={
                    "episode_id": episode_id,
                    "job_id": job_id,
                    "word_count": result.word_count,
                    "tokens_used": result.usage.total_tokens,
                    "new_status": "script_review",
                },
            )

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=True,
                asset_ids=[str(asset.id)],
                cost_usd=float(result.usage.estimated_cost_usd),
                tokens_used=result.usage.total_tokens,
                word_count=result.word_count,
                duration_seconds=result.estimated_duration_seconds,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Scripting stage failed for episode {episode_id}: {error_msg}",
                extra={"episode_id": episode_id, "error": error_msg},
                exc_info=True,
            )

            retry_policy = get_retry_policy(stage)
            if self.request.retries < retry_policy["max_retries"]:
                countdown = calculate_retry_countdown(stage, self.request.retries)
                update_episode_pipeline_state(
                    db, episode_id, stage, "running",
                    error=f"Retry {self.request.retries + 1}: {error_msg}",
                )
                db.commit()
                raise self.retry(countdown=countdown, exc=e)

            if job_id:
                update_job_status(db, job_id, JobStatus.FAILED, error_message=error_msg)
            update_episode_pipeline_state(db, episode_id, stage, "failed", error=error_msg)
            update_episode_status(db, episode_id, EpisodeStatus.FAILED, last_error=error_msg)
            db.commit()

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=False,
                error=error_msg,
            )


# =============================================================================
# Metadata Stage Task
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.pipeline.run_metadata_stage",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def run_metadata_stage(
    self,
    episode_id: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Generate video metadata from script.

    This task:
    1. Fetches the episode with its script
    2. Generates SEO metadata using MetadataService
    3. Stores the metadata in the episode record
    4. Updates pipeline state and job status

    Args:
        episode_id: UUID of the episode
        job_id: Optional UUID of the job record for tracking

    Returns:
        Result dict with metadata summary
    """
    stage = PipelineStage.METADATA.value
    settings = get_settings()

    logger.info(
        f"Starting metadata stage for episode {episode_id}",
        extra={"episode_id": episode_id, "job_id": job_id},
    )

    with get_db_session() as db:
        try:
            # Validate episode can proceed to this stage
            is_valid, validation_error = validate_episode_for_stage(db, episode_id, stage)
            if not is_valid:
                logger.warning(
                    f"Validation failed for metadata stage: {validation_error}",
                    extra={"episode_id": episode_id, "error": validation_error},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=False,
                    error=validation_error,
                )

            # Check idempotency
            if stage_already_completed(db, episode_id, stage):
                logger.info(
                    f"Metadata stage already completed for episode {episode_id}",
                    extra={"episode_id": episode_id},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=True,
                    already_completed=True,
                )

            # Create job record if not provided
            if not job_id:
                job = create_job_record(
                    db=db,
                    episode_id=episode_id,
                    stage=stage,
                    celery_task_id=self.request.id,
                )
                job_id = str(job.id)
                db.commit()

            # Update job status to running
            update_job_status(db, job_id, JobStatus.RUNNING)
            db.commit()

            # Update episode pipeline state and status
            update_episode_pipeline_state(db, episode_id, stage, "running")
            update_episode_status(db, episode_id, EpisodeStatus.SCRIPT_REVIEW)
            db.commit()

            # Create metadata service and generate metadata
            metadata_service = MetadataService(db=db)
            result = metadata_service.generate_metadata(
                episode_id=UUID(episode_id),
                job_id=UUID(job_id) if job_id else None,
            )

            # Upload metadata to storage
            metadata_content = result.metadata.model_dump_json(indent=2).encode("utf-8")
            storage = StorageClient(settings=settings)
            storage_result = storage.upload_episode_asset(
                data=metadata_content,
                episode_id=UUID(episode_id),
                asset_type="metadata",
                file_extension="json",
                content_type="application/json",
            )

            # Create asset record
            asset = create_asset_record(
                db=db,
                episode_id=episode_id,
                asset_type=AssetType.METADATA,
                uri=storage_result.uri,
                storage_bucket=storage_result.bucket,
                storage_key=storage_result.key,
                provider="openai",
                mime_type="application/json",
                file_size_bytes=storage_result.file_size_bytes,
                metadata={
                    "model_used": result.model_used,
                    "tokens_used": result.usage.total_tokens,
                    "cost_usd": float(result.usage.estimated_cost_usd),
                    "title_options_count": len(result.metadata.title_options),
                    "tags_count": len(result.metadata.tags),
                },
                is_primary=True,
                name=f"Episode Metadata - {result.metadata.recommended_title[:50]}",
            )

            # Update job with success
            update_job_status(
                db=db,
                job_id=job_id,
                status=JobStatus.COMPLETED,
                result={
                    "metadata_generated": True,
                    "recommended_title": result.metadata.recommended_title,
                    "tags_count": len(result.metadata.tags),
                    "thumbnail_prompts_count": len(result.metadata.thumbnail_prompts),
                    "asset_id": str(asset.id),
                },
                cost_usd=float(result.usage.estimated_cost_usd),
                tokens_used=result.usage.total_tokens,
            )

            # Update pipeline state to completed
            update_episode_pipeline_state(
                db=db,
                episode_id=episode_id,
                stage=stage,
                status="completed",
                model_used=result.model_used,
                tokens_used=result.usage.total_tokens,
                cost_usd=float(result.usage.estimated_cost_usd),
            )

            # For Stage 1 (planning -> scripting -> metadata only), mark as READY
            # This transitions the episode past script_review to indicate metadata is complete
            # In full pipeline, this would be handled by the orchestrator after all stages
            episode = get_episode_with_channel(db, episode_id)
            if episode and episode.status == EpisodeStatus.SCRIPT_REVIEW:
                # Check if we're in Stage 1 mode (no audio stage configured yet)
                # For now, update to READY to indicate Stage 1 completion
                update_episode_status(db, episode_id, EpisodeStatus.READY)
                logger.info(
                    f"Episode {episode_id} status updated to READY (Stage 1 complete)",
                    extra={"episode_id": episode_id},
                )

            db.commit()

            logger.info(
                f"Metadata stage completed for episode {episode_id}",
                extra={
                    "episode_id": episode_id,
                    "job_id": job_id,
                    "recommended_title": result.metadata.recommended_title[:50],
                },
            )

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=True,
                asset_ids=[str(asset.id)],
                cost_usd=float(result.usage.estimated_cost_usd),
                tokens_used=result.usage.total_tokens,
                recommended_title=result.metadata.recommended_title,
                tags_count=len(result.metadata.tags),
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Metadata stage failed for episode {episode_id}: {error_msg}",
                extra={"episode_id": episode_id, "error": error_msg},
                exc_info=True,
            )

            retry_policy = get_retry_policy(stage)
            if self.request.retries < retry_policy["max_retries"]:
                countdown = calculate_retry_countdown(stage, self.request.retries)
                update_episode_pipeline_state(
                    db, episode_id, stage, "running",
                    error=f"Retry {self.request.retries + 1}: {error_msg}",
                )
                db.commit()
                raise self.retry(countdown=countdown, exc=e)

            if job_id:
                update_job_status(db, job_id, JobStatus.FAILED, error_message=error_msg)
            update_episode_pipeline_state(db, episode_id, stage, "failed", error=error_msg)
            db.commit()

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=False,
                error=error_msg,
            )


# =============================================================================
# Audio Stage Task
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.pipeline.run_audio_stage",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    time_limit=600,  # 10 minute timeout
    soft_time_limit=540,
)
def run_audio_stage(
    self,
    episode_id: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Generate audio using ElevenLabs.

    This task:
    1. Fetches the episode with its script
    2. Extracts voiceover text from script
    3. Generates audio using ElevenLabs
    4. Uploads audio to S3
    5. Creates asset record
    6. Updates pipeline state and job status

    Args:
        episode_id: UUID of the episode
        job_id: Optional UUID of the job record for tracking

    Returns:
        Result dict with audio metadata
    """
    stage = PipelineStage.AUDIO.value
    settings = get_settings()

    logger.info(
        f"Starting audio stage for episode {episode_id}",
        extra={"episode_id": episode_id, "job_id": job_id},
    )

    with get_db_session() as db:
        try:
            # Validate episode can proceed to this stage
            is_valid, validation_error = validate_episode_for_stage(db, episode_id, stage)
            if not is_valid:
                logger.warning(
                    f"Validation failed for audio stage: {validation_error}",
                    extra={"episode_id": episode_id, "error": validation_error},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=False,
                    error=validation_error,
                )

            # Check idempotency
            if stage_already_completed(db, episode_id, stage):
                logger.info(
                    f"Audio stage already completed for episode {episode_id}",
                    extra={"episode_id": episode_id},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=True,
                    already_completed=True,
                )

            # Create job record if not provided
            if not job_id:
                job = create_job_record(
                    db=db,
                    episode_id=episode_id,
                    stage=stage,
                    celery_task_id=self.request.id,
                )
                job_id = str(job.id)
                db.commit()

            # Update job status to running
            update_job_status(db, job_id, JobStatus.RUNNING)
            db.commit()

            # Update episode pipeline state
            update_episode_pipeline_state(db, episode_id, stage, "running")
            update_episode_status(db, episode_id, EpisodeStatus.AUDIO)
            db.commit()

            # Get episode with channel for voice settings
            episode = get_episode_with_channel(db, episode_id)
            if not episode:
                raise NotFoundError("Episode", episode_id)

            if not episode.script:
                raise ValidationError(
                    message="Episode has no script. Run scripting stage first.",
                    field="script",
                )

            # Extract voiceover text
            script_service = ScriptService(db=db)
            voiceover_text = script_service.extract_voiceover_text(UUID(episode_id))

            if not voiceover_text or not voiceover_text.strip():
                raise ValidationError(
                    message="No voiceover text found in script",
                    field="script",
                )

            # Get voice settings from channel
            channel = episode.channel
            voice_settings_dict = channel.get_voice_settings()
            voice_id = voice_settings_dict.get("voice_id")

            if not voice_id:
                # Use default voice
                voice_id = ElevenLabsClient.DEFAULT_VOICES.get("rachel")
                logger.warning(
                    f"No voice_id configured for channel, using default: {voice_id}",
                    extra={"channel_id": str(channel.id), "voice_id": voice_id},
                )

            voice_settings = VoiceSettings(
                stability=voice_settings_dict.get("stability", 0.5),
                similarity_boost=voice_settings_dict.get("similarity_boost", 0.75),
                style=voice_settings_dict.get("style", 0.0),
            )

            # Initialize ElevenLabs client and storage
            elevenlabs = ElevenLabsClient(settings=settings)
            storage = StorageClient(settings=settings)

            # Generate speech and save to S3
            result = elevenlabs.generate_speech_and_save(
                text=voiceover_text,
                voice_id=voice_id,
                episode_id=UUID(episode_id),
                storage_client=storage,
                voice_settings=voice_settings,
            )

            # Create asset record
            asset = create_asset_record(
                db=db,
                episode_id=episode_id,
                asset_type=AssetType.AUDIO,
                uri=result.storage_result.uri,
                storage_bucket=result.storage_result.bucket,
                storage_key=result.storage_result.key,
                provider="elevenlabs",
                provider_job_id=None,  # ElevenLabs is synchronous
                mime_type=result.content_type,
                file_size_bytes=result.file_size_bytes,
                duration_ms=result.duration_ms,
                metadata={
                    "voice_id": result.voice_id,
                    "model_id": result.model_id,
                    "character_count": result.character_count,
                    "cost_usd": float(result.usage.estimated_cost_usd) if result.usage else 0,
                },
                is_primary=True,
                name="Episode Audio",
            )

            cost_usd = float(result.usage.estimated_cost_usd) if result.usage else 0

            # Update job with success
            update_job_status(
                db=db,
                job_id=job_id,
                status=JobStatus.COMPLETED,
                result={
                    "audio_generated": True,
                    "duration_ms": result.duration_ms,
                    "file_size_bytes": result.file_size_bytes,
                    "voice_id": result.voice_id,
                    "asset_id": str(asset.id),
                },
                cost_usd=cost_usd,
            )

            # Update pipeline state to completed
            update_episode_pipeline_state(
                db=db,
                episode_id=episode_id,
                stage=stage,
                status="completed",
                voice_id=result.voice_id,
                model_id=result.model_id,
                duration_ms=result.duration_ms,
                cost_usd=cost_usd,
            )

            db.commit()

            logger.info(
                f"Audio stage completed for episode {episode_id}",
                extra={
                    "episode_id": episode_id,
                    "job_id": job_id,
                    "duration_ms": result.duration_ms,
                    "cost_usd": cost_usd,
                },
            )

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=True,
                asset_ids=[str(asset.id)],
                cost_usd=cost_usd,
                duration_seconds=result.duration_seconds,
                voice_id=result.voice_id,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Audio stage failed for episode {episode_id}: {error_msg}",
                extra={"episode_id": episode_id, "error": error_msg},
                exc_info=True,
            )

            retry_policy = get_retry_policy(stage)
            if self.request.retries < retry_policy["max_retries"]:
                countdown = calculate_retry_countdown(stage, self.request.retries)
                update_episode_pipeline_state(
                    db, episode_id, stage, "running",
                    error=f"Retry {self.request.retries + 1}: {error_msg}",
                )
                db.commit()
                raise self.retry(countdown=countdown, exc=e)

            if job_id:
                update_job_status(db, job_id, JobStatus.FAILED, error_message=error_msg)
            update_episode_pipeline_state(db, episode_id, stage, "failed", error=error_msg)
            update_episode_status(db, episode_id, EpisodeStatus.FAILED, last_error=error_msg)
            db.commit()

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=False,
                error=error_msg,
            )


# =============================================================================
# Avatar Stage Task
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.pipeline.run_avatar_stage",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    time_limit=900,  # 15 minute timeout (avatar generation can be slow)
    soft_time_limit=840,
)
def run_avatar_stage(
    self,
    episode_id: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Generate avatar video using HeyGen.

    This task:
    1. Fetches the episode with its script
    2. Extracts avatar segments from script
    3. Generates talking head video using HeyGen
    4. Waits for video completion
    5. Downloads and uploads to S3
    6. Creates asset record
    7. Updates pipeline state and job status

    Args:
        episode_id: UUID of the episode
        job_id: Optional UUID of the job record for tracking

    Returns:
        Result dict with video metadata
    """
    stage = PipelineStage.AVATAR.value
    settings = get_settings()

    logger.info(
        f"Starting avatar stage for episode {episode_id}",
        extra={"episode_id": episode_id, "job_id": job_id},
    )

    with get_db_session() as db:
        try:
            # Validate episode can proceed to this stage
            is_valid, validation_error = validate_episode_for_stage(db, episode_id, stage)
            if not is_valid:
                logger.warning(
                    f"Validation failed for avatar stage: {validation_error}",
                    extra={"episode_id": episode_id, "error": validation_error},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=False,
                    error=validation_error,
                )

            # Check idempotency
            if stage_already_completed(db, episode_id, stage):
                logger.info(
                    f"Avatar stage already completed for episode {episode_id}",
                    extra={"episode_id": episode_id},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=True,
                    already_completed=True,
                )

            # Create job record if not provided
            if not job_id:
                job = create_job_record(
                    db=db,
                    episode_id=episode_id,
                    stage=stage,
                    celery_task_id=self.request.id,
                )
                job_id = str(job.id)
                db.commit()

            # Update job status to running
            update_job_status(db, job_id, JobStatus.RUNNING)
            db.commit()

            # Update episode pipeline state
            update_episode_pipeline_state(db, episode_id, stage, "running")
            update_episode_status(db, episode_id, EpisodeStatus.AVATAR)
            db.commit()

            # Get episode with channel for avatar settings
            episode = get_episode_with_channel(db, episode_id)
            if not episode:
                raise NotFoundError("Episode", episode_id)

            if not episode.script:
                raise ValidationError(
                    message="Episode has no script. Run scripting stage first.",
                    field="script",
                )

            # Get avatar settings from channel
            channel = episode.channel
            avatar_settings = channel.get_avatar_settings()
            avatar_id = avatar_settings.get("avatar_id")

            if not avatar_id:
                # Use default avatar
                avatar_id = HeyGenClient.DEFAULT_AVATARS.get("josh")
                logger.warning(
                    f"No avatar_id configured for channel, using default: {avatar_id}",
                    extra={"channel_id": str(channel.id), "avatar_id": avatar_id},
                )

            # Extract avatar text from script (text marked with [AVATAR:])
            import re
            avatar_pattern = r'\[AVATAR:\s*([^\]]+)\]'
            avatar_matches = re.findall(avatar_pattern, episode.script)

            if not avatar_matches:
                # If no avatar markers, use the voiceover text
                script_service = ScriptService(db=db)
                avatar_text = script_service.extract_voiceover_text(UUID(episode_id))
            else:
                avatar_text = "\n\n".join(avatar_matches)

            if not avatar_text or not avatar_text.strip():
                raise ValidationError(
                    message="No avatar text found in script",
                    field="script",
                )

            # Initialize HeyGen client and storage
            heygen = HeyGenClient(settings=settings)
            storage = StorageClient(settings=settings)

            # Generate video and save to S3
            result = heygen.create_video_and_save(
                script_text=avatar_text,
                avatar_id=avatar_id,
                episode_id=UUID(episode_id),
                storage_client=storage,
            )

            # Create asset record
            asset = create_asset_record(
                db=db,
                episode_id=episode_id,
                asset_type=AssetType.AVATAR_VIDEO,
                uri=result.storage_result.uri,
                storage_bucket=result.storage_result.bucket,
                storage_key=result.storage_result.key,
                provider="heygen",
                provider_job_id=result.video_id,
                mime_type=result.content_type,
                file_size_bytes=result.file_size_bytes,
                duration_ms=result.duration_ms,
                metadata={
                    "video_id": result.video_id,
                    "avatar_id": avatar_id,
                    "thumbnail_url": result.thumbnail_url,
                    "cost_usd": float(result.usage.estimated_cost_usd) if result.usage else 0,
                },
                is_primary=True,
                name="Episode Avatar Video",
            )

            cost_usd = float(result.usage.estimated_cost_usd) if result.usage else 0

            # Update job with success
            update_job_status(
                db=db,
                job_id=job_id,
                status=JobStatus.COMPLETED,
                result={
                    "video_generated": True,
                    "video_id": result.video_id,
                    "duration_ms": result.duration_ms,
                    "file_size_bytes": result.file_size_bytes,
                    "avatar_id": avatar_id,
                    "asset_id": str(asset.id),
                },
                cost_usd=cost_usd,
            )

            # Update pipeline state to completed
            update_episode_pipeline_state(
                db=db,
                episode_id=episode_id,
                stage=stage,
                status="completed",
                video_id=result.video_id,
                avatar_id=avatar_id,
                duration_ms=result.duration_ms,
                cost_usd=cost_usd,
            )

            db.commit()

            logger.info(
                f"Avatar stage completed for episode {episode_id}",
                extra={
                    "episode_id": episode_id,
                    "job_id": job_id,
                    "video_id": result.video_id,
                    "duration_ms": result.duration_ms,
                    "cost_usd": cost_usd,
                },
            )

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=True,
                asset_ids=[str(asset.id)],
                cost_usd=cost_usd,
                duration_seconds=result.duration_seconds,
                video_id=result.video_id,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Avatar stage failed for episode {episode_id}: {error_msg}",
                extra={"episode_id": episode_id, "error": error_msg},
                exc_info=True,
            )

            retry_policy = get_retry_policy(stage)
            if self.request.retries < retry_policy["max_retries"]:
                countdown = calculate_retry_countdown(stage, self.request.retries)
                update_episode_pipeline_state(
                    db, episode_id, stage, "running",
                    error=f"Retry {self.request.retries + 1}: {error_msg}",
                )
                db.commit()
                raise self.retry(countdown=countdown, exc=e)

            if job_id:
                update_job_status(db, job_id, JobStatus.FAILED, error_message=error_msg)
            update_episode_pipeline_state(db, episode_id, stage, "failed", error=error_msg)
            update_episode_status(db, episode_id, EpisodeStatus.FAILED, last_error=error_msg)
            db.commit()

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=False,
                error=error_msg,
            )


# =============================================================================
# B-Roll Stage Task
# =============================================================================


@shared_task(
    bind=True,
    name="acog.workers.tasks.pipeline.run_broll_stage",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    time_limit=900,  # 15 minute timeout
    soft_time_limit=840,
)
def run_broll_stage(
    self,
    episode_id: str,
    job_id: str | None = None,
    max_clips: int = 3,
) -> dict[str, Any]:
    """
    Generate B-roll clips using Runway.

    This task:
    1. Fetches the episode with its plan/script
    2. Extracts B-roll suggestions from plan
    3. Generates video clips using Runway
    4. Uploads clips to S3
    5. Creates asset records
    6. Updates pipeline state and job status

    Args:
        episode_id: UUID of the episode
        job_id: Optional UUID of the job record for tracking
        max_clips: Maximum number of B-roll clips to generate (default: 3)

    Returns:
        Result dict with B-roll metadata
    """
    stage = PipelineStage.BROLL.value
    settings = get_settings()

    logger.info(
        f"Starting B-roll stage for episode {episode_id}",
        extra={"episode_id": episode_id, "job_id": job_id, "max_clips": max_clips},
    )

    with get_db_session() as db:
        try:
            # Validate episode can proceed to this stage
            is_valid, validation_error = validate_episode_for_stage(db, episode_id, stage)
            if not is_valid:
                logger.warning(
                    f"Validation failed for B-roll stage: {validation_error}",
                    extra={"episode_id": episode_id, "error": validation_error},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=False,
                    error=validation_error,
                )

            # Check idempotency
            if stage_already_completed(db, episode_id, stage):
                logger.info(
                    f"B-roll stage already completed for episode {episode_id}",
                    extra={"episode_id": episode_id},
                )
                return format_task_result(
                    stage=stage,
                    episode_id=episode_id,
                    job_id=job_id,
                    success=True,
                    already_completed=True,
                )

            # Create job record if not provided
            if not job_id:
                job = create_job_record(
                    db=db,
                    episode_id=episode_id,
                    stage=stage,
                    celery_task_id=self.request.id,
                    input_params={"max_clips": max_clips},
                )
                job_id = str(job.id)
                db.commit()

            # Update job status to running
            update_job_status(db, job_id, JobStatus.RUNNING)
            db.commit()

            # Update episode pipeline state
            update_episode_pipeline_state(db, episode_id, stage, "running")
            update_episode_status(db, episode_id, EpisodeStatus.BROLL)
            db.commit()

            # Get episode
            episode = get_episode_with_channel(db, episode_id)
            if not episode:
                raise NotFoundError("Episode", episode_id)

            # Extract B-roll prompts from plan and script
            broll_prompts = []

            # From plan sections
            if episode.plan:
                for section in episode.plan.get("sections", []):
                    for suggestion in section.get("broll_suggestions", []):
                        if suggestion and len(broll_prompts) < max_clips:
                            broll_prompts.append(suggestion)

            # From script [BROLL:] markers
            if episode.script:
                import re
                broll_pattern = r'\[BROLL:\s*([^\]]+)\]'
                broll_matches = re.findall(broll_pattern, episode.script)
                for match in broll_matches:
                    if match and len(broll_prompts) < max_clips:
                        broll_prompts.append(match)

            if not broll_prompts:
                # Generate generic B-roll based on topic
                topic = episode.idea.get("topic") or episode.title or "abstract motion"
                broll_prompts = [
                    f"Cinematic establishing shot related to {topic}, 4K quality",
                    f"Abstract visualization representing {topic}, smooth motion",
                ]

            # Limit to max_clips
            broll_prompts = broll_prompts[:max_clips]

            # Initialize Runway client and storage
            runway = RunwayClient(settings=settings)
            storage = StorageClient(settings=settings)

            # Generate B-roll clips
            asset_ids = []
            total_cost = 0.0
            total_duration_ms = 0

            for i, prompt in enumerate(broll_prompts):
                logger.info(
                    f"Generating B-roll clip {i + 1}/{len(broll_prompts)} for episode {episode_id}",
                    extra={
                        "episode_id": episode_id,
                        "clip_index": i,
                        "prompt": prompt[:100],
                    },
                )

                # Generate video and save to S3
                result = runway.generate_video_and_save(
                    prompt=prompt,
                    episode_id=UUID(episode_id),
                    storage_client=storage,
                    duration=4,  # 4-second clips
                    asset_suffix=f"_{i + 1}" if i > 0 else "",
                )

                # Create asset record
                asset = create_asset_record(
                    db=db,
                    episode_id=episode_id,
                    asset_type=AssetType.B_ROLL,
                    uri=result.storage_result.uri,
                    storage_bucket=result.storage_result.bucket,
                    storage_key=result.storage_result.key,
                    provider="runway",
                    provider_job_id=result.generation_id,
                    mime_type=result.content_type,
                    file_size_bytes=result.file_size_bytes,
                    duration_ms=result.duration_ms,
                    metadata={
                        "generation_id": result.generation_id,
                        "prompt": prompt,
                        "thumbnail_url": result.thumbnail_url,
                        "clip_index": i,
                        "cost_usd": float(result.usage.estimated_cost_usd) if result.usage else 0,
                    },
                    is_primary=(i == 0),  # First clip is primary
                    name=f"B-Roll Clip {i + 1}",
                )

                asset_ids.append(str(asset.id))
                if result.usage:
                    total_cost += float(result.usage.estimated_cost_usd)
                if result.duration_ms:
                    total_duration_ms += result.duration_ms

                db.commit()

            # Update job with success
            update_job_status(
                db=db,
                job_id=job_id,
                status=JobStatus.COMPLETED,
                result={
                    "broll_generated": True,
                    "clips_count": len(asset_ids),
                    "total_duration_ms": total_duration_ms,
                    "asset_ids": asset_ids,
                },
                cost_usd=total_cost,
            )

            # Update pipeline state to completed
            update_episode_pipeline_state(
                db=db,
                episode_id=episode_id,
                stage=stage,
                status="completed",
                clips_count=len(asset_ids),
                total_duration_ms=total_duration_ms,
                cost_usd=total_cost,
            )

            db.commit()

            logger.info(
                f"B-roll stage completed for episode {episode_id}",
                extra={
                    "episode_id": episode_id,
                    "job_id": job_id,
                    "clips_count": len(asset_ids),
                    "total_cost": total_cost,
                },
            )

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=True,
                asset_ids=asset_ids,
                cost_usd=total_cost,
                duration_seconds=total_duration_ms / 1000.0 if total_duration_ms else None,
                clips_count=len(asset_ids),
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"B-roll stage failed for episode {episode_id}: {error_msg}",
                extra={"episode_id": episode_id, "error": error_msg},
                exc_info=True,
            )

            retry_policy = get_retry_policy(stage)
            if self.request.retries < retry_policy["max_retries"]:
                countdown = calculate_retry_countdown(stage, self.request.retries)
                update_episode_pipeline_state(
                    db, episode_id, stage, "running",
                    error=f"Retry {self.request.retries + 1}: {error_msg}",
                )
                db.commit()
                raise self.retry(countdown=countdown, exc=e)

            if job_id:
                update_job_status(db, job_id, JobStatus.FAILED, error_message=error_msg)
            update_episode_pipeline_state(db, episode_id, stage, "failed", error=error_msg)
            update_episode_status(db, episode_id, EpisodeStatus.FAILED, last_error=error_msg)
            db.commit()

            return format_task_result(
                stage=stage,
                episode_id=episode_id,
                job_id=job_id,
                success=False,
                error=error_msg,
            )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "run_planning_stage",
    "run_scripting_stage",
    "run_metadata_stage",
    "run_audio_stage",
    "run_avatar_stage",
    "run_broll_stage",
]
