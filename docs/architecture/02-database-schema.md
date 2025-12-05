# ACOG Database Schema Design

**Document:** 02-database-schema.md
**Version:** 1.1
**Phase:** 1 (Core Platform MVP)
**Author:** Systems Architect
**Last Updated:** 2024-12-05

---

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.1 | 2024-12-05 | Systems Architect | Added jobs table, aligned episode_status enum, standardized pipeline stages, added niche column, fixed directory references |
| 1.0 | 2024-12-05 | Systems Architect | Initial schema design |

---

## Overview

This document defines the PostgreSQL database schema for ACOG Phase 1. The schema supports the core domain model: Channels, Episodes, Assets, Jobs, and PulseEvents. It is designed for modularity, auditability, and future extensibility.

### Design Principles

1. **Soft Deletes** - All entities use `deleted_at` timestamps for audit trails
2. **JSON Flexibility** - Complex nested data (personas, plans, metadata) stored as JSONB
3. **Explicit State Management** - Enum types for status fields ensure data integrity
4. **Indexing for Performance** - Strategic indexes on foreign keys and query patterns
5. **Migration-Ready** - Schema designed for incremental Alembic migrations

---

## Entity Relationship Diagram (Textual)

```
+-------------+       +-------------+       +-------------+
|   Channel   |       |   Episode   |       |    Asset    |
+-------------+       +-------------+       +-------------+
| id (PK)     |<------| channel_id  |       | id (PK)     |
| name        |  1:N  | id (PK)     |<------| episode_id  |
| slug        |       | status      |  1:N  | type        |
| niche       |       | plan        |       | uri         |
| persona     |       | script      |       | provider    |
| style_guide |       | metadata    |       | metadata    |
| avatar_prof |       +-------------+       +-------------+
| voice_prof  |             |
+-------------+             | 1:N
                            v
                      +-------------+
                      |    Job      |
                      +-------------+
                      | id (PK)     |
                      | episode_id  |
                      | stage       |
                      | status      |
                      | result      |
                      +-------------+

                      +-------------+
                      | PulseEvent  |  (optional link to Episode)
                      +-------------+
                      | id (PK)     |
                      | source      |
                      | payload     |
                      | topic_tags  |
                      +-------------+
```

---

## SQL DDL - MVP Schema

### Enum Types

```sql
-- Episode lifecycle status
-- Tracks progression through the content pipeline
-- ALIGNED WITH API CONTRACTS (v1.1)
CREATE TYPE episode_status AS ENUM (
    'idea',           -- Initial concept captured
    'planning',       -- OpenAI planner generating outline
    'scripting',      -- Script generation in progress
    'script_review',  -- Script ready for human review
    'audio',          -- Audio generation in progress
    'avatar',         -- Avatar video generation in progress
    'broll',          -- B-roll generation in progress
    'assembly',       -- Final video assembly in progress
    'ready',          -- All assets ready, awaiting publish
    'publishing',     -- Upload in progress
    'published',      -- Successfully published to platform
    'failed',         -- Pipeline failed (check pipeline_state for details)
    'cancelled'       -- Manually cancelled by user
);

-- Job status for async pipeline operations
CREATE TYPE job_status AS ENUM (
    'queued',      -- Job queued, waiting for worker
    'running',     -- Job currently executing
    'completed',   -- Job finished successfully
    'failed',      -- Job failed (check error_message)
    'cancelled'    -- Job was cancelled
);

-- Pipeline stage names (standardized)
-- Used in jobs.stage and pipeline_state keys
CREATE TYPE pipeline_stage AS ENUM (
    'planning',       -- Content planning and outline generation
    'scripting',      -- Script generation
    'script_review',  -- Script QA and refinement
    'metadata',       -- SEO metadata generation
    'audio',          -- Voice synthesis (ElevenLabs)
    'avatar',         -- Avatar video generation (HeyGen/Synthesia)
    'broll',          -- B-roll generation (Runway/Pika)
    'assembly',       -- Final video assembly
    'upload'          -- Upload to publishing platform
);

-- Asset types produced during episode pipeline
CREATE TYPE asset_type AS ENUM (
    'script',           -- Final script document (text/markdown)
    'audio',            -- Voice synthesis output (MP3/WAV)
    'avatar_video',     -- Talking head video segments
    'b_roll',           -- Generated or sourced B-roll clips
    'assembled_video',  -- Final rendered video (MP4)
    'thumbnail',        -- Video thumbnail image
    'plan',             -- Stored plan document (alternative to inline JSON)
    'metadata'          -- SEO metadata export
);

-- Idea source tracking
CREATE TYPE idea_source AS ENUM (
    'manual',       -- User-entered topic
    'pulse',        -- Auto-generated from PulseEvent
    'series',       -- Generated as part of a series
    'followup',     -- Follow-up to previous episode
    'repurpose'     -- Repurposed from existing content
);
```

### Channel Table

