"""
Channel model for content brands/personas.

Channels represent distinct content brands with their own voice,
style, and publishing identity. Each channel can have multiple episodes.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from acog.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from acog.models.episode import Episode


class Channel(Base, TimestampMixin):
    """
    Channel model representing a content brand/persona.

    Each channel has:
    - Unique identity (name, slug, description)
    - Persona configuration defining the AI personality
    - Style guide for content generation
    - Voice and avatar profiles for media synthesis
    - Publishing configuration

    Attributes:
        id: Unique identifier (UUID)
        name: Display name for the channel
        slug: URL-friendly unique identifier
        description: Channel description
        niche: Content niche (e.g., 'cosmology', 'tech_reviews')
        persona: JSON configuration for AI personality
        style_guide: JSON configuration for content style
        avatar_profile: JSON configuration for avatar video generation
        voice_profile: JSON configuration for voice synthesis
        cadence: Target publishing frequency
        platform_config: YouTube channel ID and OAuth configuration
        is_active: Whether channel is active for content generation
        episodes: Related episodes (one-to-many relationship)
    """

    __tablename__ = "channels"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Basic identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Display name for the channel",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        doc="URL-friendly unique identifier",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Channel description",
    )
    niche: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Content niche (e.g., 'cosmology', 'tech_reviews')",
    )

    # Persona and style configuration (JSONB for flexibility)
    persona: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: name, background, voice, attitude, values, expertise areas",
    )
    style_guide: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: tone, complexity, pacing, humor level, do/dont rules",
    )

    # Media generation profiles
    avatar_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: provider (heygen/synthesia), avatar_id, framing, background",
    )
    voice_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: provider (elevenlabs), voice_id, stability, similarity_boost",
    )

    # Publishing configuration
    cadence: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Target publishing frequency: daily, 3_per_week, weekly, etc.",
    )
    platform_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: YouTube channel ID, OAuth refs, etc.",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        doc="Whether channel is active for content generation",
    )

    # YouTube channel ID for direct lookup (indexed with unique partial index)
    youtube_channel_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="YouTube channel ID for direct lookup",
    )

    # Relationships
    episodes: Mapped[list["Episode"]] = relationship(
        "Episode",
        back_populates="channel",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        """Return string representation of the channel."""
        return f"<Channel {self.slug} ({self.name})>"

    @property
    def episode_count(self) -> int:
        """Get the count of non-deleted episodes."""
        from acog.models.episode import Episode

        return (
            self.episodes.filter(Episode.deleted_at.is_(None))  # type: ignore[union-attr]
            .count()
        )

    def get_voice_settings(self) -> dict[str, Any]:
        """
        Get voice synthesis settings for this channel.

        Returns:
            Dictionary with provider, voice_id, and synthesis settings
        """
        return {
            "provider": self.voice_profile.get("provider", "elevenlabs"),
            "voice_id": self.voice_profile.get("voice_id"),
            "stability": self.voice_profile.get("stability", 0.5),
            "similarity_boost": self.voice_profile.get("similarity_boost", 0.75),
            "style": self.voice_profile.get("style", 0.0),
        }

    def get_avatar_settings(self) -> dict[str, Any]:
        """
        Get avatar generation settings for this channel.

        Returns:
            Dictionary with provider, avatar_id, and visual settings
        """
        return {
            "provider": self.avatar_profile.get("provider", "heygen"),
            "avatar_id": self.avatar_profile.get("avatar_id"),
            "background": self.avatar_profile.get("background", "default"),
            "framing": self.avatar_profile.get("framing", "medium"),
        }
