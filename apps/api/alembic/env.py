"""
Alembic migration environment configuration.

This module configures Alembic to work with the ACOG database schema.
It loads the database URL from environment variables and sets up
the migration context.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the src directory to the path so we can import acog modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from acog.models.base import Base

# Import all models to ensure they are registered with Base.metadata
from acog.models import Asset, Channel, Episode, Job  # noqa: F401

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Get database URL from environment or config.

    Priority:
    1. DATABASE_URL environment variable
    2. sqlalchemy.url from alembic.ini
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        # Handle asyncpg URLs - convert to sync for Alembic
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://")
        return url

    return config.get_main_option("sqlalchemy.url", "")


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    # Get configuration for the engine
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        configuration = {}

    # Override the URL from environment
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
