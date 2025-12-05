"""
Pydantic schemas for Channel endpoints.

Defines request and response schemas for channel CRUD operations
including nested schemas for persona, style guide, and media profiles.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from acog.schemas.common import ApiResponse, PaginationMeta


class Persona(BaseModel):
    """
    Channel persona configuration schema.

    Defines the AI personality characteristics for content generation.

    Attributes:
        name: Display name for the persona
        background: Character background and expertise
        voice: Description of speaking style and tone
        values: Core values that guide content
        expertise: Areas of expertise
    """

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Display name for the persona",
    )
    background: str = Field(
        max_length=2000,
        description="Character background and expertise",
    )
    voice: str | None = Field(
        default=None,
        max_length=500,
        description="Description of speaking style and tone",
    )
    values: list[str] = Field(
        default_factory=list,
        description="Core values that guide content",
    )
    expertise: list[str] = Field(
        default_factory=list,
        description="Areas of expertise",
    )


class VideoLengthTarget(BaseModel):
    """Video length target configuration."""

    min_minutes: int = Field(ge=1, default=8, description="Minimum video length")
    max_minutes: int = Field(le=120, default=15, description="Maximum video length")


class StyleGuide(BaseModel):
    """
    Channel style guide configuration schema.

    Defines content style preferences for generation.

    Attributes:
        tone: Overall tone of content
        complexity: Target audience complexity level
        pacing: Content delivery speed
        humor_level: Amount of humor to include
        video_length_target: Target video duration range
        do_rules: Things the content SHOULD do
        dont_rules: Things the content should AVOID
    """

    tone: str | None = Field(
        default="conversational",
        description="Overall tone: formal, conversational, casual, academic, enthusiastic",
    )
    complexity: str | None = Field(
        default="intermediate",
        description="Complexity level: beginner, intermediate, advanced, expert",
    )
    pacing: str | None = Field(
        default="moderate",
        description="Content pacing: slow, moderate, fast",
    )
    humor_level: str | None = Field(
        default="light",
        description="Humor level: none, light, moderate, heavy",
    )
    video_length_target: VideoLengthTarget | None = Field(
        default=None,
        description="Target video duration range",
    )
    do_rules: list[str] = Field(
        default_factory=list,
        description="Things the content SHOULD do",
    )
    dont_rules: list[str] = Field(
        default_factory=list,
        description="Things the content should AVOID",
    )


class VoiceProfile(BaseModel):
    """
    Voice synthesis configuration schema.

    Configures voice generation provider settings.

    Attributes:
        provider: Voice synthesis provider (elevenlabs, amazon_polly, google_tts)
        voice_id: Provider-specific voice identifier
        stability: Voice stability setting
        similarity_boost: Similarity boost setting
        style: Style exaggeration setting
    """

    provider: str = Field(
        default="elevenlabs",
        description="Voice provider: elevenlabs, amazon_polly, google_tts",
    )
    voice_id: str | None = Field(
        default=None,
        description="Provider-specific voice identifier",
    )
    stability: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Voice stability (0-1)",
    )
    similarity_boost: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Similarity boost (0-1)",
    )
    style: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Style exaggeration (0-1)",
    )


class AvatarProfile(BaseModel):
    """
    Avatar video configuration schema.

    Configures avatar generation provider settings.

    Attributes:
        provider: Avatar video provider (heygen, synthesia, d-id)
        avatar_id: Provider-specific avatar identifier
        background: Background setting or scene
        framing: Camera framing preference
        attire: Avatar clothing/appearance setting
    """

    provider: str = Field(
        default="heygen",
        description="Avatar provider: heygen, synthesia, d-id",
    )
    avatar_id: str | None = Field(
        default=None,
        description="Provider-specific avatar identifier",
    )
    background: str | None = Field(
        default=None,
        description="Background setting or scene",
    )
    framing: str = Field(
        default="medium",
        description="Camera framing: closeup, medium, wide",
    )
    attire: str | None = Field(
        default=None,
        description="Avatar clothing/appearance setting",
    )


class Cadence(BaseModel):
    """Publishing cadence configuration."""

    videos_per_week: int = Field(
        default=3,
        ge=1,
        le=21,
        description="Target videos per week",
    )
    preferred_days: list[str] = Field(
        default_factory=list,
        description="Preferred publishing days",
    )


class ChannelCreate(BaseModel):
    """
    Schema for creating a new channel.

    Attributes:
        name: Channel display name
        description: Channel description
        niche: Content niche/category
        persona: AI persona configuration (required)
        style_guide: Content style configuration
        voice_profile: Voice synthesis settings
        avatar_profile: Avatar generation settings
        cadence: Publishing frequency settings
        youtube_channel_id: YouTube channel ID for publishing
        is_active: Whether channel is active
    """

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Channel display name",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Channel description",
    )
    niche: str | None = Field(
        default=None,
        max_length=100,
        description="Content niche/category",
    )
    persona: Persona = Field(description="AI persona configuration")
    style_guide: StyleGuide | None = Field(
        default=None,
        description="Content style configuration",
    )
    voice_profile: VoiceProfile | None = Field(
        default=None,
        description="Voice synthesis settings",
    )
    avatar_profile: AvatarProfile | None = Field(
        default=None,
        description="Avatar generation settings",
    )
    cadence: Cadence | None = Field(
        default=None,
        description="Publishing frequency settings",
    )
    youtube_channel_id: str | None = Field(
        default=None,
        description="YouTube channel ID for publishing",
    )
    is_active: bool = Field(
        default=True,
        description="Whether channel is active",
    )


class ChannelUpdate(BaseModel):
    """
    Schema for updating an existing channel.

    All fields are optional - only provided fields are updated.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
    )
    niche: str | None = Field(
        default=None,
        max_length=100,
    )
    persona: Persona | None = None
    style_guide: StyleGuide | None = None
    voice_profile: VoiceProfile | None = None
    avatar_profile: AvatarProfile | None = None
    cadence: Cadence | None = None
    youtube_channel_id: str | None = None
    is_active: bool | None = None


