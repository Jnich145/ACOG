"""
Celery workers for ACOG async episode production pipeline.

This module provides the Celery infrastructure and tasks for:
- Episode planning (OpenAI-driven content planning)
- Script generation (OpenAI-generated scripts)
- Metadata extraction (SEO titles, descriptions, tags)
- Voice synthesis (ElevenLabs integration)
- Avatar video generation (HeyGen)
- B-roll generation (Runway)
- Pipeline orchestration (chained task execution)

All tasks are designed to be idempotent and support retry with exponential backoff.
"""

from acog.workers.celery_app import celery_app
from acog.workers.tasks import (
    run_audio_stage,
    run_avatar_stage,
    run_broll_stage,
    run_full_pipeline,
    run_metadata_stage,
    run_pipeline_from_stage,
    run_planning_stage,
    run_scripting_stage,
)
from acog.workers.utils import (
    create_asset_record,
    get_db_session,
    update_episode_pipeline_state,
    update_episode_status,
    update_job_status,
)

__all__ = [
    # Celery app
    "celery_app",
    # Pipeline stage tasks
    "run_planning_stage",
    "run_scripting_stage",
    "run_metadata_stage",
    "run_audio_stage",
    "run_avatar_stage",
    "run_broll_stage",
    # Pipeline orchestration
    "run_full_pipeline",
    "run_pipeline_from_stage",
    # Utilities
    "get_db_session",
    "update_job_status",
    "update_episode_pipeline_state",
    "update_episode_status",
    "create_asset_record",
]
