"""
Job model for async pipeline operations.

Jobs track the execution of individual pipeline stages,
providing status, timing, and result information.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from acog.models.base import Base
from acog.models.enums import JobStatus

if TYPE_CHECKING:
    from acog.models.episode import Episode


class Job(Base):
    """
    Job model tracking async pipeline operations.

    Each job represents a single stage execution for an episode.
    Jobs are created when pipeline stages are triggered via API
    and executed by Celery workers.

    Note: Jobs do not use soft delete (no deleted_at) as they are
    execution records, not user content.

    Attributes:
        id: Unique identifier (UUID)
        episode_id: Parent episode reference
        stage: Pipeline stage (planning, scripting, audio, etc.)
        status: Job execution status
        celery_task_id: Celery task ID for tracking/revocation
        input_params: Parameters passed to the job
        result: Job output/result data
        error_message: Error details if failed
        started_at: When execution started
        completed_at: When execution completed
        retry_count: Number of retry attempts
        max_retries: Maximum allowed retries
        cost_usd: Cost incurred by this job
        tokens_used: Total tokens used (for LLM jobs)
    """

    __tablename__ = "jobs"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key
    episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Job identification
    stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Pipeline stage: planning, scripting, audio, avatar, broll, assembly, etc.",
    )

    # Status tracking
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=JobStatus.QUEUED,
        index=True,
    )

    # Celery integration
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Celery task ID for monitoring and revocation",
    )

    # Execution details
    input_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: stage-specific input parameters",
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="JSON: stage-specific output data",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # Cost tracking
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )
    tokens_used: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Timestamps (no soft delete for jobs)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    episode: Mapped["Episode"] = relationship(
        "Episode",
        back_populates="jobs",
    )

    def __repr__(self) -> str:
        """Return string representation of the job."""
        return f"<Job {self.id} [{self.stage}:{self.status.value}]>"

    def start(self) -> None:
        """
        Mark job as running.

        Sets status to RUNNING and records start time.
        """
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now(UTC)

    def complete(self, result: dict[str, Any] | None = None) -> None:
        """
        Mark job as completed with optional result.

        Args:
            result: Optional result data to store
        """
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        if result is not None:
            self.result = result

    def fail(self, error_message: str) -> None:
        """
        Mark job as failed with error message.

        Args:
            error_message: Description of the failure
        """
        self.status = JobStatus.FAILED
        self.completed_at = datetime.now(UTC)
        self.error_message = error_message

    def cancel(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.now(UTC)

    def retry(self) -> bool:
        """
        Attempt to retry the job.

        Increments retry count and resets status to QUEUED.

        Returns:
            True if retry was allowed, False if max retries exceeded
        """
        if not self.can_retry:
            return False

        self.retry_count += 1
        self.status = JobStatus.QUEUED
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        return True

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return (
            self.retry_count < self.max_retries
            and self.status == JobStatus.FAILED
        )

    @property
    def duration_seconds(self) -> float | None:
        """
        Calculate job duration in seconds.

        Returns:
            Duration in seconds if job has completed, None otherwise
        """
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_active(self) -> bool:
        """Check if job is currently active (queued or running)."""
        return self.status in [JobStatus.QUEUED, JobStatus.RUNNING]

    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ]

    def set_cost(self, cost_usd: float, tokens: int | None = None) -> None:
        """
        Set cost information for the job.

        Args:
            cost_usd: Cost in USD
            tokens: Number of tokens used (for LLM jobs)
        """
        self.cost_usd = Decimal(str(cost_usd))
        if tokens is not None:
            self.tokens_used = tokens