class ChannelStats(BaseModel):
    """Channel statistics."""

    total_episodes: int = Field(description="Total number of episodes")
    published_episodes: int = Field(description="Number of published episodes")
    failed_episodes: int = Field(description="Number of failed episodes")
    in_progress_episodes: int = Field(description="Number of episodes in progress")
    avg_production_time_minutes: float | None = Field(
        default=None,
        description="Average production time in minutes",
    )


class ChannelResponse(BaseModel):
    """
    Schema for channel response data.

    Includes all channel fields plus computed properties.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Channel unique identifier")
    name: str = Field(description="Channel display name")
    slug: str = Field(description="URL-friendly identifier")
    description: str | None = Field(description="Channel description")
    niche: str | None = Field(description="Content niche")
    persona: dict[str, Any] = Field(description="Persona configuration")
    style_guide: dict[str, Any] = Field(description="Style guide configuration")
    voice_profile: dict[str, Any] = Field(description="Voice profile configuration")
    avatar_profile: dict[str, Any] = Field(description="Avatar profile configuration")
    cadence: str | None = Field(description="Publishing cadence")
    platform_config: dict[str, Any] = Field(description="Platform configuration")
    youtube_channel_id: str | None = Field(
        default=None,
        description="YouTube channel ID",
    )
    is_active: bool = Field(description="Whether channel is active")
    episode_count: int = Field(default=0, description="Number of episodes")
    stats: ChannelStats | None = Field(
        default=None,
        description="Channel statistics",
    )
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    deleted_at: datetime | None = Field(description="Deletion timestamp")


class ChannelListResponse(ApiResponse[list[ChannelResponse]]):
    """Response schema for channel list endpoint."""

    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        channels: list[ChannelResponse],
        pagination: PaginationMeta,
        request_id: str | None = None,
    ) -> "ChannelListResponse":
        """Create a channel list response with pagination."""
        meta: dict[str, Any] = {"pagination": pagination.model_dump()}
        if request_id:
            meta["request_id"] = request_id
        return cls(data=channels, meta=meta)


class ChannelIdentifier(BaseModel):
    """
    Identifier for channel lookup.

    Used to find a channel by one of several possible identifiers.
    At least one identifier must be provided.

    Attributes:
        slug: URL-friendly channel identifier
        youtube_channel_id: YouTube channel ID (e.g., UCxxxxxxx)
        youtube_handle: YouTube handle (e.g., @channelname)
    """

    slug: str | None = Field(
        default=None,
        description="URL-friendly channel identifier",
    )
    youtube_channel_id: str | None = Field(
        default=None,
        description="YouTube channel ID (e.g., UCxxxxxxx)",
    )
    youtube_handle: str | None = Field(
        default=None,
        description="YouTube handle (e.g., @channelname)",
    )

    @model_validator(mode="after")
    def at_least_one_identifier(self) -> "ChannelIdentifier":
        """Validate that at least one identifier is provided."""
        if not any([self.slug, self.youtube_channel_id, self.youtube_handle]):
            raise ValueError("At least one identifier must be provided")
        return self


class ChannelLookupRequest(BaseModel):
    """
    Request body for get-or-create channel endpoint.

    Provides an identifier to look up a channel, and optionally
    data to create the channel if it doesn't exist.

    Attributes:
        identifier: Channel identifier for lookup
        create_data: Optional channel creation data if not found
    """

    identifier: ChannelIdentifier = Field(
        description="Channel identifier for lookup",
    )
    create_data: ChannelCreate | None = Field(
        default=None,
        description="Channel creation data if not found (triggers create on 404)",
    )


class ChannelLookupResponse(ApiResponse[ChannelResponse]):
    """
    Response schema for channel lookup endpoint.

    Extends the standard ApiResponse with lookup-specific metadata.

    Attributes:
        data: The found or created channel
        meta: Metadata including created flag and matched_by identifier
    """

    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        channel: ChannelResponse,
        created: bool,
        matched_by: str | None = None,
    ) -> "ChannelLookupResponse":
        """
        Create a channel lookup response.

        Args:
            channel: The channel data
            created: Whether the channel was newly created
            matched_by: Which identifier matched (slug, youtube_channel_id, youtube_handle)

        Returns:
            ChannelLookupResponse instance
        """
        meta: dict[str, Any] = {"created": created}
        if matched_by:
            meta["matched_by"] = matched_by
        return cls(data=channel, meta=meta)
