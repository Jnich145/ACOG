"""
Episode model for content units flowing through the pipeline.

Episodes are the core content units that progress through defined
stages from idea to published video.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from acog.models.base import Base, TimestampMixin
from acog.models.enums import EpisodeStatus, IdeaSource

if TYPE_CHECKING:
    from acog.models.asset import Asset
    from acog.models.channel import Channel
    from acog.models.job import Job


class Episode(Base, TimestampMixin):
    """
    Episode model representing a content unit in the production pipeline.

    Each episode belongs to a channel and progresses through defined stages:
    idea -> planning -> scripting -> script_review -> audio -> avatar ->
    broll -> assembly -> ready -> publishing -> published

    Attributes:
        id: Unique identifier (UUID)
        channel_id: Parent channel reference
        pulse_event_id: Optional link to triggering PulseEvent
        title: Working title (may change during pipeline)
        slug: URL-friendly identifier within channel
        status: Current pipeline status
        idea_source: How the episode idea originated
        idea: Original idea/topic brief (JSON)
        plan: Structured outline from planner (JSON)
        script: Full script content
        script_metadata: Script version, word count, etc. (JSON)
        metadata: Title, description, tags, SEO (JSON)
        pipeline_state: Per-stage status, timestamps, errors (JSON)
        published_url: URL where episode was published
        published_at: Timestamp of publication
        priority: Higher = process sooner
        retry_count: Number of retry attempts
        last_error: Last error message
    """

    __tablename__ = "episodes"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    channel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pulse_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="Optional link to triggering PulseEvent",
    )

    # Content identification
    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Working title (may change during pipeline)",
    )
    slug: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="URL-friendly identifier within channel",
    )

    # Pipeline status
    status: Mapped[EpisodeStatus] = mapped_column(
        Enum(
            EpisodeStatus,
            name="episode_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=EpisodeStatus.IDEA,
        index=True,
    )
    idea_source: Mapped[IdeaSource] = mapped_column(
        Enum(
            IdeaSource,
            name="idea_source",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=IdeaSource.MANUAL,
    )

    # Content data (JSONB for complex nested structures)
    idea: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: topic, brief, target_audience, key_points, source_context",
    )
    plan: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: hook, intro, sections[], key_facts[], ctas[], broll_suggestions[]",
    )
    script: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Full script text with markers: [AVATAR], [VOICEOVER], [BROLL:desc]",
    )
    script_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: version, word_count, estimated_duration, etc.",
    )
    episode_meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata",  # Column name in database
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: final_title, description, tags[], thumbnail_prompt, social_copy",
    )

    # Pipeline execution state
    pipeline_state: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: {stage: {status, started_at, completed_at, error, attempts}}",
    )

    # Publishing information
    published_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Execution tracking
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        doc="Higher = process sooner",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    channel: Mapped["Channel"] = relationship(
        "Channel",
        back_populates="episodes",
    )
    assets: Mapped[list["Asset"]] = relationship(
        "Asset",
        back_populates="episode",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="episode",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        """Return string representation of the episode."""
        return f"<Episode {self.id} [{self.status.value}]>"

    def update_pipeline_stage(
        self,
        stage: str,
        status: str,
        error: str | None = None,
        **extra: Any,
    ) -> None:
        """
        Update a specific pipeline stage status.

        Automatically manages timestamps for stage transitions.

        Args:
            stage: Pipeline stage name (planning, scripting, etc.)
            status: New status (pending, running, completed, failed)
            error: Error message if status is 'failed'
            **extra: Additional fields to store (tokens_used, model_used, etc.)
        """
        if stage not in self.pipeline_state:
            self.pipeline_state[stage] = {}

        stage_data = self.pipeline_state[stage]
        stage_data["status"] = status
        stage_data["updated_at"] = datetime.now(UTC).isoformat()

        if status == "running" and "started_at" not in stage_data:
            stage_data["started_at"] = datetime.now(UTC).isoformat()
            stage_data["attempts"] = stage_data.get("attempts", 0) + 1
        elif status == "completed":
            stage_data["completed_at"] = datetime.now(UTC).isoformat()
            stage_data["error"] = None
        elif status == "failed" and error:
            stage_data["error"] = error

        for key, value in extra.items():
            stage_data[key] = value

        # Mark the JSONB column as modified for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(self, "pipeline_state")

    def get_stage_status(self, stage: str) -> str:
        """
        Get the status of a pipeline stage.

        Args:
            stage: Pipeline stage name

        Returns:
            Status string ('pending', 'running', 'completed', 'failed')
        """
        return self.pipeline_state.get(stage, {}).get("status", "pending")

    def is_stage_complete(self, stage: str) -> bool:
        """Check if a pipeline stage is complete."""
        return self.get_stage_status(stage) == "completed"

    def can_advance_to(self, target_status: EpisodeStatus) -> bool:
        """
        Check if the episode can advance to a target status.

        Validates that required stages are complete before advancing.

        Args:
            target_status: Target status to check

        Returns:
            True if advancement is allowed, False otherwise
        """
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
            EpisodeStatus.PUBLISHING,
            EpisodeStatus.PUBLISHED,
        ]

        try:
            current_idx = stage_order.index(self.status)
            target_idx = stage_order.index(target_status)
            # Can only advance to next stage or same stage
            return target_idx <= current_idx + 1
        except ValueError:
            # Status not in normal flow (FAILED, CANCELLED)
            return False

    @property
    def asset_count(self) -> int:
        """Get the count of non-deleted assets."""
        from acog.models.asset import Asset

        return (
            self.assets.filter(Asset.deleted_at.is_(None))  # type: ignore[union-attr]
            .count()
        )

    @property
    def active_job_count(self) -> int:
        """Get the count of active (queued or running) jobs."""
        from acog.models.enums import JobStatus
        from acog.models.job import Job

        return (
            self.jobs.filter(  # type: ignore[union-attr]
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
            )
            .count()
        )