```sql
-- Channels represent distinct content brands/personas
-- Each channel has its own voice, style, and publishing identity
CREATE TABLE channels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic identity
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(100) NOT NULL UNIQUE,  -- URL-friendly identifier
    description     TEXT,
    niche           VARCHAR(100),  -- Content niche (e.g., "cosmology", "tech_reviews", "finance")

    -- Persona and style configuration (JSONB for flexibility)
    persona         JSONB NOT NULL DEFAULT '{}',
    style_guide     JSONB NOT NULL DEFAULT '{}',

    -- Media generation profiles
    avatar_profile  JSONB NOT NULL DEFAULT '{}',
    voice_profile   JSONB NOT NULL DEFAULT '{}',

    -- Publishing configuration
    cadence         VARCHAR(50),  -- e.g., "3_per_week", "daily", "weekly"
    platform_config JSONB NOT NULL DEFAULT '{}',  -- YouTube channel ID, OAuth refs, etc.

    -- Status and metadata
    is_active       BOOLEAN NOT NULL DEFAULT true,

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ  -- Soft delete
);

-- Indexes for Channel
CREATE INDEX idx_channels_slug ON channels(slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_channels_is_active ON channels(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_channels_niche ON channels(niche) WHERE deleted_at IS NULL AND niche IS NOT NULL;
CREATE INDEX idx_channels_created_at ON channels(created_at DESC);

-- Comments for documentation
COMMENT ON TABLE channels IS 'Content channels/brands with distinct personas and publishing targets';
COMMENT ON COLUMN channels.niche IS 'Content niche for filtering and recommendations (e.g., cosmology, tech_reviews)';
COMMENT ON COLUMN channels.persona IS 'JSON: background, voice, attitude, values, expertise areas';
COMMENT ON COLUMN channels.style_guide IS 'JSON: tone, complexity, pacing, humor level, do/dont rules';
COMMENT ON COLUMN channels.avatar_profile IS 'JSON: provider (heygen/synthesia), avatar_id, framing, clothing';
COMMENT ON COLUMN channels.voice_profile IS 'JSON: provider (elevenlabs), voice_id, stability, similarity_boost';
COMMENT ON COLUMN channels.cadence IS 'Target publishing frequency: daily, 3_per_week, weekly, etc.';
```

### Episode Table

```sql
-- Episodes are the core content units that flow through the pipeline
-- Each episode belongs to a channel and progresses through defined stages
CREATE TABLE episodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    channel_id      UUID NOT NULL REFERENCES channels(id) ON DELETE RESTRICT,
    pulse_event_id  UUID,  -- Optional link to triggering PulseEvent

    -- Content identification
    title           VARCHAR(500),  -- Working title (may change during pipeline)
    slug            VARCHAR(200),  -- URL-friendly identifier

    -- Pipeline status (aligned with API contracts v1.1)
    status          episode_status NOT NULL DEFAULT 'idea',
    idea_source     idea_source NOT NULL DEFAULT 'manual',

    -- Content data (JSONB for complex nested structures)
    idea            JSONB NOT NULL DEFAULT '{}',  -- Original idea/topic brief
    plan            JSONB NOT NULL DEFAULT '{}',  -- Structured outline from planner
    script          TEXT,                          -- Full script content
    script_metadata JSONB NOT NULL DEFAULT '{}',  -- Script version, word count, etc.
    metadata        JSONB NOT NULL DEFAULT '{}',  -- Title, description, tags, SEO

    -- Pipeline execution state
    pipeline_state  JSONB NOT NULL DEFAULT '{}',  -- Per-stage status, timestamps, errors

    -- Publishing information
    published_url   VARCHAR(500),
    published_at    TIMESTAMPTZ,

    -- Execution tracking
    priority        INTEGER NOT NULL DEFAULT 0,   -- Higher = process sooner
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ  -- Soft delete
);

-- Indexes for Episode
CREATE INDEX idx_episodes_channel_id ON episodes(channel_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_episodes_status ON episodes(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_episodes_channel_status ON episodes(channel_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_episodes_created_at ON episodes(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_episodes_pulse_event ON episodes(pulse_event_id) WHERE pulse_event_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_episodes_priority ON episodes(priority DESC, created_at ASC) WHERE status IN ('idea', 'planning', 'scripting', 'script_review', 'audio', 'avatar', 'broll', 'assembly') AND deleted_at IS NULL;

-- Unique slug per channel (added in v1.1)
CREATE UNIQUE INDEX idx_episodes_slug_per_channel ON episodes(channel_id, slug) WHERE deleted_at IS NULL AND slug IS NOT NULL;

-- Comments
COMMENT ON TABLE episodes IS 'Content episodes flowing through the production pipeline';
COMMENT ON COLUMN episodes.idea IS 'JSON: topic, brief, target_audience, key_points, source_context';
COMMENT ON COLUMN episodes.plan IS 'JSON: hook, intro, sections[], key_facts[], ctas[], broll_suggestions[]';
COMMENT ON COLUMN episodes.script IS 'Full script text with markers: [AVATAR], [VOICEOVER], [BROLL:desc]';
COMMENT ON COLUMN episodes.metadata IS 'JSON: final_title, description, tags[], thumbnail_prompt, social_copy';
COMMENT ON COLUMN episodes.pipeline_state IS 'JSON: {stage: {status, started_at, completed_at, error, attempts}}';
```

### Jobs Table (Added in v1.1)

```sql
-- Jobs track async pipeline operations
-- Each job represents a single stage execution for an episode
-- Jobs are created when pipeline stages are triggered via API
CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,

    -- Job identification
    stage           VARCHAR(50) NOT NULL,  -- planning, scripting, audio, avatar, broll, assembly, metadata, upload

    -- Status tracking
    status          job_status NOT NULL DEFAULT 'queued',

    -- Celery integration
    celery_task_id  VARCHAR(255),  -- Celery task ID for tracking/revocation

    -- Execution details
    input_params    JSONB NOT NULL DEFAULT '{}',  -- Parameters passed to the job
    result          JSONB,                         -- Job output/result data
    error_message   TEXT,                          -- Error details if failed

    -- Timing
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,

    -- Retry tracking
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 3,

    -- Cost tracking (for billing/analytics)
    cost_usd        DECIMAL(10,4),
    tokens_used     INTEGER,

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for Jobs
CREATE INDEX idx_jobs_episode_id ON jobs(episode_id);
CREATE INDEX idx_jobs_status ON jobs(status) WHERE status IN ('queued', 'running');
CREATE INDEX idx_jobs_episode_stage ON jobs(episode_id, stage);
CREATE INDEX idx_jobs_celery_task ON jobs(celery_task_id) WHERE celery_task_id IS NOT NULL;
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);

-- Comments
COMMENT ON TABLE jobs IS 'Async pipeline job tracking for episode processing stages';
COMMENT ON COLUMN jobs.stage IS 'Pipeline stage: planning, scripting, script_review, metadata, audio, avatar, broll, assembly, upload';
COMMENT ON COLUMN jobs.status IS 'Job execution status: queued, running, completed, failed, cancelled';
COMMENT ON COLUMN jobs.celery_task_id IS 'Celery task ID for monitoring and revocation';
COMMENT ON COLUMN jobs.input_params IS 'JSON: stage-specific input parameters';
COMMENT ON COLUMN jobs.result IS 'JSON: stage-specific output data';
```

