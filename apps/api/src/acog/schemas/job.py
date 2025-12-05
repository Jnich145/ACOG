"""
Pydantic schemas for Job endpoints.

Defines request and response schemas for job status and management.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acog.models.enums import JobStatus, PipelineStage
from acog.schemas.common import ApiResponse, PaginationMeta


class JobProgress(BaseModel):
    """
    Progress information for long-running jobs.

    Attributes:
        percent: Completion percentage (0-100)
        current_step: Current step description
        steps_completed: Number of completed steps
        steps_total: Total number of steps
    """

    percent: int = Field(
        ge=0,
        le=100,
        description="Completion percentage",
    )
    current_step: str | None = Field(
        default=None,
        description="Current step description",
    )
    steps_completed: int = Field(
        default=0,
        ge=0,
        description="Number of completed steps",
    )
    steps_total: int = Field(
        default=0,
        ge=0,
        description="Total number of steps",
    )


class JobCreate(BaseModel):
    """
    Schema for creating a new job.

    Jobs are typically created internally when triggering pipeline stages.

    Attributes:
        episode_id: Episode to process
        stage: Pipeline stage to execute
        params: Stage-specific parameters
        max_retries: Maximum retry attempts
    """

    episode_id: UUID = Field(description="Episode to process")
    stage: PipelineStage = Field(description="Pipeline stage to execute")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Stage-specific parameters",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts",
    )


class JobResponse(BaseModel):
    """
    Schema for job response data.

    Attributes:
        id: Job unique identifier
        episode_id: Associated episode identifier
        stage: Pipeline stage
        status: Current job status
        progress: Progress information for running jobs
        worker_id: ID of processing worker
        params: Parameters passed to the job
        result: Job result on completion
        error_message: Error message if failed
        retry_count: Number of retry attempts
        max_retries: Maximum allowed retries
        cost_usd: Cost incurred
        tokens_used: Tokens used (for LLM jobs)
        queued_at: When job was queued
        started_at: When processing started
        completed_at: When job completed
        duration_seconds: Total duration
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Job unique identifier")
    episode_id: UUID = Field(description="Associated episode identifier")
    stage: str = Field(description="Pipeline stage")
    status: JobStatus = Field(description="Current job status")
    progress: JobProgress | None = Field(
        default=None,
        description="Progress information",
    )
    worker_id: str | None = Field(
        default=None,
        description="ID of processing worker",
    )
    celery_task_id: str | None = Field(
        default=None,
        description="Celery task ID",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters passed to the job",
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description="Job result on completion",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if failed",
    )
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum allowed retries",
    )
    cost_usd: Decimal | None = Field(
        default=None,
        description="Cost incurred in USD",
    )
    tokens_used: int | None = Field(
        default=None,
        description="Tokens used (for LLM jobs)",
    )
    queued_at: datetime = Field(description="When job was queued")
    started_at: datetime | None = Field(
        default=None,
        description="When processing started",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When job completed",
    )
    duration_seconds: float | None = Field(
        default=None,
        description="Total duration in seconds",
    )
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    @classmethod
    def from_model(cls, job: Any) -> "JobResponse":
        """Create response from job model."""
        return cls(
            id=job.id,
            episode_id=job.episode_id,
            stage=job.stage,
            status=job.status,
            celery_task_id=job.celery_task_id,
            params=job.input_params,
            result=job.result,
            error_message=job.error_message,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            cost_usd=job.cost_usd,
            tokens_used=job.tokens_used,
            queued_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class JobListResponse(ApiResponse[list[JobResponse]]):
    """Response schema for job list endpoint."""

    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        jobs: list[JobResponse],
        pagination: PaginationMeta | None = None,
        request_id: str | None = None,
    ) -> "JobListResponse":
        """Create a job list response."""
        meta: dict[str, Any] = {}
        if pagination:
            meta["pagination"] = pagination.model_dump()
        if request_id:
            meta["request_id"] = request_id
        return cls(data=jobs, meta=meta)


class PipelineTriggerRequest(BaseModel):
    """
    Schema for triggering a pipeline stage.

    Attributes:
        stage: Stage to trigger
        params: Stage-specific parameters
        force: Force re-execution even if already completed
    """

    stage: PipelineStage = Field(description="Pipeline stage to trigger")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Stage-specific parameters",
    )
    force: bool = Field(
        default=False,
        description="Force re-execution even if completed",
    )


class PipelineTriggerResponse(BaseModel):
    """
    Response schema for pipeline trigger.

    Attributes:
        job_id: ID of created job
        episode_id: Episode being processed
        stage: Triggered stage
        status: Initial job status
        message: Status message
    """

    job_id: UUID = Field(description="ID of created job")
    episode_id: UUID = Field(description="Episode being processed")
    stage: str = Field(description="Triggered stage")
    status: str = Field(description="Initial job status")
    message: str = Field(description="Status message")
