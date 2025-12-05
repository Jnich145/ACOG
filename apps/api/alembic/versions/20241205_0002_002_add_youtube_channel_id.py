"""002_add_youtube_channel_id

Add youtube_channel_id column to channels table with unique partial index.

Revision ID: 002_add_youtube_channel_id
Revises: 001_initial_schema
Create Date: 2024-12-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_add_youtube_channel_id"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add youtube_channel_id column to channels table
    op.add_column(
        "channels",
        sa.Column(
            "youtube_channel_id",
            sa.String(50),
            nullable=True,
            comment="YouTube channel ID for direct lookup",
        ),
    )

    # Migrate existing data from platform_config->>'youtube_channel_id' to the new column
    # This SQL extracts the youtube_channel_id from the JSONB platform_config and sets it
    op.execute("""
        UPDATE channels
        SET youtube_channel_id = platform_config->>'youtube_channel_id'
        WHERE platform_config->>'youtube_channel_id' IS NOT NULL
          AND platform_config->>'youtube_channel_id' != ''
    """)

    # Create unique partial index for youtube_channel_id
    # Only enforces uniqueness on non-deleted channels with non-null youtube_channel_id
    op.create_index(
        "ix_channels_youtube_channel_id_unique",
        "channels",
        ["youtube_channel_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND youtube_channel_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Drop the unique partial index
    op.drop_index("ix_channels_youtube_channel_id_unique", table_name="channels")

    # Migrate data back to platform_config (optional - preserves data)
    op.execute("""
        UPDATE channels
        SET platform_config = jsonb_set(
            platform_config,
            '{youtube_channel_id}',
            to_jsonb(youtube_channel_id)
        )
        WHERE youtube_channel_id IS NOT NULL
    """)

    # Drop the youtube_channel_id column
    op.drop_column("channels", "youtube_channel_id")