### Asset Table

```sql
-- Assets are generated artifacts attached to episodes
-- Each asset has a type, storage location, and provider metadata
CREATE TABLE assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,

    -- Asset identification
    type            asset_type NOT NULL,
    name            VARCHAR(255),  -- Human-readable name

    -- Storage location
    uri             VARCHAR(1000) NOT NULL,  -- S3/MinIO path or external URL
    storage_bucket  VARCHAR(255),            -- Bucket name for S3/MinIO
    storage_key     VARCHAR(500),            -- Object key within bucket

    -- Provider information
    provider        VARCHAR(100),  -- elevenlabs, heygen, runway, local, etc.
    provider_job_id VARCHAR(255),  -- External job/task ID for tracking

    -- Asset metadata
    metadata        JSONB NOT NULL DEFAULT '{}',

    -- File information
    mime_type       VARCHAR(100),
    file_size_bytes BIGINT,
    duration_ms     INTEGER,  -- For audio/video assets

    -- Status tracking
    is_primary      BOOLEAN NOT NULL DEFAULT false,  -- Primary asset of this type

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ  -- Soft delete
);

-- Indexes for Asset
CREATE INDEX idx_assets_episode_id ON assets(episode_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_assets_episode_type ON assets(episode_id, type) WHERE deleted_at IS NULL;
CREATE INDEX idx_assets_type ON assets(type) WHERE deleted_at IS NULL;
CREATE INDEX idx_assets_provider ON assets(provider) WHERE deleted_at IS NULL;
CREATE INDEX idx_assets_created_at ON assets(created_at DESC) WHERE deleted_at IS NULL;

-- Unique constraint: only one primary asset per type per episode
CREATE UNIQUE INDEX idx_assets_primary_unique
    ON assets(episode_id, type)
    WHERE is_primary = true AND deleted_at IS NULL;

-- Comments
COMMENT ON TABLE assets IS 'Generated artifacts (audio, video, scripts) attached to episodes';
COMMENT ON COLUMN assets.uri IS 'Full URI: s3://bucket/key or https://external.url/path';
COMMENT ON COLUMN assets.metadata IS 'JSON: resolution, bitrate, voice_settings, generation_params, cost_cents';
COMMENT ON COLUMN assets.is_primary IS 'True if this is the primary/active asset of this type for the episode';
```

### PulseEvent Table (Optional for Phase 1)

```sql
-- PulseEvents capture trend intelligence from external sources
-- These can seed episode ideas automatically
CREATE TABLE pulse_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification
    source          VARCHAR(100) NOT NULL,  -- youtube, reddit, twitter, news, etc.
    source_id       VARCHAR(255),           -- External ID from source platform
    source_url      VARCHAR(1000),          -- Link to original content

    -- Content
    payload         JSONB NOT NULL DEFAULT '{}',  -- Raw event data

    -- Classification
    topic_tags      TEXT[],  -- Array of topic tags
    relevance_score DECIMAL(5,4),  -- 0.0000 to 1.0000 relevance score

    -- Processing status
    is_processed    BOOLEAN NOT NULL DEFAULT false,
    processed_at    TIMESTAMPTZ,

    -- Matching channels (which channels might use this)
    matched_channels UUID[],  -- Array of channel IDs

    -- Timestamps
    event_timestamp TIMESTAMPTZ,  -- When the event occurred externally
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ  -- Soft delete
);

-- Indexes for PulseEvent
CREATE INDEX idx_pulse_events_source ON pulse_events(source) WHERE deleted_at IS NULL;
CREATE INDEX idx_pulse_events_is_processed ON pulse_events(is_processed) WHERE deleted_at IS NULL;
CREATE INDEX idx_pulse_events_score ON pulse_events(relevance_score DESC) WHERE deleted_at IS NULL AND is_processed = false;
CREATE INDEX idx_pulse_events_created_at ON pulse_events(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_pulse_events_topic_tags ON pulse_events USING GIN(topic_tags) WHERE deleted_at IS NULL;

-- Comments
COMMENT ON TABLE pulse_events IS 'Trend intelligence events from external sources (YouTube, Reddit, etc.)';
COMMENT ON COLUMN pulse_events.payload IS 'JSON: title, content, comments[], metrics{}, context{}';
COMMENT ON COLUMN pulse_events.relevance_score IS 'ML-computed relevance score (0-1)';
COMMENT ON COLUMN pulse_events.matched_channels IS 'Channel IDs this event is relevant to';
```

### Add Foreign Key for Episode-PulseEvent

```sql
-- Add FK constraint after both tables exist
ALTER TABLE episodes
    ADD CONSTRAINT fk_episodes_pulse_event
    FOREIGN KEY (pulse_event_id)
    REFERENCES pulse_events(id)
    ON DELETE SET NULL;
```

### Updated_at Trigger (Added in v1.1)

