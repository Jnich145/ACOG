"""
Database configuration and session management.

This module provides SQLAlchemy engine configuration, session factory,
and dependency injection for database sessions in FastAPI.
"""

from collections.abc import Generator
from typing import Any

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from acog.core.config import get_settings

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

    This class provides:
    - Consistent metadata with naming conventions
    - Common functionality inherited by all models
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_db_engine(database_url: str | None = None) -> Any:
    """
    Create SQLAlchemy engine with appropriate configuration.

    Args:
        database_url: Optional database URL override. If not provided,
                     uses the URL from settings.

    Returns:
        SQLAlchemy engine instance
    """
    settings = get_settings()
    url = database_url or settings.database_url

    # Engine configuration options
    engine_kwargs: dict[str, Any] = {
        "pool_pre_ping": True,  # Test connections before using
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 3600,  # Recycle connections after 1 hour
    }

    # Add echo for development debugging
    if settings.debug:
        engine_kwargs["echo"] = True

    return create_engine(url, **engine_kwargs)


# Global engine instance
engine = create_db_engine()

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection function for database sessions.

    Yields a database session and ensures it is properly closed
    after the request is complete.

    Yields:
        Session: SQLAlchemy database session

    Example:
        ```python
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
        ```
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables defined in the models. This should only be used
    for testing or initial development. Production should use Alembic
    migrations.
    """
    # Import all models to ensure they are registered with Base
    from acog.models import Asset, Channel, Episode, Job  # noqa: F401

    Base.metadata.create_all(bind=engine)
