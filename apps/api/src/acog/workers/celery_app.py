"""
Celery application configuration for ACOG.

This module configures the Celery app with:
- Redis broker and result backend
- Task routing for different queues
- Retry policies with exponential backoff
- Serialization settings
- Beat scheduler configuration (for future scheduled tasks)
"""

import logging
from typing import Any

from celery import Celery

from acog.core.config import get_settings

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# =============================================================================
# Celery Application Configuration
# =============================================================================

celery_app = Celery(
    "acog_workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "acog.workers.tasks.pipeline",
        "acog.workers.tasks.orchestrator",
    ],
)

# =============================================================================
# Task Serialization Settings
# =============================================================================

celery_app.conf.update(
    # Use JSON for serialization (more secure than pickle)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone configuration
    timezone="UTC",
    enable_utc=True,
)

# =============================================================================
# Task Execution Settings
# =============================================================================

celery_app.conf.update(
    # Acknowledge tasks late (after execution) for reliability
    # If worker crashes, task will be re-delivered to another worker
    task_acks_late=True,
    # Reject tasks when worker shuts down, so they get re-queued
    task_reject_on_worker_lost=True,
    # Only prefetch one task at a time for long-running tasks
    worker_prefetch_multiplier=1,
    # Default task timeout (10 minutes)
    task_time_limit=600,
    # Soft time limit - raises SoftTimeLimitExceeded before hard timeout
    task_soft_time_limit=540,
    # Track task start time
    task_track_started=True,
    # Send task-sent events for monitoring
    task_send_sent_event=True,
)

# =============================================================================
# Retry Policy Configuration
# =============================================================================

# Default retry settings for all tasks
DEFAULT_RETRY_POLICY: dict[str, Any] = {
    "max_retries": 3,
    "interval_start": 10,  # Initial retry delay (seconds)
    "interval_step": 30,   # Increase retry delay each attempt
    "interval_max": 300,   # Maximum retry delay (5 minutes)
}

# Stage-specific retry policies
RETRY_POLICIES: dict[str, dict[str, Any]] = {
    "planning": {
        "max_retries": 3,
        "interval_start": 10,
        "interval_step": 20,
        "interval_max": 120,
    },
    "scripting": {
        "max_retries": 3,
        "interval_start": 10,
        "interval_step": 20,
        "interval_max": 120,
    },
    "metadata": {
        "max_retries": 3,
        "interval_start": 5,
        "interval_step": 15,
        "interval_max": 60,
    },
    "audio": {
        "max_retries": 5,  # More retries for external services
        "interval_start": 15,
        "interval_step": 30,
        "interval_max": 300,
    },
    "avatar": {
        "max_retries": 3,
        "interval_start": 30,  # Longer initial delay
        "interval_step": 60,
        "interval_max": 600,  # Can take up to 10 minutes
    },
    "broll": {
        "max_retries": 5,
        "interval_start": 15,
        "interval_step": 30,
        "interval_max": 300,
    },
}

celery_app.conf.task_default_retry_delay = DEFAULT_RETRY_POLICY["interval_start"]

# =============================================================================
# Task Routing Configuration
# =============================================================================

# Route tasks to specific queues based on their resource requirements
celery_app.conf.task_routes = {
    # OpenAI-based tasks (moderate resources, fast)
    "acog.workers.tasks.pipeline.run_planning_stage": {"queue": "openai"},
    "acog.workers.tasks.pipeline.run_scripting_stage": {"queue": "openai"},
    "acog.workers.tasks.pipeline.run_metadata_stage": {"queue": "openai"},
    # External media service tasks (longer running, may need more retries)
    "acog.workers.tasks.pipeline.run_audio_stage": {"queue": "media"},
    "acog.workers.tasks.pipeline.run_avatar_stage": {"queue": "media"},
    "acog.workers.tasks.pipeline.run_broll_stage": {"queue": "media"},
    # Orchestration tasks
    "acog.workers.tasks.orchestrator.run_full_pipeline": {"queue": "orchestrator"},
    "acog.workers.tasks.orchestrator.run_pipeline_from_stage": {
        "queue": "orchestrator"
    },
    "acog.workers.tasks.orchestrator.run_stage_1_pipeline": {
        "queue": "orchestrator"
    },
}

# Define queue configurations
celery_app.conf.task_queues = {
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
    "openai": {
        "exchange": "openai",
        "routing_key": "openai",
    },
    "media": {
        "exchange": "media",
        "routing_key": "media",
    },
    "orchestrator": {
        "exchange": "orchestrator",
        "routing_key": "orchestrator",
    },
}

celery_app.conf.task_default_queue = "default"

# =============================================================================
# Result Backend Settings
# =============================================================================

celery_app.conf.update(
    # Keep task results for 24 hours
    result_expires=86400,
    # Extend result format with additional metadata
    result_extended=True,
)

# =============================================================================
# Logging Configuration
# =============================================================================

celery_app.conf.update(
    # Log format for Celery workers
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format=(
        "[%(asctime)s: %(levelname)s/%(processName)s] "
        "[%(task_name)s(%(task_id)s)] %(message)s"
    ),
)

# =============================================================================
# Celery Beat Configuration (for scheduled tasks)
# =============================================================================

# Beat schedule for periodic tasks (currently empty, can be extended)
celery_app.conf.beat_schedule = {}

# =============================================================================
# Task Base Class Configuration
# =============================================================================


def get_retry_policy(stage: str) -> dict[str, Any]:
    """
    Get retry policy for a specific pipeline stage.

    Args:
        stage: Pipeline stage name (planning, scripting, audio, etc.)

    Returns:
        Dictionary with retry configuration
    """
    return RETRY_POLICIES.get(stage, DEFAULT_RETRY_POLICY)


def calculate_retry_countdown(
    stage: str,
    retry_count: int,
) -> int:
    """
    Calculate the countdown for the next retry using exponential backoff.

    Args:
        stage: Pipeline stage name
        retry_count: Current retry attempt number (0-based)

    Returns:
        Number of seconds to wait before retry
    """
    policy = get_retry_policy(stage)
    countdown = policy["interval_start"] + (retry_count * policy["interval_step"])
    return min(countdown, policy["interval_max"])


# Export configuration utilities
__all__ = [
    "celery_app",
    "get_retry_policy",
    "calculate_retry_countdown",
    "DEFAULT_RETRY_POLICY",
    "RETRY_POLICIES",
]