```sql
-- Trigger function to automatically update updated_at timestamp
-- This ensures updated_at is maintained even for direct SQL updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_channels_updated_at
    BEFORE UPDATE ON channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_episodes_updated_at
    BEFORE UPDATE ON episodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_assets_updated_at
    BEFORE UPDATE ON assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pulse_events_updated_at
    BEFORE UPDATE ON pulse_events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## JSONB Schema Definitions

### Channel.persona Schema

```json
{
  "name": "Dr. Sarah Chen",
  "background": "Astrophysicist with 15 years at NASA JPL",
  "expertise_areas": ["cosmology", "black holes", "space exploration"],
  "voice": "Warm, curious, slightly nerdy",
  "attitude": "Enthusiastic about science, accessible explanations",
  "values": ["accuracy", "wonder", "education"],
  "quirks": ["Often uses space analogies", "Ends with thought-provoking questions"],
  "avoid": ["Condescension", "Jargon without explanation"]
}
```

### Channel.style_guide Schema

```json
{
  "tone": "educational_entertaining",
  "complexity_level": "accessible_advanced",
  "pacing": "measured",
  "humor_level": "light",
  "target_length_minutes": 12,
  "structure_preferences": {
    "hook_style": "question_or_mindblower",
    "intro_length_seconds": 30,
    "sections_target": 4,
    "cta_placement": ["mid", "end"]
  },
  "rules": {
    "do": ["Use analogies", "Show enthusiasm", "Cite sources"],
    "dont": ["Clickbait titles", "Sensationalize", "Skip context"]
  }
}
```

### Channel.avatar_profile Schema

```json
{
  "provider": "heygen",
  "avatar_id": "avatar_abc123",
  "avatar_name": "Professional Female 1",
  "framing": "medium_shot",
  "background": "modern_office",
  "clothing_style": "business_casual",
  "gestures_enabled": true
}
```

### Channel.voice_profile Schema

```json
{
  "provider": "elevenlabs",
  "voice_id": "voice_xyz789",
  "voice_name": "Sarah - Professional",
  "model": "eleven_turbo_v2",
  "settings": {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
    "use_speaker_boost": true
  }
}
```

### Episode.pipeline_state Schema (Standardized Stage Names v1.1)

```json
{
  "planning": {
    "status": "completed",
    "started_at": "2024-01-15T10:00:00Z",
    "completed_at": "2024-01-15T10:02:30Z",
    "attempts": 1,
    "model_used": "gpt-4-turbo",
    "tokens_used": 2450
  },
  "scripting": {
    "status": "completed",
    "started_at": "2024-01-15T10:02:31Z",
    "completed_at": "2024-01-15T10:08:15Z",
    "attempts": 1,
    "model_used": "gpt-4-turbo",
    "tokens_used": 8200,
    "refinement_passes": 1
  },
  "script_review": {
    "status": "completed",
    "started_at": "2024-01-15T10:08:20Z",
    "completed_at": "2024-01-15T10:10:00Z",
    "reviewer": "system"
  },
  "metadata": {
    "status": "completed",
    "started_at": "2024-01-15T10:10:05Z",
    "completed_at": "2024-01-15T10:11:00Z"
  },
  "audio": {
    "status": "completed",
    "started_at": "2024-01-15T10:11:05Z",
    "completed_at": "2024-01-15T10:15:30Z",
    "attempts": 1,
    "provider": "elevenlabs",
    "job_id": "job_abc123"
  },
  "avatar": {
    "status": "running",
    "started_at": "2024-01-15T10:15:35Z",
    "attempts": 1,
    "provider": "heygen",
    "job_id": "job_def456"
  },
  "broll": {
    "status": "pending"
  },
  "assembly": {
    "status": "pending"
  },
  "upload": {
    "status": "pending"
  }
}
```

### Job.input_params Schema Examples

```json
// For planning stage
{
  "topic": "Black holes and time dilation",
  "target_length_minutes": 12,
  "style_overrides": {}
}

// For scripting stage
{
  "plan_id": "uuid",
  "refinement_level": "standard",
  "include_broll_markers": true
}

// For audio stage
{
  "script_id": "uuid",
  "voice_settings_override": {
    "stability": 0.6
  }
}
```

### Job.result Schema Examples

```json
// For planning stage
{
  "plan_id": "uuid",
  "sections_count": 5,
  "estimated_duration_minutes": 11.5
}

// For audio stage
{
  "asset_id": "uuid",
  "duration_seconds": 485.5,
  "character_count": 8500
}
```

### Asset.metadata Schema (varies by type)

```json
// For audio assets
{
  "duration_seconds": 485.5,
  "format": "mp3",
  "bitrate": 192,
  "sample_rate": 44100,
  "voice_settings_used": {
    "stability": 0.5,
    "similarity_boost": 0.75
  },
  "cost_cents": 125,
  "character_count": 8500
}

// For video assets
{
  "duration_seconds": 495.2,
  "resolution": "1920x1080",
  "fps": 30,
  "codec": "h264",
  "bitrate_kbps": 8000,
  "cost_cents": 350,
  "generation_params": {
    "avatar_id": "avatar_abc123",
    "background": "modern_office"
  }
}
```

---

## Indexing Strategy

### Query Patterns and Index Coverage

| Query Pattern | Index Used | Notes |
|---------------|------------|-------|
| List episodes by channel | `idx_episodes_channel_id` | Filtered by `deleted_at IS NULL` |
| Filter episodes by status | `idx_episodes_status` | Common dashboard filter |
| Channel + status combo | `idx_episodes_channel_status` | Composite for dashboard views |
| Episode assets by type | `idx_assets_episode_type` | Loading specific asset types |
| Unprocessed pulse events | `idx_pulse_events_is_processed` | Processing queue |
| High-score pulse events | `idx_pulse_events_score` | Priority processing |
| Topic-based search | `idx_pulse_events_topic_tags` (GIN) | Array contains queries |
| Priority queue | `idx_episodes_priority` | Partial index on active statuses |
| Active jobs | `idx_jobs_status` | Partial index on queued/running |
| Jobs by episode | `idx_jobs_episode_id` | Loading all jobs for episode |
| Job by Celery task | `idx_jobs_celery_task` | Celery status lookup |
| Channels by niche | `idx_channels_niche` | Filter channels by content niche |
| Episodes by slug | `idx_episodes_slug_per_channel` | Unique slug per channel |

### Partial Indexes

Partial indexes are used to exclude soft-deleted records, reducing index size and improving performance:

```sql
-- All indexes include WHERE deleted_at IS NULL
-- This is critical for maintaining query performance as data grows
```

### GIN Index for JSONB (Future)

```sql
-- Add when JSONB queries become common
CREATE INDEX idx_episodes_plan_gin ON episodes USING GIN(plan jsonb_path_ops);
CREATE INDEX idx_episodes_metadata_gin ON episodes USING GIN(metadata jsonb_path_ops);
```

---

## Migration Strategy (Alembic)

### Directory Structure

```
apps/api/
  alembic/
    versions/
      001_initial_schema.py
      002_add_pulse_events.py
      003_add_jobs_table.py
      004_add_niche_column.py
    env.py
    script.py.mako
  alembic.ini
