"""
Base model classes and mixins for SQLAlchemy models.

This module provides the foundation for all database models including:
- Base declarative class with naming conventions
- TimestampMixin for created_at, updated_at, deleted_at fields
- Common model utilities
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention for database constraints
# This ensures consistent naming across all databases and makes
# Alembic migrations more predictable
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Provides:
    - Consistent metadata with naming conventions
    - Common type annotations for mapped columns
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Type annotation map for SQLAlchemy 2.0
    type_annotation_map = {
        UUID: PGUUID(as_uuid=True),
    }


class TimestampMixin:
    """
    Mixin providing standard timestamp fields for models.

    Adds created_at, updated_at, and deleted_at fields with
    automatic timestamp management.

    Attributes:
        created_at: Timestamp when the record was created
        updated_at: Timestamp when the record was last updated
        deleted_at: Timestamp when the record was soft-deleted (nullable)
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when the record was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when the record was last updated",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="Timestamp when the record was soft-deleted",
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record has been soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the record as soft-deleted with current timestamp."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None


class UUIDMixin:
    """
    Mixin providing a UUID primary key.

    Generates a UUID v4 as the default primary key value.
    """

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Unique identifier (UUID v4)",
    )


def model_to_dict(model: Any, exclude: set[str] | None = None) -> dict[str, Any]:
    """
    Convert a SQLAlchemy model instance to a dictionary.

    Useful for serialization and debugging.

    Args:
        model: SQLAlchemy model instance
        exclude: Set of field names to exclude from output

    Returns:
        Dictionary representation of the model
    """
    exclude = exclude or set()
    result = {}

    for column in model.__table__.columns:
        if column.name not in exclude:
            value = getattr(model, column.name)
            # Convert UUID to string for JSON serialization
            if isinstance(value, UUID):
                value = str(value)
            # Convert datetime to ISO format
            elif isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value

    return result
