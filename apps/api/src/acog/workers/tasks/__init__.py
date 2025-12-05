"""
Celery tasks for ACOG episode production pipeline.

This module exports all pipeline stage tasks and orchestration tasks:

Pipeline Stage Tasks:
- run_planning_stage: Generate episode plan using OpenAI
- run_scripting_stage: Generate script from plan
- run_metadata_stage: Generate video metadata (titles, descriptions, tags)
- run_audio_stage: Generate audio using ElevenLabs
- run_avatar_stage: Generate avatar video using HeyGen
- run_broll_stage: Generate B-roll clips using Runway

Orchestration Tasks:
- run_full_pipeline: Execute complete pipeline from start
- run_pipeline_from_stage: Resume pipeline from a specific stage
"""

from acog.workers.tasks.orchestrator import (
    run_full_pipeline,
    run_pipeline_from_stage,
)
from acog.workers.tasks.pipeline import (
    run_audio_stage,
    run_avatar_stage,
    run_broll_stage,
    run_metadata_stage,
    run_planning_stage,
    run_scripting_stage,
)

__all__ = [
    # Pipeline stage tasks
    "run_planning_stage",
    "run_scripting_stage",
    "run_metadata_stage",
    "run_audio_stage",
    "run_avatar_stage",
    "run_broll_stage",
    # Orchestration tasks
    "run_full_pipeline",
    "run_pipeline_from_stage",
]
