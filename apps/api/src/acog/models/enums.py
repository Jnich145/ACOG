"""
Enum definitions for ACOG database models.

These enums define the valid values for status fields and type fields
throughout the application. They are used both in SQLAlchemy models
and Pydantic schemas for consistent validation.
"""

import enum


class EpisodeStatus(str, enum.Enum):
    """
    Episode lifecycle status values.

    Tracks the progression of an episode through the content pipeline.
    Aligned with API contracts v1.1.

    Attributes:
        IDEA: Initial concept captured, not yet planned
        PLANNING: OpenAI planner generating outline
        SCRIPTING: Script generation in progress
        SCRIPT_REVIEW: Script ready for human review
        AUDIO: Audio generation in progress (ElevenLabs)
        AVATAR: Avatar video generation in progress (HeyGen/Synthesia)
        BROLL: B-roll generation in progress (Runway/Pika)
        ASSEMBLY: Final video assembly in progress
        READY: All assets ready, awaiting publish
        PUBLISHING: Upload in progress
        PUBLISHED: Successfully published to platform
        FAILED: Pipeline failed (check pipeline_state for details)
        CANCELLED: Manually cancelled by user
    """

    IDEA = "idea"
    PLANNING = "planning"
    SCRIPTING = "scripting"
    SCRIPT_REVIEW = "script_review"
    AUDIO = "audio"
    AVATAR = "avatar"
    BROLL = "broll"
    ASSEMBLY = "assembly"
    READY = "ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStatus(str, enum.Enum):
    """
    Job execution status values.

    Tracks the state of async pipeline operations.

    Attributes:
        QUEUED: Job queued, waiting for worker
        RUNNING: Job currently executing
        COMPLETED: Job finished successfully
        FAILED: Job failed (check error_message)
        CANCELLED: Job was cancelled
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(str, enum.Enum):
    """
    Standardized pipeline stage names.

    Used in jobs.stage and pipeline_state keys for consistency.

    Attributes:
        PLANNING: Content planning and outline generation
        SCRIPTING: Script generation
        SCRIPT_REVIEW: Script QA and refinement
        METADATA: SEO metadata generation
        AUDIO: Voice synthesis (ElevenLabs)
        AVATAR: Avatar video generation (HeyGen/Synthesia)
        BROLL: B-roll generation (Runway/Pika)
        ASSEMBLY: Final video assembly
        UPLOAD: Upload to publishing platform
    """

    PLANNING = "planning"
    SCRIPTING = "scripting"
    SCRIPT_REVIEW = "script_review"
    METADATA = "metadata"
    AUDIO = "audio"
    AVATAR = "avatar"
    BROLL = "broll"
    ASSEMBLY = "assembly"
    UPLOAD = "upload"


class AssetType(str, enum.Enum):
    """
    Asset types produced during episode pipeline.

    Each type corresponds to a specific output from a pipeline stage.

    Attributes:
        SCRIPT: Final script document (text/markdown)
        AUDIO: Voice synthesis output (MP3/WAV)
        AVATAR_VIDEO: Talking head video segments
        B_ROLL: Generated or sourced B-roll clips
        ASSEMBLED_VIDEO: Final rendered video (MP4)
        THUMBNAIL: Video thumbnail image
        PLAN: Stored plan document
        METADATA: SEO metadata export
    """

    SCRIPT = "script"
    AUDIO = "audio"
    AVATAR_VIDEO = "avatar_video"
    B_ROLL = "b_roll"
    ASSEMBLED_VIDEO = "assembled_video"
    THUMBNAIL = "thumbnail"
    PLAN = "plan"
    METADATA = "metadata"


class IdeaSource(str, enum.Enum):
    """
    Source of episode ideas.

    Tracks how episode ideas originated for analytics and filtering.

    Attributes:
        MANUAL: User-entered topic
        PULSE: Auto-generated from PulseEvent
        SERIES: Generated as part of a series
        FOLLOWUP: Follow-up to previous episode
        REPURPOSE: Repurposed from existing content
    """

    MANUAL = "manual"
    PULSE = "pulse"
    SERIES = "series"
    FOLLOWUP = "followup"
    REPURPOSE = "repurpose"


class Priority(str, enum.Enum):
    """
    Episode production priority levels.

    Used to determine processing order in the pipeline queue.
    Maps to integer values for database storage:
        LOW = -1, NORMAL = 0, HIGH = 1, URGENT = 2

    Attributes:
        LOW: Low priority, process when idle
        NORMAL: Default priority level
        HIGH: High priority, process soon
        URGENT: Urgent, process immediately
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    def to_int(self) -> int:
        """Convert priority to integer for database storage."""
        priority_map = {
            Priority.LOW: -1,
            Priority.NORMAL: 0,
            Priority.HIGH: 1,
            Priority.URGENT: 2,
        }
        return priority_map[self]

    @classmethod
    def from_int(cls, value: int) -> "Priority":
        """Convert integer to priority enum."""
        int_map = {
            -1: Priority.LOW,
            0: Priority.NORMAL,
            1: Priority.HIGH,
            2: Priority.URGENT,
        }
        return int_map.get(value, Priority.NORMAL)
