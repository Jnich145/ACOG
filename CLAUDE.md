# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ACOG (Automated Content Orchestration & Generation Engine) is an AI-orchestrated media production system that autonomously generates, manages, and publishes persona-driven video content across multiple YouTube channels and niches.

The system coordinates a pipeline of services—OpenAI models, audio synthesis (ElevenLabs), avatar video generation (HeyGen/Synthesia), B-roll generation (Runway/Pika), and publishing APIs—to produce end-to-end content with minimal human intervention.

## Technology Stack

**Backend:** Python 3.x with FastAPI, SQLAlchemy, Alembic, Celery + Redis
**Database:** PostgreSQL
**Storage:** S3/MinIO for assets
**Frontend:** Next.js (App Router) with TypeScript, TailwindCSS, React Query/SWR
**AI/LLM:** OpenAI (GPT-4.x) for planning, scripting, metadata generation
**Media Providers:** ElevenLabs (voice), HeyGen/Synthesia (avatars), Runway/Pika (B-roll)

## Core Domain Model

- **Channel**: Persona, style guide, avatar/voice profiles, publishing cadence
- **Episode**: Content unit progressing through pipeline stages (idea → planning → script → media → assembly → publish)
- **Asset**: Generated artifacts (scripts, audio, video, thumbnails) stored in object storage
- **PulseEvent**: External trend intelligence that seeds episode ideas

## Pipeline Stages

Episodes flow through: Idea Intake → Planning (OpenAI) → Script Generation → Script Refinement → Metadata Generation → Audio (ElevenLabs) → Avatar Video → B-roll → Assembly → Upload to YouTube

## Architecture Principles

1. **OpenAI at the core**: Use for reasoning, planning, scriptwriting, metadata
2. **Modularity**: Services can be developed, upgraded, or replaced independently
3. **Multi-channel & multi-persona**: Each channel has unique persona and style
4. **Automation with human override**: Manual review/edit at any stage
5. **Observability**: All prompts and outputs recorded for audit/debugging
6. **Cost awareness**: Per-episode and per-channel budgets

## Specialized Agents

This project uses specialized Claude Code agents for different concerns:

- **acog-systems-architect**: Architecture design, API contracts, database schemas, sprint planning
- **acog-backend-engineer**: FastAPI endpoints, SQLAlchemy models, Celery tasks, integrations
- **acog-frontend-nextjs**: Next.js dashboard pages, components, real-time updates
- **acog-reviewer-qa**: Code review, architecture review, quality assurance

## Backend Code Organization

```
/api          - FastAPI routers and endpoints
/services     - Business logic layer
/models       - SQLAlchemy ORM entities
/schemas      - Pydantic validation models
/workers      - Celery tasks
/integrations - External API clients (OpenAI, ElevenLabs, HeyGen, etc.)
/core         - Configuration, dependencies, security
```

## Key Design Decisions

- **Task orchestration**: Celery + Redis for MVP, consider Prefect/Temporal for advanced DAG workflows
- **State machine**: Each episode stage can be "pending", "running", "completed", "failed"
- **Provider abstraction**: Media providers isolated behind adapters for easy swapping
- **Dual interfaces**: Dashboard and CLI consume the same backend APIs

## External Documentation Library

ACOG maintains local copies of external API documentation to ground agent decisions in real constraints rather than approximations. Documentation is organized in:

```
docs/external/youtube/     - YouTube Data API, upload specs, metadata schemas
docs/external/backend/     - Alembic, SQLAlchemy, Celery, FastAPI references
docs/external/ffmpeg/      - Video encoding, assembly, format specifications
docs/external/media/       - ElevenLabs, HeyGen, Runway API documentation
```

**Agent Instruction**: Before generating schemas, migrations, or integration code, the agent MUST check the relevant documentation files. Open files directly (via cat/Read) before generating code. When local copies exist, they take priority over web lookups.

### Proactive Documentation Identification

When designing or implementing:
- A new pipeline stage
- A new media integration
- A new metadata mapping
- A new external service client
- Schema changes that map to external APIs

The agent must:
1. Check whether currently loaded documentation is sufficient
2. Identify any missing docs that would reduce ambiguity
3. Recommend adding new URLs or local copies to persistent context

**Examples of documentation the agent should proactively request (if missing):**
- OAuth 2.0 for YouTube desktop/server-side apps
- YouTube upload quotas & error code reference
- FFmpeg safe encoding settings for YouTube (H.264 + AAC constraints)
- ElevenLabs voice settings documentation
- Runway async generation callback docs
- Google API Python client library docs
- MIME type tables for video uploads
- S3/MinIO multipart upload constraints
- Best practices for long-running Celery tasks and monitoring

If the agent identifies a missing doc, it should respond with:

> "Recommendation: Add the following documentation to persistent context: [URL/resource]
> Reason: This resource defines [key fields/constraints] that affect [component]."

This allows the documentation library to expand automatically as ACOG grows.

## Current Development Status

**Phase 1 (Complete):**
- Core backend infrastructure (47 Python files)
- Database schema with 4 core tables (channels, episodes, assets, jobs)
- 17 REST API endpoints
- AI services: PlanningService, ScriptService, MetadataService (all using OpenAI structured output)
- Celery pipeline tasks for planning, scripting, metadata stages
- Docker Compose setup (PostgreSQL, Redis, MinIO)

**Phase 2 (In Progress):**
- Stage 1 pipeline execution (planning → scripting → metadata)
- Frontend dashboard with Next.js
- End-to-end testing

**Running Services:**
- FastAPI: http://localhost:8000 (docs at /docs)
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- MinIO Console: http://localhost:9001

**Common Commands:**
```bash
# Start API server
cd apps/api && poetry run uvicorn acog.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (all queues)
cd apps/api && poetry run celery -A acog.workers.celery_app worker --loglevel=info -Q default,orchestrator,openai,media

# Run migrations
cd apps/api && poetry run alembic upgrade head

# Run smoke test
cd apps/api && poetry run python scripts/manual_smoke_run.py
```

## OpenAI Structured Output Requirements

When creating Pydantic models for OpenAI structured output (response_format), these rules MUST be followed:

1. **ConfigDict required**: All models must have `model_config = ConfigDict(extra="forbid")`
2. **No default values**: Remove all `default=...` and `default_factory=...` from Field definitions
3. **No Optional types for OpenAI**: Change `str | None` to `str` with description indicating "empty string if not applicable"
4. **No bare dict types**: Use proper Pydantic models instead of `dict[str, str]`

Example:
```python
# WRONG - will fail OpenAI validation
class MyModel(BaseModel):
    name: str = Field(default="")
    items: list[str] = Field(default_factory=list)
    meta: dict[str, str] = Field(...)

# CORRECT - passes OpenAI validation
class MyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(description="Name (empty string if not applicable)")
    items: list[str] = Field(description="Items list (empty list if none)")
    meta: list[MetaItem] = Field(description="Metadata items")  # Use proper model
```