```

### Initial Migration Template

```python
"""001_initial_schema

Create core ACOG tables: channels, episodes, assets

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types (aligned with API contracts v1.1)
    op.execute("""
        CREATE TYPE episode_status AS ENUM (
            'idea', 'planning', 'scripting', 'script_review',
            'audio', 'avatar', 'broll', 'assembly', 'ready',
            'publishing', 'published', 'failed', 'cancelled'
        )
    """)

    op.execute("""
        CREATE TYPE job_status AS ENUM (
            'queued', 'running', 'completed', 'failed', 'cancelled'
        )
    """)

    op.execute("""
        CREATE TYPE pipeline_stage AS ENUM (
            'planning', 'scripting', 'script_review', 'metadata',
            'audio', 'avatar', 'broll', 'assembly', 'upload'
        )
    """)

    op.execute("""
        CREATE TYPE asset_type AS ENUM (
            'script', 'audio', 'avatar_video', 'b_roll',
            'assembled_video', 'thumbnail', 'plan', 'metadata'
        )
    """)

    op.execute("""
        CREATE TYPE idea_source AS ENUM (
            'manual', 'pulse', 'series', 'followup', 'repurpose'
        )
    """)

    # Create channels table
    op.create_table(
        'channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text),
        sa.Column('niche', sa.String(100)),  # Added in v1.1
        sa.Column('persona', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('style_guide', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('avatar_profile', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('voice_profile', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('cadence', sa.String(50)),
        sa.Column('platform_config', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
    )

    # Create episodes table
    op.create_table(
        'episodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pulse_event_id', postgresql.UUID(as_uuid=True)),
        sa.Column('title', sa.String(500)),
        sa.Column('slug', sa.String(200)),
        sa.Column('status', postgresql.ENUM('idea', 'planning', 'scripting', 'script_review',
                  'audio', 'avatar', 'broll', 'assembly', 'ready',
                  'publishing', 'published', 'failed', 'cancelled',
                  name='episode_status', create_type=False), nullable=False,
                  server_default='idea'),
        sa.Column('idea_source', postgresql.ENUM('manual', 'pulse', 'series', 'followup',
                  'repurpose', name='idea_source', create_type=False), nullable=False,
                  server_default='manual'),
        sa.Column('idea', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('plan', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('script', sa.Text),
        sa.Column('script_metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('pipeline_state', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('published_url', sa.String(500)),
        sa.Column('published_at', sa.DateTime(timezone=True)),
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='RESTRICT'),
    )

    # Create jobs table (added in v1.1)
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('episode_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('status', postgresql.ENUM('queued', 'running', 'completed', 'failed', 'cancelled',
                  name='job_status', create_type=False), nullable=False,
                  server_default='queued'),
        sa.Column('celery_task_id', sa.String(255)),
        sa.Column('input_params', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('result', postgresql.JSONB),
        sa.Column('error_message', sa.Text),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer, nullable=False, server_default='3'),
        sa.Column('cost_usd', sa.Numeric(10, 4)),
        sa.Column('tokens_used', sa.Integer),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ondelete='CASCADE'),
    )

    # Create assets table
    op.create_table(
        'assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('episode_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', postgresql.ENUM('script', 'audio', 'avatar_video', 'b_roll',
                  'assembled_video', 'thumbnail', 'plan', 'metadata',
                  name='asset_type', create_type=False), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('uri', sa.String(1000), nullable=False),
        sa.Column('storage_bucket', sa.String(255)),
        sa.Column('storage_key', sa.String(500)),
        sa.Column('provider', sa.String(100)),
        sa.Column('provider_job_id', sa.String(255)),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('mime_type', sa.String(100)),
        sa.Column('file_size_bytes', sa.BigInteger),
        sa.Column('duration_ms', sa.Integer),
        sa.Column('is_primary', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ondelete='CASCADE'),
    )

    # Create indexes (see full DDL above for complete list)
    # ... index creation statements


def downgrade() -> None:
    op.drop_table('assets')
    op.drop_table('jobs')
    op.drop_table('episodes')
    op.drop_table('channels')
    op.execute('DROP TYPE episode_status')
    op.execute('DROP TYPE job_status')
    op.execute('DROP TYPE pipeline_stage')
    op.execute('DROP TYPE asset_type')
    op.execute('DROP TYPE idea_source')
```

### Migration Best Practices

1. **One concept per migration** - Don't mix unrelated changes
2. **Always test rollback** - Ensure `downgrade()` works
3. **Use transactions** - Alembic wraps in transaction by default
4. **Data migrations separate** - Split DDL and data migrations
5. **Index creation** - Use `CREATE INDEX CONCURRENTLY` in production

---

## SQLAlchemy Model Structure

### Model Location

```
apps/api/
  src/
    acog/
      models/
        __init__.py
        base.py          # Base model with common fields
        channel.py
        episode.py
        job.py           # Added in v1.1
        asset.py
        pulse_event.py
```

### Base Model

```python
# apps/api/src/acog/models/base.py
from datetime import datetime
from typing import Optional
from uuid import UUID
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID


class Base(DeclarativeBase):
    """Base class for all models with common fields."""
    pass


class TimestampMixin:
    """Mixin for created_at, updated_at, deleted_at fields."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()
