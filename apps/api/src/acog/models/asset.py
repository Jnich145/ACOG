"""
Asset model for generated artifacts attached to episodes.

Assets represent the various outputs produced during the episode
pipeline, including scripts, audio files, videos, and thumbnails.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from acog.models.base import Base, TimestampMixin
from acog.models.enums import AssetType

if TYPE_CHECKING:
    from acog.models.episode import Episode


class Asset(Base, TimestampMixin):
    """
    Asset model representing generated artifacts attached to episodes.

    Each asset has a type, storage location, and provider metadata.
    Assets are produced by various pipeline stages:
    - planning -> plan
    - scripting -> script
    - audio -> audio
    - avatar -> avatar_video
    - broll -> b_roll
    - assembly -> assembled_video
    - metadata -> thumbnail, metadata

    Attributes:
        id: Unique identifier (UUID)
        episode_id: Parent episode reference
        type: Asset type (script, audio, avatar_video, etc.)
        name: Human-readable name
        uri: S3/MinIO path or external URL
        storage_bucket: Bucket name for S3/MinIO
        storage_key: Object key within bucket
        provider: Service that generated the asset
        provider_job_id: External job/task ID for tracking
        metadata: Provider-specific metadata (JSON)
        mime_type: MIME type of the asset
        file_size_bytes: File size in bytes
        duration_ms: Duration for audio/video assets (milliseconds)
        is_primary: Primary asset of this type for the episode
    """

    __tablename__ = "assets"

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

    # Asset identification
    type: Mapped[AssetType] = mapped_column(
        Enum(
            AssetType,
            name="asset_type",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Human-readable name",
    )

    # Storage location
    uri: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        doc="Full URI: s3://bucket/key or https://external.url/path",
    )
    storage_bucket: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Bucket name for S3/MinIO",
    )
    storage_key: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Object key within bucket",
    )

    # Provider information
    provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Service that generated the asset (elevenlabs, heygen, runway, etc.)",
    )
    provider_job_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="External job/task ID for tracking",
    )

    # Asset metadata (named asset_meta to avoid SQLAlchemy reserved 'metadata')
    asset_meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata",  # Column name in database
        JSONB,
        nullable=False,
        default=dict,
        doc="JSON: resolution, bitrate, voice_settings, generation_params, cost_cents",
    )

    # File information
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Duration in milliseconds for audio/video assets",
    )

    # Status
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="True if this is the primary/active asset of this type",
    )

    # Relationships
    episode: Mapped["Episode"] = relationship(
        "Episode",
        back_populates="assets",
    )

    def __repr__(self) -> str:
        """Return string representation of the asset."""
        return f"<Asset {self.type.value} for Episode {self.episode_id}>"

    @property
    def duration_seconds(self) -> float | None:
        """Get duration in seconds (convenience property)."""
        if self.duration_ms is not None:
            return self.duration_ms / 1000.0
        return None

    @duration_seconds.setter
    def duration_seconds(self, value: float | None) -> None:
        """Set duration from seconds."""
        if value is not None:
            self.duration_ms = int(value * 1000)
        else:
            self.duration_ms = None

    @property
    def file_size_mb(self) -> float | None:
        """Get file size in megabytes (convenience property)."""
        if self.file_size_bytes is not None:
            return self.file_size_bytes / (1024 * 1024)
        return None

    @property
    def cost_cents(self) -> int | None:
        """Extract cost in cents from metadata."""
        return self.asset_meta.get("cost_cents")

    @cost_cents.setter
    def cost_cents(self, value: int | None) -> None:
        """Set cost in cents in metadata."""
        if value is not None:
            self.asset_meta["cost_cents"] = value
        elif "cost_cents" in self.asset_meta:
            del self.asset_meta["cost_cents"]

    def get_s3_path(self) -> str | None:
        """
        Get the S3 path for this asset.

        Returns:
            S3 path in format 'bucket/key' or None if not stored in S3
        """
        if self.storage_bucket and self.storage_key:
            return f"{self.storage_bucket}/{self.storage_key}"
        return None

    def is_video(self) -> bool:
        """Check if this asset is a video type."""
        return self.type in [
            AssetType.AVATAR_VIDEO,
            AssetType.B_ROLL,
            AssetType.ASSEMBLED_VIDEO,
        ]

    def is_audio(self) -> bool:
        """Check if this asset is an audio type."""
        return self.type == AssetType.AUDIO

    def is_document(self) -> bool:
        """Check if this asset is a document type."""
        return self.type in [
            AssetType.SCRIPT,
            AssetType.PLAN,
            AssetType.METADATA,
        ]
