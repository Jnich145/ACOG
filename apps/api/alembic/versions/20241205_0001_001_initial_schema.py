"""001_initial_schema

Create core ACOG tables: channels, episodes, jobs, assets

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-12-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    # Episode status enum (aligned with API contracts v1.1)
    episode_status = postgresql.ENUM(
        "idea",
        "planning",
        "scripting",
        "script_review",
        "audio",
        "avatar",
        "broll",
        "assembly",
        "ready",
        "publishing",
        "published",
        "failed",
        "cancelled",
        name="episode_status",
        create_type=True,
    )
    episode_status.create(op.get_bind(), checkfirst=True)

    # Job status enum
    job_status = postgresql.ENUM(
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="job_status",
        create_type=True,
    )
    job_status.create(op.get_bind(), checkfirst=True)

    # Asset type enum
    asset_type = postgresql.ENUM(
        "script",
        "audio",
        "avatar_video",
        "b_roll",
        "assembled_video",
        "thumbnail",
        "plan",
        "metadata",
        name="asset_type",
        create_type=True,
    )
    asset_type.create(op.get_bind(), checkfirst=True)

    # Idea source enum
    idea_source = postgresql.ENUM(
        "manual",
        "pulse",
        "series",
        "followup",
        "repurpose",
        name="idea_source",
        create_type=True,
    )
    idea_source.create(op.get_bind(), checkfirst=True)

    # Create channels table
    op.create_table(
        "channels",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("niche", sa.String(100), nullable=True),
        sa.Column(
            "persona",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "style_guide",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "avatar_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "voice_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("cadence", sa.String(50), nullable=True),
        sa.Column(
            "platform_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_channels")),
        sa.UniqueConstraint("slug", name=op.f("uq_channels_slug")),
    )

    # Create indexes for channels
    op.create_index(
        op.f("ix_channels_slug"),
        "channels",
        ["slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_channels_is_active"),
        "channels",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_channels_niche"),
        "channels",
        ["niche"],
        unique=False,
    )
    op.create_index(
        op.f("ix_channels_created_at"),
        "channels",
        ["created_at"],
        unique=False,
    )

    # Create episodes table
    op.create_table(
        "episodes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "pulse_event_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("slug", sa.String(200), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "idea",
                "planning",
                "scripting",
                "script_review",
                "audio",
                "avatar",
                "broll",
                "assembly",
                "ready",
                "publishing",
                "published",
                "failed",
                "cancelled",
                name="episode_status",
                create_type=False,
            ),
            server_default=sa.text("'idea'"),
            nullable=False,
        ),
        sa.Column(
            "idea_source",
            postgresql.ENUM(
                "manual",
                "pulse",
                "series",
                "followup",
                "repurpose",
                name="idea_source",
                create_type=False,
            ),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column(
            "idea",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "plan",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("script", sa.Text(), nullable=True),
        sa.Column(
            "script_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_state",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("published_url", sa.String(500), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "priority",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.id"],
            name=op.f("fk_episodes_channel_id_channels"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_episodes")),
    )

    # Create indexes for episodes
    op.create_index(
        op.f("ix_episodes_channel_id"),
        "episodes",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_episodes_status"),
        "episodes",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_episodes_priority"),
        "episodes",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_episodes_created_at"),
        "episodes",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_episodes_pulse_event_id"),
        "episodes",
        ["pulse_event_id"],
        unique=False,
    )

    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "episode_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="job_status",
                create_type=False,
            ),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column(
            "input_params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "max_retries",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"],
            ["episodes.id"],
            name=op.f("fk_jobs_episode_id_episodes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )

    # Create indexes for jobs
    op.create_index(
        op.f("ix_jobs_episode_id"),
        "jobs",
        ["episode_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_jobs_status"),
        "jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_jobs_stage"),
        "jobs",
        ["stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_jobs_celery_task_id"),
        "jobs",
        ["celery_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_jobs_created_at"),
        "jobs",
        ["created_at"],
        unique=False,
    )

    # Create assets table
    op.create_table(
        "assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "episode_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(
                "script",
                "audio",
                "avatar_video",
                "b_roll",
                "assembled_video",
                "thumbnail",
                "plan",
                "metadata",
                name="asset_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("uri", sa.String(1000), nullable=False),
        sa.Column("storage_bucket", sa.String(255), nullable=True),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("provider_job_id", sa.String(255), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["episode_id"],
            ["episodes.id"],
            name=op.f("fk_assets_episode_id_episodes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
    )

    # Create indexes for assets
    op.create_index(
        op.f("ix_assets_episode_id"),
        "assets",
        ["episode_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assets_type"),
        "assets",
        ["type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assets_provider"),
        "assets",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assets_created_at"),
        "assets",
        ["created_at"],
        unique=False,
    )

    # Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Create triggers for updated_at
    op.execute("""
        CREATE TRIGGER update_channels_updated_at
            BEFORE UPDATE ON channels
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER update_episodes_updated_at
            BEFORE UPDATE ON episodes
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER update_jobs_updated_at
            BEFORE UPDATE ON jobs
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER update_assets_updated_at
            BEFORE UPDATE ON assets
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_assets_updated_at ON assets;")
    op.execute("DROP TRIGGER IF EXISTS update_jobs_updated_at ON jobs;")
    op.execute("DROP TRIGGER IF EXISTS update_episodes_updated_at ON episodes;")
    op.execute("DROP TRIGGER IF EXISTS update_channels_updated_at ON channels;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop indexes
    op.drop_index(op.f("ix_assets_created_at"), table_name="assets")
    op.drop_index(op.f("ix_assets_provider"), table_name="assets")
    op.drop_index(op.f("ix_assets_type"), table_name="assets")
    op.drop_index(op.f("ix_assets_episode_id"), table_name="assets")

    op.drop_index(op.f("ix_jobs_created_at"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_celery_task_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_stage"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_episode_id"), table_name="jobs")

    op.drop_index(op.f("ix_episodes_pulse_event_id"), table_name="episodes")
    op.drop_index(op.f("ix_episodes_created_at"), table_name="episodes")
    op.drop_index(op.f("ix_episodes_priority"), table_name="episodes")
    op.drop_index(op.f("ix_episodes_status"), table_name="episodes")
    op.drop_index(op.f("ix_episodes_channel_id"), table_name="episodes")

    op.drop_index(op.f("ix_channels_created_at"), table_name="channels")
    op.drop_index(op.f("ix_channels_niche"), table_name="channels")
    op.drop_index(op.f("ix_channels_is_active"), table_name="channels")
    op.drop_index(op.f("ix_channels_slug"), table_name="channels")

    # Drop tables
    op.drop_table("assets")
    op.drop_table("jobs")
    op.drop_table("episodes")
    op.drop_table("channels")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS asset_type;")
    op.execute("DROP TYPE IF EXISTS idea_source;")
    op.execute("DROP TYPE IF EXISTS job_status;")
    op.execute("DROP TYPE IF EXISTS episode_status;")