```

### Channel Model

```python
# apps/api/src/acog/models/channel.py
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
import uuid

from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .episode import Episode


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    niche: Mapped[Optional[str]] = mapped_column(String(100))  # Added in v1.1

    # JSONB fields for flexible configuration
    persona: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    style_guide: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    avatar_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    voice_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    platform_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    cadence: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    episodes: Mapped[List["Episode"]] = relationship(
        "Episode",
        back_populates="channel",
        lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Channel {self.slug}>"
```

### Episode Model

```python
# apps/api/src/acog/models/episode.py
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from datetime import datetime
import uuid
import enum

from sqlalchemy import String, Text, Integer, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .channel import Channel
    from .asset import Asset
    from .job import Job


class EpisodeStatus(str, enum.Enum):
    """Episode lifecycle status - aligned with API contracts v1.1"""
    IDEA = "idea"
    PLANNING = "planning"
    SCRIPTING = "scripting"
    SCRIPT_REVIEW = "script_review"
    AUDIO = "audio"
    AVATAR = "avatar"
    BROLL = "broll"
    ASSEMBLY = "assembly"
    READY = "ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IdeaSource(str, enum.Enum):
    MANUAL = "manual"
    PULSE = "pulse"
    SERIES = "series"
    FOLLOWUP = "followup"
    REPURPOSE = "repurpose"


class Episode(Base, TimestampMixin):
    __tablename__ = "episodes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    channel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="RESTRICT"),
        nullable=False
    )
    pulse_event_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pulse_events.id", ondelete="SET NULL"),
        nullable=True
    )

    title: Mapped[Optional[str]] = mapped_column(String(500))
    slug: Mapped[Optional[str]] = mapped_column(String(200))

    status: Mapped[EpisodeStatus] = mapped_column(
        Enum(EpisodeStatus, name="episode_status", create_type=False),
        nullable=False,
        default=EpisodeStatus.IDEA
    )
    idea_source: Mapped[IdeaSource] = mapped_column(
        Enum(IdeaSource, name="idea_source", create_type=False),
        nullable=False,
        default=IdeaSource.MANUAL
    )

    # Content fields
    idea: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    script: Mapped[Optional[str]] = mapped_column(Text)
    script_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    pipeline_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Publishing
    published_url: Mapped[Optional[str]] = mapped_column(String(500))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Execution
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="episodes")
    assets: Mapped[List["Asset"]] = relationship(
        "Asset",
        back_populates="episode",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    jobs: Mapped[List["Job"]] = relationship(
        "Job",
        back_populates="episode",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Episode {self.id} [{self.status.value}]>"

    def update_pipeline_stage(
        self,
        stage: str,
        status: str,
        error: Optional[str] = None,
        **extra
    ) -> None:
        """Update a specific pipeline stage status."""
        if stage not in self.pipeline_state:
            self.pipeline_state[stage] = {}

        self.pipeline_state[stage]["status"] = status
        self.pipeline_state[stage]["updated_at"] = datetime.utcnow().isoformat()

        if status == "running" and "started_at" not in self.pipeline_state[stage]:
            self.pipeline_state[stage]["started_at"] = datetime.utcnow().isoformat()
        elif status == "completed":
            self.pipeline_state[stage]["completed_at"] = datetime.utcnow().isoformat()
        elif status == "failed" and error:
            self.pipeline_state[stage]["error"] = error

        for key, value in extra.items():
            self.pipeline_state[stage][key] = value
```

### Job Model (Added in v1.1)

```python
# apps/api/src/acog/models/job.py
from typing import Optional, TYPE_CHECKING
from uuid import UUID
from datetime import datetime
from decimal import Decimal
import uuid
import enum

from sqlalchemy import String, Text, Integer, ForeignKey, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from .base import Base

if TYPE_CHECKING:
    from .episode import Episode


class JobStatus(str, enum.Enum):
    """Job execution status"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(str, enum.Enum):
    """Standardized pipeline stage names"""
    PLANNING = "planning"
    SCRIPTING = "scripting"
    SCRIPT_REVIEW = "script_review"
    METADATA = "metadata"
    AUDIO = "audio"
    AVATAR = "avatar"
    BROLL = "broll"
    ASSEMBLY = "assembly"
    UPLOAD = "upload"


class Job(Base):
    """
    Jobs track async pipeline operations.
    Each job represents a single stage execution for an episode.
    """
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=False
    )

    # Job identification
    stage: Mapped[str] = mapped_column(String(50), nullable=False)

    # Status tracking
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", create_type=False),
        nullable=False,
        default=JobStatus.QUEUED
    )

    # Celery integration
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Execution details
    input_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Cost tracking
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamps (no soft delete for jobs)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    episode: Mapped["Episode"] = relationship("Episode", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<Job {self.id} [{self.stage}:{self.status.value}]>"

    def start(self) -> None:
        """Mark job as running."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self, result: Optional[dict] = None) -> None:
        """Mark job as completed with optional result."""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if result:
            self.result = result

    def fail(self, error_message: str) -> None:
        """Mark job as failed with error message."""
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message

    def cancel(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries and self.status == JobStatus.FAILED

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
```

### Asset Model

```python
# apps/api/src/acog/models/asset.py
from typing import Optional, TYPE_CHECKING
from uuid import UUID
import uuid
import enum

from sqlalchemy import String, BigInteger, Integer, Boolean, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .episode import Episode


class AssetType(str, enum.Enum):
    SCRIPT = "script"
    AUDIO = "audio"
    AVATAR_VIDEO = "avatar_video"
    B_ROLL = "b_roll"
    ASSEMBLED_VIDEO = "assembled_video"
    THUMBNAIL = "thumbnail"
    PLAN = "plan"
    METADATA = "metadata"


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=False
    )

    type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type", create_type=False),
        nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(255))

    # Storage
    uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_bucket: Mapped[Optional[str]] = mapped_column(String(255))
    storage_key: Mapped[Optional[str]] = mapped_column(String(500))

    # Provider
    provider: Mapped[Optional[str]] = mapped_column(String(100))
    provider_job_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # File info
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    episode: Mapped["Episode"] = relationship("Episode", back_populates="assets")

    def __repr__(self) -> str:
        return f"<Asset {self.type.value} for Episode {self.episode_id}>"
```

### Models __init__.py

```python
# apps/api/src/acog/models/__init__.py
from .base import Base, TimestampMixin
from .channel import Channel
from .episode import Episode, EpisodeStatus, IdeaSource
from .job import Job, JobStatus, PipelineStage
from .asset import Asset, AssetType
from .pulse_event import PulseEvent

__all__ = [
    "Base",
    "TimestampMixin",
    "Channel",
    "Episode",
    "EpisodeStatus",
    "IdeaSource",
    "Job",
    "JobStatus",
    "PipelineStage",
    "Asset",
    "AssetType",
    "PulseEvent",
]
```

---

## Future Extensions (Post-MVP)

### Phase 2+ Schema Additions

#### 1. Cost Tracking Table

```sql
-- Track costs per operation for budgeting and analytics
CREATE TABLE cost_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id      UUID REFERENCES episodes(id),
    channel_id      UUID REFERENCES channels(id),

    provider        VARCHAR(100) NOT NULL,  -- openai, elevenlabs, heygen, etc.
    operation_type  VARCHAR(100) NOT NULL,  -- planning, script, audio, video

    -- Cost details
    cost_cents      INTEGER NOT NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',

    -- Usage metrics
    units_consumed  DECIMAL(12,4),  -- tokens, characters, seconds, etc.
    unit_type       VARCHAR(50),    -- tokens, characters, video_seconds

    -- Reference
    provider_ref    VARCHAR(255),   -- Provider's transaction/job ID

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cost_entries_episode ON cost_entries(episode_id);
CREATE INDEX idx_cost_entries_channel ON cost_entries(channel_id);
CREATE INDEX idx_cost_entries_provider ON cost_entries(provider);
CREATE INDEX idx_cost_entries_created_at ON cost_entries(created_at DESC);
```

#### 2. Version History Table

```sql
-- Track version history for scripts and plans
CREATE TABLE episode_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id      UUID NOT NULL REFERENCES episodes(id),

    version_type    VARCHAR(50) NOT NULL,  -- 'plan', 'script', 'metadata'
    version_number  INTEGER NOT NULL,

    content         JSONB NOT NULL,  -- Snapshot of the versioned content

    -- Change tracking
    changed_by      VARCHAR(255),    -- User or 'system'
    change_reason   TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_episode_versions_episode ON episode_versions(episode_id);
CREATE UNIQUE INDEX idx_episode_versions_unique ON episode_versions(episode_id, version_type, version_number);
```

#### 3. User Accounts Table

```sql
-- User accounts for dashboard access
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,

    name            VARCHAR(255),
    role            VARCHAR(50) NOT NULL DEFAULT 'viewer',  -- admin, editor, viewer

    is_active       BOOLEAN NOT NULL DEFAULT true,

    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

-- User-channel permissions (many-to-many)
CREATE TABLE user_channel_permissions (
    user_id         UUID NOT NULL REFERENCES users(id),
    channel_id      UUID NOT NULL REFERENCES channels(id),
    permission      VARCHAR(50) NOT NULL,  -- view, edit, admin

    PRIMARY KEY (user_id, channel_id)
);
```

#### 4. Scheduled Jobs Table

```sql
-- Schedule future episodes and recurring content
CREATE TABLE scheduled_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    channel_id      UUID NOT NULL REFERENCES channels(id),
    episode_id      UUID REFERENCES episodes(id),  -- NULL for templates

    job_type        VARCHAR(50) NOT NULL,  -- 'episode_create', 'episode_publish', 'series_next'

    scheduled_for   TIMESTAMPTZ NOT NULL,

    config          JSONB NOT NULL DEFAULT '{}',  -- Job-specific configuration

    status          VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    executed_at     TIMESTAMPTZ,
    result          JSONB,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scheduled_jobs_status ON scheduled_jobs(status, scheduled_for) WHERE status = 'pending';
```

#### 5. Audit Log Table

```sql
-- Comprehensive audit trail for compliance and debugging
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    entity_type     VARCHAR(100) NOT NULL,  -- channel, episode, asset
    entity_id       UUID NOT NULL,
    action          VARCHAR(50) NOT NULL,   -- create, update, delete, status_change

    actor_type      VARCHAR(50) NOT NULL,   -- user, system, worker
    actor_id        VARCHAR(255),

    old_values      JSONB,
    new_values      JSONB,

    ip_address      INET,
    user_agent      TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
```

---

## Common Queries Reference

### Dashboard Queries

```sql
-- List episodes for a channel with latest status
SELECT
    e.id,
    e.title,
    e.status,
    e.created_at,
    e.updated_at,
    COUNT(a.id) as asset_count
FROM episodes e
LEFT JOIN assets a ON a.episode_id = e.id AND a.deleted_at IS NULL
WHERE e.channel_id = :channel_id
  AND e.deleted_at IS NULL
GROUP BY e.id
ORDER BY e.created_at DESC
LIMIT 50;

-- Pipeline status overview
SELECT
    status,
    COUNT(*) as count
FROM episodes
WHERE channel_id = :channel_id
  AND deleted_at IS NULL
  AND created_at > NOW() - INTERVAL '30 days'
GROUP BY status;

-- Get episode with all assets
SELECT
    e.*,
    json_agg(
        json_build_object(
            'id', a.id,
            'type', a.type,
            'uri', a.uri,
            'provider', a.provider,
            'is_primary', a.is_primary
        )
    ) FILTER (WHERE a.id IS NOT NULL) as assets
FROM episodes e
LEFT JOIN assets a ON a.episode_id = e.id AND a.deleted_at IS NULL
WHERE e.id = :episode_id
  AND e.deleted_at IS NULL
GROUP BY e.id;

-- Get episode with active jobs
SELECT
    e.*,
    json_agg(
        json_build_object(
            'id', j.id,
            'stage', j.stage,
            'status', j.status,
            'started_at', j.started_at,
            'completed_at', j.completed_at
        )
    ) FILTER (WHERE j.id IS NOT NULL) as jobs
FROM episodes e
LEFT JOIN jobs j ON j.episode_id = e.id
WHERE e.id = :episode_id
  AND e.deleted_at IS NULL
GROUP BY e.id;

-- List channels by niche
SELECT *
FROM channels
WHERE niche = :niche
  AND is_active = true
  AND deleted_at IS NULL
ORDER BY name;
```

### Worker Queries

```sql
-- Get next episode to process (by priority)
SELECT *
FROM episodes
WHERE status IN ('idea', 'planning', 'scripting', 'script_review', 'audio', 'avatar', 'broll', 'assembly')
  AND deleted_at IS NULL
ORDER BY priority DESC, created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- Get queued jobs for processing
SELECT j.*, e.channel_id
FROM jobs j
JOIN episodes e ON e.id = j.episode_id
WHERE j.status = 'queued'
ORDER BY j.created_at ASC
LIMIT 10
FOR UPDATE SKIP LOCKED;

-- Get unprocessed pulse events
SELECT *
FROM pulse_events
WHERE is_processed = false
  AND deleted_at IS NULL
  AND relevance_score > 0.7
ORDER BY relevance_score DESC
LIMIT 10;
```

---

## Maintenance Notes

### Vacuum and Analyze

```sql
-- Run periodically for JSONB columns
VACUUM ANALYZE channels;
VACUUM ANALYZE episodes;
VACUUM ANALYZE jobs;
VACUUM ANALYZE assets;
```

### Soft Delete Cleanup (Optional)

```sql
-- Archive old soft-deleted records (run monthly)
-- Only after confirming audit requirements are met

-- Example: permanently delete episodes soft-deleted >90 days ago
DELETE FROM assets
WHERE episode_id IN (
    SELECT id FROM episodes
    WHERE deleted_at < NOW() - INTERVAL '90 days'
);

DELETE FROM episodes
WHERE deleted_at < NOW() - INTERVAL '90 days';
```

---

## Checklist for Implementation

### Phase 1 MVP

- [ ] Create enum types (episode_status, job_status, pipeline_stage, asset_type, idea_source)
- [ ] Create channels table with indexes (including niche column)
- [ ] Create episodes table with indexes and FK to channels
- [ ] Create jobs table with indexes and FK to episodes
- [ ] Create assets table with indexes and FK to episodes
- [ ] Create pulse_events table (optional, can defer)
- [ ] Add FK from episodes to pulse_events (if created)
- [ ] Create updated_at triggers for all tables
- [ ] Set up Alembic with initial migration
- [ ] Create SQLAlchemy models
- [ ] Write Pydantic schemas for API validation
- [ ] Test soft delete behavior
- [ ] Verify index coverage for planned queries

### Post-MVP

- [ ] Add cost_entries table
- [ ] Add episode_versions table
- [ ] Add users and permissions tables
- [ ] Add scheduled_jobs table
- [ ] Add audit_logs table
- [ ] Add GIN indexes for JSONB queries

---

## Decision Log

| Date | Decision | Reasoning |
|------|----------|-----------|
| 2024-12-05 | Use UUID for all primary keys | Global uniqueness, safe for distributed systems, no sequence contention |
| 2024-12-05 | JSONB for flexible fields | Allows schema evolution without migrations for persona/config data |
| 2024-12-05 | Soft deletes via deleted_at | Audit requirements, ability to recover, maintains referential integrity |
| 2024-12-05 | Partial indexes with deleted_at filter | Performance optimization, smaller index size for active data |
| 2024-12-05 | ON DELETE RESTRICT for channel->episode | Prevent accidental data loss, require explicit episode cleanup |
| 2024-12-05 | ON DELETE CASCADE for episode->asset | Assets have no meaning without episode, simplify cleanup |
| 2024-12-05 | Store script as TEXT not JSONB | Scripts are primarily text, simpler editing, better full-text search later |
| 2024-12-05 | Add jobs table (v1.1) | Required for async pipeline tracking, API contracts return job_id |
| 2024-12-05 | Align episode_status enum (v1.1) | Consistency with API contracts, more granular pipeline tracking |
| 2024-12-05 | Standardize pipeline stage names (v1.1) | Consistency across DB, API, and workers (use: audio, avatar, broll) |
| 2024-12-05 | Add niche column to channels (v1.1) | API contracts expect niche filtering capability |
| 2024-12-05 | ON DELETE CASCADE for episode->job | Jobs have no meaning without episode, simplify cleanup |
| 2024-12-05 | No soft delete for jobs | Jobs are execution records, not user content; hard delete is appropriate |

---

*This document is part of the ACOG Architecture Documentation series.*
