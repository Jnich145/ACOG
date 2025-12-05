"""
Pytest configuration and fixtures for ACOG API tests.

Provides database fixtures, test client, and factory functions
for creating test data.
"""

import os
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set test environment before importing application
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://acog:acog_dev_password@localhost:5432/acog_test",
)
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["S3_ACCESS_KEY"] = "test"
os.environ["S3_SECRET_KEY"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-key"

from acog.core.database import Base, get_db
from acog.main import app


# Test database setup
TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    """Override database dependency for tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the dependency
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def setup_database() -> Generator[None, None, None]:
    """
    Create database tables at the start of test session.

    Drops all tables at the end of the session.
    """
    # Import all models to register them with Base
    from acog.models import Asset, Channel, Episode, Job  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(setup_database: None) -> Generator[Session, None, None]:
    """
    Provide a database session for each test.

    Rolls back all changes after each test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(setup_database: None) -> Generator[TestClient, None, None]:
    """
    Provide a test client for API testing.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """
    Provide authentication headers for protected endpoints.

    Uses the demo user credentials.
    """
    from acog.core.security import create_access_token

    token = create_access_token(
        data={
            "sub": "test-user-id",
            "email": "test@acog.io",
            "role": "admin",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_channel_data() -> dict[str, Any]:
    """Provide sample data for creating a channel."""
    return {
        "name": "Test Channel",
        "description": "A test channel for unit tests",
        "niche": "testing",
        "persona": {
            "name": "Test Persona",
            "background": "Expert in testing",
            "voice": "Professional and clear",
            "values": ["accuracy", "clarity"],
            "expertise": ["testing", "quality assurance"],
        },
        "style_guide": {
            "tone": "conversational",
            "complexity": "intermediate",
            "pacing": "moderate",
            "humor_level": "light",
        },
        "voice_profile": {
            "provider": "elevenlabs",
            "voice_id": "test-voice-id",
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
        "avatar_profile": {
            "provider": "heygen",
            "avatar_id": "test-avatar-id",
            "background": "office",
            "framing": "medium",
        },
        "is_active": True,
    }


@pytest.fixture
def sample_episode_data() -> dict[str, Any]:
    """Provide sample data for creating an episode."""
    return {
        "title": "Test Episode",
        "idea_brief": "A test episode about testing things",
        "idea_source": "manual",
        "target_length_minutes": 10,
        "priority": "normal",
        "tags": ["test", "example"],
        "notes": "This is a test episode",
        "auto_advance": False,
    }


@pytest.fixture
def created_channel(
    db: Session,
    sample_channel_data: dict[str, Any],
) -> Any:
    """Create and return a channel in the database."""
    from acog.models.channel import Channel

    channel = Channel(
        name=sample_channel_data["name"],
        slug="test-channel",
        description=sample_channel_data["description"],
        niche=sample_channel_data["niche"],
        persona=sample_channel_data["persona"],
        style_guide=sample_channel_data["style_guide"],
        voice_profile=sample_channel_data["voice_profile"],
        avatar_profile=sample_channel_data["avatar_profile"],
        is_active=True,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@pytest.fixture
def created_episode(
    db: Session,
    created_channel: Any,
    sample_episode_data: dict[str, Any],
) -> Any:
    """Create and return an episode in the database."""
    from acog.models.episode import Episode
    from acog.models.enums import EpisodeStatus, IdeaSource

    episode = Episode(
        channel_id=created_channel.id,
        title=sample_episode_data["title"],
        slug="test-episode",
        status=EpisodeStatus.IDEA,
        idea_source=IdeaSource.MANUAL,
        idea={
            "brief": sample_episode_data["idea_brief"],
            "tags": sample_episode_data["tags"],
            "notes": sample_episode_data["notes"],
        },
        priority=0,
    )
    db.add(episode)
    db.commit()
    db.refresh(episode)
    return episode
