"""
Pydantic schemas for Episode endpoints.

Defines request and response schemas for episode CRUD operations
and pipeline state management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acog.models.enums import EpisodeStatus, IdeaSource, Priority
from acog.schemas.common import ApiResponse, PaginationMeta


class StageStatus(BaseModel):
    """
    Status of an individual pipeline stage.

    Attributes:
        status: Current stage status
        started_at: When the stage started
        completed_at: When the stage completed
        duration_seconds: Total duration in seconds
        error: Error message if failed
        retry_count: Number of retry attempts
        output_ref: Reference to stage output
    """

    status: str = Field(
        default="pending",
        description="Stage status: pending, queued, processing, completed, failed, skipped",
    )
    started_at: datetime | None = Field(
        default=None,
        description="When the stage started",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When the stage completed",
    )
    duration_seconds: float | None = Field(
        default=None,
        description="Total duration in seconds",
    )
    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts",
    )
    output_ref: str | None = Field(
        default=None,
        description="Reference to stage output (asset ID or S3 path)",
    )


class PipelineState(BaseModel):
    """
    Complete pipeline state for an episode.

    Tracks the status of all pipeline stages.

    Attributes:
        current_stage: Current active stage
        overall_status: Overall pipeline status
        stages: Status of each individual stage
    """

    current_stage: str = Field(
        default="idea",
        description="Current pipeline stage",
    )
    overall_status: str = Field(
        default="pending",
        description="Overall status: pending, in_progress, completed, failed, cancelled",
    )
    stages: dict[str, StageStatus] = Field(
        default_factory=dict,
        description="Status of each pipeline stage",
    )

    @classmethod
    def create_default(cls) -> "PipelineState":
        """Create a default pipeline state with all stages pending."""
        stage_names = [
            "planning",
            "scripting",
            "script_review",
            "metadata",
            "audio",
            "avatar",
            "broll",
            "assembly",
            "upload",
        ]
        stages = {name: StageStatus() for name in stage_names}
        return cls(
            current_stage="idea",
            overall_status="pending",
            stages=stages,
        )


class SeriesInfo(BaseModel):
    """Series information for episodes that are part of a series."""

    series_id: UUID = Field(description="Series identifier")
    sequence_number: int = Field(ge=1, description="Position in the series")


class CostTracking(BaseModel):
    """Cost tracking information for an episode."""

    estimated_cost_usd: float | None = Field(
        default=None,
        description="Estimated total cost in USD",
    )
    actual_cost_usd: float = Field(
        default=0.0,
        description="Actual cost incurred so far",
    )
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by stage/provider",
    )


class EpisodeCreate(BaseModel):
    """
    Schema for creating a new episode.

    Attributes:
        title: Working title for the episode
        idea_brief: Initial idea description and context
        idea_source: How the episode idea originated
        pulse_event_id: Reference to PulseEvent if source is 'pulse'
        series_info: Series information if part of a series
        target_length_minutes: Target video length
        priority: Production priority
        tags: Tags for categorization
        notes: Internal production notes
        auto_advance: Automatically advance through pipeline
    """

    title: str = Field(
        min_length=1,
        max_length=200,
        description="Working title for the episode",
    )
    idea_brief: str | None = Field(
        default=None,
        max_length=5000,
        description="Initial idea description and context",
    )
    idea_source: IdeaSource = Field(
        default=IdeaSource.MANUAL,
        description="How the episode idea originated",
    )
    pulse_event_id: UUID | None = Field(
        default=None,
        description="Reference to PulseEvent if source is 'pulse'",
    )
    series_info: SeriesInfo | None = Field(
        default=None,
        description="Series information if part of a series",
    )
    target_length_minutes: int | None = Field(
        default=None,
        ge=1,
        le=120,
        description="Target video length in minutes",
    )
    priority: Priority = Field(
        default=Priority.NORMAL,
        description="Production priority: low, normal, high, urgent",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Tags for categorization and search",
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Internal notes for production",
    )
    auto_advance: bool = Field(
        default=False,
        description="Automatically advance through pipeline stages",
    )


class EpisodeUpdate(BaseModel):
    """
    Schema for updating an existing episode.

    All fields are optional - only provided fields are updated.
    """

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    idea_brief: str | None = Field(
        default=None,
        max_length=5000,
    )
    target_length_minutes: int | None = Field(
        default=None,
        ge=1,
        le=120,
    )
    priority: Priority | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    notes: str | None = Field(default=None)
    status: EpisodeStatus | None = Field(default=None)


class ScriptSegment(BaseModel):
    """A segment of the episode script."""

    type: str = Field(description="Segment type: avatar, voiceover, broll")
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds")
    text: str = Field(description="Segment text content")
    tone: str | None = Field(default=None, description="Tone guidance")
    notes: str | None = Field(default=None, description="Production notes")
    broll_cue: str | None = Field(default=None, description="B-roll cue if applicable")


class ScriptContent(BaseModel):
    """Full script content with metadata."""

    version: int = Field(default=1, description="Script version number")
    status: str = Field(default="draft", description="Script status")
    full_text: str | None = Field(default=None, description="Complete script text")
    segments: list[ScriptSegment] = Field(
        default_factory=list,
        description="Script segments",
    )
    word_count: int = Field(default=0, description="Total word count")
    estimated_duration_seconds: float = Field(
        default=0,
        description="Estimated duration",
    )
    generated_at: datetime | None = Field(default=None, description="Generation timestamp")
    model_used: str | None = Field(default=None, description="LLM model used")


class EpisodeResponse(BaseModel):
    """
    Schema for episode response data.

    Includes all episode fields plus computed properties.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Episode unique identifier")
    channel_id: UUID = Field(description="Parent channel identifier")
    title: str | None = Field(description="Working title")
    slug: str | None = Field(description="URL-friendly identifier")
    idea_brief: str | None = Field(description="Initial idea description")
    idea_source: IdeaSource = Field(description="Idea origin")
    pulse_event_id: UUID | None = Field(description="Related PulseEvent ID")
    series_info: SeriesInfo | None = Field(default=None, description="Series information")
    status: EpisodeStatus = Field(description="Current pipeline status")
    target_length_minutes: int | None = Field(description="Target video length")
    priority: Priority = Field(default=Priority.NORMAL, description="Production priority")
    tags: list[str] = Field(default_factory=list, description="Episode tags")
    notes: str | None = Field(description="Production notes")
    auto_advance: bool = Field(default=False, description="Auto-advance enabled")

    # Content fields
    plan: dict[str, Any] | None = Field(default=None, description="Episode plan")
    script: ScriptContent | None = Field(default=None, description="Episode script")
    metadata: dict[str, Any] | None = Field(default=None, description="SEO metadata")

    # Pipeline state
    pipeline_state: PipelineState | None = Field(
        default=None,
        description="Pipeline execution state",
    )

    # Cost tracking
    cost_tracking: CostTracking | None = Field(
        default=None,
        description="Cost information",
    )

    # Asset summary
    asset_count: int = Field(default=0, description="Number of assets")
    assets: list[Any] = Field(default_factory=list, description="Associated assets")

    # Publishing
    published_url: str | None = Field(description="Published video URL")
    published_at: datetime | None = Field(description="Publication timestamp")

    # Timestamps
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    deleted_at: datetime | None = Field(description="Deletion timestamp")

    @classmethod
    def from_model(
        cls,
        episode: Any,
        include_plan: bool = True,
        include_script: bool = True,
        include_assets: bool = True,
    ) -> "EpisodeResponse":
        """
        Create response from episode model with optional field inclusion.

        Args:
            episode: Episode model instance
            include_plan: Include full plan JSON
            include_script: Include full script content
            include_assets: Include asset list

        Returns:
            EpisodeResponse instance
        """
        # Extract idea_brief from idea JSONB
        idea_brief = episode.idea.get("brief") if episode.idea else None

        # Build pipeline state
        pipeline_state = None
        if episode.pipeline_state:
            stages = {
                k: StageStatus(**v) if isinstance(v, dict) else StageStatus()
                for k, v in episode.pipeline_state.items()
                if k not in ["current_stage", "overall_status"]
            }
            pipeline_state = PipelineState(
                current_stage=episode.status.value,
                overall_status="in_progress"
                if episode.status not in [EpisodeStatus.PUBLISHED, EpisodeStatus.FAILED, EpisodeStatus.CANCELLED]
                else episode.status.value,
                stages=stages,
            )

        return cls(
            id=episode.id,
            channel_id=episode.channel_id,
            title=episode.title,
            slug=episode.slug,
            idea_brief=idea_brief,
            idea_source=episode.idea_source,
            pulse_event_id=episode.pulse_event_id,
            status=episode.status,
            target_length_minutes=episode.idea.get("target_length_minutes"),
            priority=Priority.from_int(episode.priority),
            tags=episode.idea.get("tags", []),
            notes=episode.idea.get("notes"),
            auto_advance=episode.idea.get("auto_advance", False),
            plan=episode.plan if include_plan else None,
            script=None,  # Would need to parse from episode.script
            metadata=episode.episode_meta,
            pipeline_state=pipeline_state,
            asset_count=episode.asset_count if hasattr(episode, "asset_count") else 0,
            assets=[],  # Would populate if include_assets
            published_url=episode.published_url,
            published_at=episode.published_at,
            created_at=episode.created_at,
            updated_at=episode.updated_at,
            deleted_at=episode.deleted_at,
        )


class EpisodeListResponse(ApiResponse[list[EpisodeResponse]]):
    """Response schema for episode list endpoint."""

    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        episodes: list[EpisodeResponse],
        pagination: PaginationMeta,
        filters_applied: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> "EpisodeListResponse":
        """Create an episode list response with pagination."""
        meta: dict[str, Any] = {"pagination": pagination.model_dump()}
        if filters_applied:
            meta["filters_applied"] = filters_applied
        if request_id:
            meta["request_id"] = request_id
        return cls(data=episodes, meta=meta)
