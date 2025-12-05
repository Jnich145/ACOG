"""
Application configuration using Pydantic Settings.

This module loads configuration from environment variables and .env files,
providing type-safe access to all application settings.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables.
    Settings are loaded from .env file if present.

    Attributes:
        environment: The deployment environment (development, staging, production)
        debug: Enable debug mode with verbose logging
        secret_key: Secret key for JWT token signing (min 32 chars)
        database_url: PostgreSQL connection string
        redis_url: Redis connection string for Celery broker
        s3_endpoint_url: S3/MinIO endpoint URL (None for AWS S3)
        s3_access_key: S3 access key
        s3_secret_key: S3 secret key
        s3_bucket_assets: S3 bucket for generated assets
        s3_bucket_scripts: S3 bucket for scripts and plans
        openai_api_key: OpenAI API key for content generation
        elevenlabs_api_key: ElevenLabs API key for voice synthesis
        heygen_api_key: HeyGen API key for avatar videos
        runway_api_key: Runway API key for B-roll generation
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Application
    app_name: str = "ACOG API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    # Security
    secret_key: str = Field(..., min_length=32)
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week
    algorithm: str = "HS256"

    # Database
    database_url: str = Field(
        ...,
        description="PostgreSQL connection string",
        examples=["postgresql://user:pass@localhost:5432/acog"],
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for Celery broker",
    )

    # S3/MinIO
    s3_endpoint_url: str | None = None  # None for real AWS S3
    s3_access_key: str = Field(..., description="S3 access key")
    s3_secret_key: str = Field(..., description="S3 secret key")
    s3_bucket_assets: str = "acog-assets"
    s3_bucket_scripts: str = "acog-scripts"
    s3_region: str = "us-east-1"

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model_planning: str = "gpt-4o"
    openai_model_scripting: str = "gpt-4o-mini"
    openai_model_metadata: str = "gpt-4o-mini"

    # Media Providers (optional for MVP)
    elevenlabs_api_key: str | None = None
    heygen_api_key: str | None = None
    runway_api_key: str | None = None

    # YouTube (optional for MVP)
    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @computed_field
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """
        Get synchronous database URL.

        Converts asyncpg URL to psycopg2 format for Alembic migrations.
        """
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses LRU cache to ensure settings are only loaded once
    during application lifecycle.

    Returns:
        Settings: Application settings instance
    """
    return Settings()
