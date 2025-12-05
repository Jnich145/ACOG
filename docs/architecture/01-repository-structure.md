# ACOG Repository Structure

**Document ID:** ARCH-001
**Version:** 1.0
**Last Updated:** 2025-12-05
**Status:** Approved for Implementation

---

## Decision

ACOG will use a **monorepo structure** with clear separation between backend (Python/FastAPI), frontend (Next.js), CLI (Python), and shared resources. This approach enables:

- Unified versioning and releases
- Shared type definitions and contracts
- Simplified CI/CD pipelines
- Atomic changes across components
- Single source of truth for documentation

---

## Reasoning

A monorepo is the right choice for ACOG because:

1. **Tight coupling between components**: The dashboard, CLI, and backend share API contracts, making coordinated changes essential
2. **Small team**: With a single developer or small team, the overhead of managing multiple repos exceeds the benefits
3. **Shared tooling**: Docker Compose, environment configs, and deployment scripts work across all components
4. **API contract enforcement**: Changes to backend endpoints can be validated against frontend/CLI consumers in the same PR

We explicitly reject a polyrepo approach because:
- It would require versioning API contracts separately
- Deployment coordination becomes complex
- Local development requires managing multiple git checkouts

---

## MVP Implementation

### Top-Level Folder Structure

```
acog/
├── .github/                    # GitHub Actions CI/CD workflows
│   └── workflows/
│       ├── ci.yml              # Lint, test, typecheck on PR
│       ├── backend.yml         # Backend-specific checks
│       └── frontend.yml        # Frontend-specific checks
│
├── apps/                       # Deployable applications
│   ├── api/                    # FastAPI backend
│   ├── web/                    # Next.js frontend dashboard
│   └── cli/                    # Python CLI tool
│
├── packages/                   # Shared code (future: shared types)
│   └── shared-types/           # OpenAPI-generated types for frontend
│
├── infra/                      # Infrastructure and deployment
│   ├── docker/                 # Dockerfiles for each service
│   │   ├── api.Dockerfile
│   │   ├── worker.Dockerfile
│   │   └── web.Dockerfile
│   ├── scripts/                # Utility scripts
│   │   ├── setup-dev.sh
│   │   ├── reset-db.sh
│   │   └── seed-data.sh
│   └── k8s/                    # Kubernetes manifests (future)
│
├── docs/                       # Documentation
│   ├── architecture/           # Architecture decision records
│   ├── api/                    # API documentation
│   └── guides/                 # Developer guides
│
├── docker-compose.yml          # Local development orchestration
├── docker-compose.override.yml # Local overrides (gitignored)
├── .env.example                # Example environment variables
├── .gitignore
├── README.md
├── CLAUDE.md                   # Claude Code guidance
└── Makefile                    # Common commands
```

---

### Backend Module Organization (`apps/api/`)

```
apps/api/
├── alembic/                    # Database migrations
│   ├── versions/               # Migration files
│   ├── env.py
│   └── alembic.ini
│
├── src/
│   └── acog/                   # Main application package
│       ├── __init__.py
│       ├── main.py             # FastAPI app entry point
│       │
│       ├── api/                # HTTP layer - routers and endpoints
│       │   ├── __init__.py
│       │   ├── deps.py         # Dependency injection (get_db, get_current_user)
│       │   ├── v1/             # API version 1
│       │   │   ├── __init__.py
│       │   │   ├── router.py   # Main router aggregating all v1 routes
│       │   │   ├── channels.py # Channel CRUD endpoints
│       │   │   ├── episodes.py # Episode CRUD and pipeline triggers
│       │   │   ├── assets.py   # Asset retrieval endpoints
│       │   │   ├── jobs.py     # Job status and management
│       │   │   ├── auth.py     # Authentication endpoints
│       │   │   └── health.py   # Health check endpoints
│       │   └── webhooks/       # External service callbacks
│       │       ├── __init__.py
│       │       ├── heygen.py   # HeyGen completion callbacks
│       │       └── pulse.py    # Pulse event intake
│       │
│       ├── services/           # Business logic layer
│       │   ├── __init__.py
│       │   ├── channel_service.py
│       │   ├── episode_service.py
│       │   ├── asset_service.py
│       │   ├── pipeline_service.py    # Pipeline orchestration logic
│       │   └── planning/              # OpenAI planning domain
│       │       ├── __init__.py
│       │       ├── planner.py         # Episode planning service
│       │       ├── script_generator.py
│       │       ├── script_refiner.py
│       │       └── metadata_generator.py
│       │
│       ├── models/             # SQLAlchemy ORM models
│       │   ├── __init__.py
│       │   ├── base.py         # Base model with common fields
│       │   ├── channel.py
│       │   ├── episode.py
│       │   ├── asset.py
│       │   ├── job.py          # Background job tracking
│       │   ├── user.py
│       │   └── pulse_event.py
│       │
│       ├── schemas/            # Pydantic request/response schemas
│       │   ├── __init__.py
│       │   ├── base.py         # Common schema patterns
│       │   ├── channel.py      # ChannelCreate, ChannelUpdate, ChannelResponse
│       │   ├── episode.py
│       │   ├── asset.py
│       │   ├── job.py
│       │   ├── auth.py
│       │   └── pipeline.py     # Pipeline stage schemas
│       │
│       ├── workers/            # Celery task definitions
│       │   ├── __init__.py
│       │   ├── celery_app.py   # Celery configuration
│       │   ├── planning_tasks.py      # Plan/script generation tasks
│       │   ├── media_tasks.py         # Voice/avatar/B-roll tasks
│       │   ├── assembly_tasks.py      # Video assembly tasks
│       │   └── upload_tasks.py        # YouTube upload tasks
│       │
│       ├── integrations/       # External service clients
│       │   ├── __init__.py
│       │   ├── base.py         # Abstract base client interface
│       │   ├── openai/         # OpenAI integration
│       │   │   ├── __init__.py
│       │   │   ├── client.py   # OpenAI API wrapper
│       │   │   ├── prompts.py  # Prompt templates
│       │   │   └── schemas.py  # Response parsing schemas
│       │   ├── elevenlabs/     # Voice synthesis
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── schemas.py
│       │   ├── heygen/         # Avatar video
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── schemas.py
│       │   ├── runway/         # B-roll generation
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── schemas.py
│       │   ├── storage/        # S3/MinIO abstraction
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── utils.py
│       │   └── youtube/        # YouTube Data API
│       │       ├── __init__.py
│       │       ├── client.py
│       │       └── schemas.py
│       │
│       └── core/               # Application foundation
│           ├── __init__.py
│           ├── config.py       # Settings via pydantic-settings
│           ├── database.py     # SQLAlchemy engine and session
│           ├── security.py     # Password hashing, JWT tokens
│           ├── exceptions.py   # Custom exception classes
│           └── logging.py      # Structured logging setup
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/                   # Unit tests
│   │   ├── services/
│   │   └── integrations/
│   ├── integration/            # Integration tests
│   │   └── api/
│   └── factories/              # Test data factories
│       └── factories.py
│
├── pyproject.toml              # Python project configuration
├── poetry.lock                 # Locked dependencies
├── pytest.ini                  # Pytest configuration
└── README.md
```

---

### Frontend Structure (`apps/web/`)

```
apps/web/
├── public/
│   ├── favicon.ico
│   └── images/
│
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Home/dashboard page
│   │   ├── globals.css
│   │   │
│   │   ├── (auth)/             # Auth route group
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   └── layout.tsx
│   │   │
│   │   ├── (dashboard)/        # Protected dashboard routes
│   │   │   ├── layout.tsx      # Dashboard shell with sidebar
│   │   │   ├── channels/
│   │   │   │   ├── page.tsx           # Channel list
│   │   │   │   ├── new/
│   │   │   │   │   └── page.tsx       # Create channel
│   │   │   │   └── [channelId]/
│   │   │   │       ├── page.tsx       # Channel detail
│   │   │   │       └── edit/
│   │   │   │           └── page.tsx   # Edit channel
│   │   │   │
│   │   │   ├── episodes/
│   │   │   │   ├── page.tsx           # Episode list
│   │   │   │   ├── new/
│   │   │   │   │   └── page.tsx       # Create episode
│   │   │   │   └── [episodeId]/
│   │   │   │       ├── page.tsx       # Episode detail & pipeline view
│   │   │   │       └── edit/
│   │   │   │           └── page.tsx   # Edit episode
│   │   │   │
│   │   │   ├── jobs/
│   │   │   │   └── page.tsx           # Job queue view
│   │   │   │
│   │   │   └── settings/
│   │   │       └── page.tsx           # User/system settings
│   │   │
│   │   └── api/                # Next.js API routes (if needed)
│   │       └── auth/
│   │           └── [...nextauth]/
│   │               └── route.ts
│   │
│   ├── components/             # Reusable UI components
│   │   ├── ui/                 # Primitive components (shadcn/ui style)
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── select.tsx
│   │   │   ├── table.tsx
│   │   │   └── ...
│   │   │
│   │   ├── layout/             # Layout components
│   │   │   ├── sidebar.tsx
│   │   │   ├── header.tsx
│   │   │   └── nav-link.tsx
│   │   │
│   │   ├── channels/           # Channel-specific components
│   │   │   ├── channel-card.tsx
│   │   │   ├── channel-form.tsx
│   │   │   └── persona-editor.tsx
│   │   │
│   │   ├── episodes/           # Episode-specific components
│   │   │   ├── episode-card.tsx
│   │   │   ├── episode-form.tsx
│   │   │   ├── pipeline-status.tsx
│   │   │   ├── script-editor.tsx
│   │   │   └── asset-viewer.tsx
│   │   │
│   │   └── common/             # Shared application components
│   │       ├── loading.tsx
│   │       ├── error-boundary.tsx
│   │       └── status-badge.tsx
│   │
│   ├── lib/                    # Utilities and helpers
│   │   ├── api-client.ts       # Typed API client (fetch wrapper)
│   │   ├── auth.ts             # Auth utilities
│   │   ├── utils.ts            # General utilities
│   │   └── constants.ts        # Application constants
│   │
│   ├── hooks/                  # Custom React hooks
│   │   ├── use-channels.ts     # Channel data fetching
│   │   ├── use-episodes.ts     # Episode data fetching
│   │   ├── use-jobs.ts         # Job status polling
│   │   └── use-auth.ts         # Authentication state
│   │
│   ├── types/                  # TypeScript type definitions
│   │   ├── api.ts              # API response types
│   │   ├── channel.ts
│   │   ├── episode.ts
│   │   └── index.ts
│   │
│   └── styles/                 # Additional styles
│       └── components.css
│
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
├── package.json
├── package-lock.json
└── README.md
```

---

### CLI Structure (`apps/cli/`)

```
apps/cli/
├── src/
│   └── acog_cli/
│       ├── __init__.py
│       ├── main.py             # Typer app entry point
│       │
│       ├── commands/           # CLI command groups
│       │   ├── __init__.py
│       │   ├── auth.py         # Login, logout, whoami
│       │   ├── channels.py     # Channel CRUD commands
│       │   ├── episodes.py     # Episode CRUD and pipeline commands
│       │   ├── jobs.py         # Job status and management
│       │   └── assets.py       # Asset download commands
│       │
│       ├── api/                # API client
│       │   ├── __init__.py
│       │   ├── client.py       # HTTP client with auth
│       │   └── models.py       # Response models
│       │
│       ├── config/             # CLI configuration
│       │   ├── __init__.py
│       │   └── settings.py     # Config file handling
│       │
│       └── utils/              # CLI utilities
│           ├── __init__.py
│           ├── output.py       # Rich console output
│           └── prompts.py      # Interactive prompts
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_commands.py
│
├── pyproject.toml
└── README.md
```

---

## Docker Compose Configuration

### `docker-compose.yml` (Production-like defaults)

```yaml
version: "3.8"

services:
  # =============================================================================
  # PostgreSQL Database
  # =============================================================================
  postgres:
    image: postgres:16-alpine
    container_name: acog-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-acog}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-acog_dev_password}
      POSTGRES_DB: ${POSTGRES_DB:-acog}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-acog}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # =============================================================================
  # Redis (Celery broker + caching)
  # =============================================================================
  redis:
    image: redis:7-alpine
    container_name: acog-redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # =============================================================================
  # MinIO (S3-compatible object storage)
  # =============================================================================
  minio:
    image: minio/minio:latest
    container_name: acog-minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-acog_minio}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-acog_minio_secret}
    volumes:
      - minio_data:/data
    ports:
      - "${MINIO_API_PORT:-9000}:9000"
      - "${MINIO_CONSOLE_PORT:-9001}:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3

  # =============================================================================
  # MinIO bucket initialization
  # =============================================================================
  minio-init:
    image: minio/mc:latest
    container_name: acog-minio-init
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set acog http://minio:9000 ${MINIO_ROOT_USER:-acog_minio} ${MINIO_ROOT_PASSWORD:-acog_minio_secret};
      mc mb --ignore-existing acog/acog-assets;
      mc mb --ignore-existing acog/acog-scripts;
      mc anonymous set download acog/acog-assets;
      exit 0;
      "

  # =============================================================================
  # FastAPI Backend
  # =============================================================================
  api:
    build:
      context: .
      dockerfile: infra/docker/api.Dockerfile
    container_name: acog-api
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-acog}:${POSTGRES_PASSWORD:-acog_dev_password}@postgres:5432/${POSTGRES_DB:-acog}
      - REDIS_URL=redis://redis:6379/0
      - S3_ENDPOINT_URL=http://minio:9000
      - S3_ACCESS_KEY=${MINIO_ROOT_USER:-acog_minio}
      - S3_SECRET_KEY=${MINIO_ROOT_PASSWORD:-acog_minio_secret}
      - S3_BUCKET_ASSETS=acog-assets
      - S3_BUCKET_SCRIPTS=acog-scripts
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
      - HEYGEN_API_KEY=${HEYGEN_API_KEY}
      - RUNWAY_API_KEY=${RUNWAY_API_KEY}
      - SECRET_KEY=${SECRET_KEY:-dev-secret-key-change-in-production}
      - ENVIRONMENT=${ENVIRONMENT:-development}
    volumes:
      - ./apps/api/src:/app/src:ro
    ports:
      - "${API_PORT:-8000}:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # =============================================================================
  # Celery Worker
  # =============================================================================
  worker:
    build:
      context: .
      dockerfile: infra/docker/worker.Dockerfile
    container_name: acog-worker
    restart: unless-stopped
    command: celery -A acog.workers.celery_app worker --loglevel=info --concurrency=2
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-acog}:${POSTGRES_PASSWORD:-acog_dev_password}@postgres:5432/${POSTGRES_DB:-acog}
      - REDIS_URL=redis://redis:6379/0
      - S3_ENDPOINT_URL=http://minio:9000
      - S3_ACCESS_KEY=${MINIO_ROOT_USER:-acog_minio}
      - S3_SECRET_KEY=${MINIO_ROOT_PASSWORD:-acog_minio_secret}
      - S3_BUCKET_ASSETS=acog-assets
      - S3_BUCKET_SCRIPTS=acog-scripts
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
      - HEYGEN_API_KEY=${HEYGEN_API_KEY}
      - RUNWAY_API_KEY=${RUNWAY_API_KEY}
    volumes:
      - ./apps/api/src:/app/src:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  # =============================================================================
  # Celery Beat (Scheduler)
  # =============================================================================
  beat:
    build:
      context: .
      dockerfile: infra/docker/worker.Dockerfile
    container_name: acog-beat
    restart: unless-stopped
    command: celery -A acog.workers.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-acog}:${POSTGRES_PASSWORD:-acog_dev_password}@postgres:5432/${POSTGRES_DB:-acog}
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./apps/api/src:/app/src:ro
    depends_on:
      - worker

  # =============================================================================
  # Next.js Frontend (Development)
  # =============================================================================
  web:
    build:
      context: .
      dockerfile: infra/docker/web.Dockerfile
      target: development
    container_name: acog-web
    restart: unless-stopped
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:${API_PORT:-8000}
      - NEXTAUTH_URL=http://localhost:${WEB_PORT:-3000}
      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET:-dev-nextauth-secret}
    volumes:
      - ./apps/web/src:/app/src:ro
      - ./apps/web/public:/app/public:ro
    ports:
      - "${WEB_PORT:-3000}:3000"
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### `docker-compose.override.yml` (Local development - gitignored)

```yaml
version: "3.8"

# Override for local development with hot reload
services:
  api:
    volumes:
      - ./apps/api/src:/app/src
    command: uvicorn acog.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      - DEBUG=true

  worker:
    volumes:
      - ./apps/api/src:/app/src
    command: watchmedo auto-restart --directory=/app/src --pattern="*.py" --recursive -- celery -A acog.workers.celery_app worker --loglevel=debug

  web:
    volumes:
      - ./apps/web/src:/app/src
      - ./apps/web/public:/app/public
```

---

## Dockerfiles

### `infra/docker/api.Dockerfile`

```dockerfile
# =============================================================================
# ACOG API Dockerfile
# =============================================================================
FROM python:3.12-slim as base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Dependencies stage
# =============================================================================
FROM base as dependencies

# Install Poetry
RUN pip install poetry==1.7.1
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Copy dependency files
COPY apps/api/pyproject.toml apps/api/poetry.lock* ./

# Install dependencies
RUN poetry install --no-root --only main

# =============================================================================
# Production stage
# =============================================================================
FROM base as production

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY apps/api/src /app/src
COPY apps/api/alembic /app/alembic
COPY apps/api/alembic.ini /app/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Set Python path
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "acog.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `infra/docker/worker.Dockerfile`

```dockerfile
# =============================================================================
# ACOG Worker Dockerfile
# =============================================================================
FROM python:3.12-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies (includes ffmpeg for video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Dependencies stage
# =============================================================================
FROM base as dependencies

RUN pip install poetry==1.7.1
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

COPY apps/api/pyproject.toml apps/api/poetry.lock* ./

# Install all dependencies including worker extras
RUN poetry install --no-root --only main --extras worker

# =============================================================================
# Production stage
# =============================================================================
FROM base as production

COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

COPY apps/api/src /app/src

RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH=/app/src

CMD ["celery", "-A", "acog.workers.celery_app", "worker", "--loglevel=info"]
```

### `infra/docker/web.Dockerfile`

```dockerfile
# =============================================================================
# ACOG Web Dockerfile
# =============================================================================
FROM node:20-alpine AS base

WORKDIR /app

# =============================================================================
# Dependencies stage
# =============================================================================
FROM base AS dependencies

COPY apps/web/package.json apps/web/package-lock.json* ./

RUN npm ci

# =============================================================================
# Development stage
# =============================================================================
FROM base AS development

COPY --from=dependencies /app/node_modules ./node_modules
COPY apps/web .

EXPOSE 3000

ENV NODE_ENV=development
CMD ["npm", "run", "dev"]

# =============================================================================
# Builder stage
# =============================================================================
FROM base AS builder

COPY --from=dependencies /app/node_modules ./node_modules
COPY apps/web .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# =============================================================================
# Production stage
# =============================================================================
FROM base AS production

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

---

## Environment Variable Management

### `.env.example`

```bash
# =============================================================================
# ACOG Environment Configuration
# =============================================================================
# Copy this file to .env and fill in your values
# NEVER commit .env to version control
# =============================================================================

# -----------------------------------------------------------------------------
# Environment
# -----------------------------------------------------------------------------
ENVIRONMENT=development
DEBUG=true

# -----------------------------------------------------------------------------
# Security
# -----------------------------------------------------------------------------
SECRET_KEY=your-secret-key-at-least-32-characters-long
NEXTAUTH_SECRET=your-nextauth-secret-at-least-32-chars

# -----------------------------------------------------------------------------
# Database (PostgreSQL)
# -----------------------------------------------------------------------------
POSTGRES_USER=acog
POSTGRES_PASSWORD=acog_dev_password
POSTGRES_DB=acog
POSTGRES_PORT=5432
DATABASE_URL=postgresql://acog:acog_dev_password@localhost:5432/acog

# -----------------------------------------------------------------------------
# Redis
# -----------------------------------------------------------------------------
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379/0

# -----------------------------------------------------------------------------
# Object Storage (MinIO/S3)
# -----------------------------------------------------------------------------
MINIO_ROOT_USER=acog_minio
MINIO_ROOT_PASSWORD=acog_minio_secret
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=acog_minio
S3_SECRET_KEY=acog_minio_secret
S3_BUCKET_ASSETS=acog-assets
S3_BUCKET_SCRIPTS=acog-scripts

# -----------------------------------------------------------------------------
# API Service
# -----------------------------------------------------------------------------
API_PORT=8000
API_URL=http://localhost:8000

# -----------------------------------------------------------------------------
# Web Service
# -----------------------------------------------------------------------------
WEB_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_URL=http://localhost:3000

# -----------------------------------------------------------------------------
# AI/LLM - OpenAI
# -----------------------------------------------------------------------------
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL_PLANNING=gpt-4o
OPENAI_MODEL_SCRIPTING=gpt-4o-mini
OPENAI_MODEL_METADATA=gpt-4o-mini

# -----------------------------------------------------------------------------
# Media Providers
# -----------------------------------------------------------------------------
# ElevenLabs (Voice Synthesis)
ELEVENLABS_API_KEY=your-elevenlabs-api-key

# HeyGen (Avatar Video)
HEYGEN_API_KEY=your-heygen-api-key

# Runway (B-roll Generation)
RUNWAY_API_KEY=your-runway-api-key

# -----------------------------------------------------------------------------
# Publishing
# -----------------------------------------------------------------------------
# YouTube OAuth credentials (see docs for setup)
YOUTUBE_CLIENT_ID=your-youtube-client-id
YOUTUBE_CLIENT_SECRET=your-youtube-client-secret
```

### Environment Loading Strategy

**Backend (`apps/api/src/acog/core/config.py`):**

```python
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Security
    secret_key: str = Field(..., min_length=32)
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    # Database
    database_url: PostgresDsn

    # Redis
    redis_url: RedisDsn

    # S3/MinIO
    s3_endpoint_url: str | None = None  # None for real AWS S3
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_assets: str = "acog-assets"
    s3_bucket_scripts: str = "acog-scripts"
    s3_region: str = "us-east-1"

    # OpenAI
    openai_api_key: str
    openai_model_planning: str = "gpt-4o"
    openai_model_scripting: str = "gpt-4o-mini"
    openai_model_metadata: str = "gpt-4o-mini"

    # Media Providers
    elevenlabs_api_key: str | None = None
    heygen_api_key: str | None = None
    runway_api_key: str | None = None

    # YouTube
    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None

    @computed_field
    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### Secret Management Philosophy

| Environment | Approach |
|------------|----------|
| **Local Dev** | `.env` file (gitignored), populated from `.env.example` |
| **CI/CD** | GitHub Actions secrets, injected as environment variables |
| **Staging** | AWS Secrets Manager or similar, injected at container runtime |
| **Production** | AWS Secrets Manager with IAM roles, secrets fetched at startup |

**Rules:**
1. Never commit secrets to git
2. Use different secrets per environment
3. Rotate secrets regularly (implement rotation automation in Phase 5)
4. Audit secret access

---

## CI/CD Pipeline Structure

### `.github/workflows/ci.yml` (Main CI Pipeline)

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  PYTHON_VERSION: "3.12"
  NODE_VERSION: "20"

jobs:
  # ===========================================================================
  # Detect changes to optimize CI runs
  # ===========================================================================
  changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
      cli: ${{ steps.filter.outputs.cli }}
      infra: ${{ steps.filter.outputs.infra }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v2
        id: filter
        with:
          filters: |
            backend:
              - 'apps/api/**'
              - 'pyproject.toml'
            frontend:
              - 'apps/web/**'
            cli:
              - 'apps/cli/**'
            infra:
              - 'infra/**'
              - 'docker-compose.yml'

  # ===========================================================================
  # Backend: Lint, Type Check, Test
  # ===========================================================================
  backend:
    needs: changes
    if: needs.changes.outputs.backend == 'true'
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/api

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: 1.7.1
          virtualenvs-create: true
          virtualenvs-in-project: true

      - name: Load cached venv
        id: cached-poetry-dependencies
        uses: actions/cache@v4
        with:
          path: apps/api/.venv
          key: venv-${{ runner.os }}-${{ env.PYTHON_VERSION }}-${{ hashFiles('apps/api/poetry.lock') }}

      - name: Install dependencies
        if: steps.cached-poetry-dependencies.outputs.cache-hit != 'true'
        run: poetry install --no-interaction --no-root

      - name: Install project
        run: poetry install --no-interaction

      - name: Run Ruff linter
        run: poetry run ruff check src tests

      - name: Run Ruff formatter check
        run: poetry run ruff format --check src tests

      - name: Run type checking
        run: poetry run mypy src

      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: test-secret-key-for-ci-minimum-32-chars
          OPENAI_API_KEY: sk-test-key
          S3_ACCESS_KEY: test
          S3_SECRET_KEY: test
        run: poetry run pytest --cov=src --cov-report=xml --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: apps/api/coverage.xml
          flags: backend

  # ===========================================================================
  # Frontend: Lint, Type Check, Build
  # ===========================================================================
  frontend:
    needs: changes
    if: needs.changes.outputs.frontend == 'true'
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: "npm"
          cache-dependency-path: apps/web/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Run ESLint
        run: npm run lint

      - name: Run type checking
        run: npm run typecheck

      - name: Run tests
        run: npm run test -- --passWithNoTests

      - name: Build
        run: npm run build
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000

  # ===========================================================================
  # CLI: Lint, Type Check, Test
  # ===========================================================================
  cli:
    needs: changes
    if: needs.changes.outputs.cli == 'true'
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/cli

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: 1.7.1
          virtualenvs-create: true
          virtualenvs-in-project: true

      - name: Load cached venv
        id: cached-poetry-dependencies
        uses: actions/cache@v4
        with:
          path: apps/cli/.venv
          key: venv-${{ runner.os }}-${{ env.PYTHON_VERSION }}-${{ hashFiles('apps/cli/poetry.lock') }}

      - name: Install dependencies
        if: steps.cached-poetry-dependencies.outputs.cache-hit != 'true'
        run: poetry install --no-interaction --no-root

      - name: Install project
        run: poetry install --no-interaction

      - name: Run Ruff linter
        run: poetry run ruff check src tests

      - name: Run type checking
        run: poetry run mypy src

      - name: Run tests
        run: poetry run pytest

  # ===========================================================================
  # Docker Build Test
  # ===========================================================================
  docker:
    needs: changes
    if: needs.changes.outputs.infra == 'true' || needs.changes.outputs.backend == 'true' || needs.changes.outputs.frontend == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build API image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: infra/docker/api.Dockerfile
          push: false
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build Worker image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: infra/docker/worker.Dockerfile
          push: false
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build Web image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: infra/docker/web.Dockerfile
          target: production
          push: false
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## Python Project Configuration

### `apps/api/pyproject.toml`

```toml
[tool.poetry]
name = "acog-api"
version = "0.1.0"
description = "ACOG Backend API - Automated Content Orchestration & Generation Engine"
authors = ["Justin Nichols"]
readme = "README.md"
packages = [{include = "acog", from = "src"}]

[tool.poetry.dependencies]
python = "^3.12"

# Web Framework
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"

# Database
sqlalchemy = "^2.0.25"
alembic = "^1.13.0"
asyncpg = "^0.29.0"
psycopg2-binary = "^2.9.9"

# Task Queue
celery = {extras = ["redis"], version = "^5.3.0"}
redis = "^5.0.0"

# Object Storage
boto3 = "^1.34.0"

# AI/LLM
openai = "^1.10.0"

# HTTP Client
httpx = "^0.26.0"

# Auth & Security
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-multipart = "^0.0.6"

# Utilities
python-dotenv = "^1.0.0"
structlog = "^24.1.0"

[tool.poetry.group.dev.dependencies]
# Testing
pytest = "^8.0.0"
pytest-cov = "^4.1.0"
pytest-asyncio = "^0.23.0"
httpx = "^0.26.0"
factory-boy = "^3.3.0"

# Linting & Formatting
ruff = "^0.2.0"
mypy = "^1.8.0"

# Type stubs
types-redis = "^4.6.0"
types-passlib = "^1.7.7"
boto3-stubs = {extras = ["s3"], version = "^1.34.0"}

# Development
watchdog = "^4.0.0"

[tool.poetry.extras]
worker = ["watchdog"]

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

# =============================================================================
# Ruff Configuration
# =============================================================================
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # Pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
    "ARG",  # flake8-unused-arguments
    "SIM",  # flake8-simplify
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "B008",   # do not perform function calls in argument defaults
]

[tool.ruff.lint.isort]
known-first-party = ["acog"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ARG"]

# =============================================================================
# MyPy Configuration
# =============================================================================
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["celery.*", "boto3.*", "botocore.*"]
ignore_missing_imports = true

# =============================================================================
# Pytest Configuration
# =============================================================================
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = [
    "ignore::DeprecationWarning",
]
addopts = "-v --tb=short"

# =============================================================================
# Coverage Configuration
# =============================================================================
[tool.coverage.run]
source = ["src"]
branch = true
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

---

## Makefile

```makefile
# =============================================================================
# ACOG Makefile - Common Development Commands
# =============================================================================

.PHONY: help install dev up down logs test lint format migrate seed clean

# Default target
help:
	@echo "ACOG Development Commands"
	@echo "========================="
	@echo ""
	@echo "Setup:"
	@echo "  make install     - Install all dependencies"
	@echo "  make dev         - Start development environment"
	@echo ""
	@echo "Docker:"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - Tail service logs"
	@echo "  make rebuild     - Rebuild and restart services"
	@echo ""
	@echo "Database:"
	@echo "  make migrate     - Run database migrations"
	@echo "  make seed        - Seed database with sample data"
	@echo "  make reset-db    - Reset database (destructive!)"
	@echo ""
	@echo "Quality:"
	@echo "  make test        - Run all tests"
	@echo "  make lint        - Run linters"
	@echo "  make format      - Format code"
	@echo "  make typecheck   - Run type checking"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       - Remove generated files"

# =============================================================================
# Setup
# =============================================================================

install:
	@echo "Installing backend dependencies..."
	cd apps/api && poetry install
	@echo "Installing CLI dependencies..."
	cd apps/cli && poetry install
	@echo "Installing frontend dependencies..."
	cd apps/web && npm install
	@echo "Copying environment file..."
	cp -n .env.example .env 2>/dev/null || true
	@echo "Done! Edit .env with your API keys."

dev: up
	@echo "Development environment started."
	@echo "  API:     http://localhost:8000"
	@echo "  Web:     http://localhost:3000"
	@echo "  MinIO:   http://localhost:9001"
	@echo "  Docs:    http://localhost:8000/docs"

# =============================================================================
# Docker
# =============================================================================

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d

# Service-specific logs
logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

logs-web:
	docker compose logs -f web

# =============================================================================
# Database
# =============================================================================

migrate:
	docker compose exec api alembic upgrade head

migrate-create:
	@read -p "Migration message: " msg; \
	docker compose exec api alembic revision --autogenerate -m "$$msg"

seed:
	docker compose exec api python -m acog.scripts.seed

reset-db:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " confirm; \
	if [ "$$confirm" = "y" ]; then \
		docker compose down -v; \
		docker compose up -d postgres redis minio minio-init; \
		sleep 5; \
		docker compose up -d; \
		make migrate; \
		echo "Database reset complete."; \
	fi

# =============================================================================
# Quality Checks
# =============================================================================

test:
	cd apps/api && poetry run pytest
	cd apps/cli && poetry run pytest
	cd apps/web && npm test -- --passWithNoTests

test-api:
	cd apps/api && poetry run pytest -v

test-cli:
	cd apps/cli && poetry run pytest -v

test-web:
	cd apps/web && npm test

lint:
	cd apps/api && poetry run ruff check src tests
	cd apps/cli && poetry run ruff check src tests
	cd apps/web && npm run lint

format:
	cd apps/api && poetry run ruff format src tests
	cd apps/cli && poetry run ruff format src tests
	cd apps/web && npm run lint -- --fix

typecheck:
	cd apps/api && poetry run mypy src
	cd apps/cli && poetry run mypy src
	cd apps/web && npm run typecheck

# =============================================================================
# CLI
# =============================================================================

cli:
	cd apps/cli && poetry run acog

# =============================================================================
# Cleanup
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned generated files."
```

---

## Future Extensions

### Phase 2+ Enhancements

| Area | Enhancement | Priority |
|------|-------------|----------|
| **Packages** | `packages/shared-types/` - OpenAPI-generated TypeScript types shared between frontend and CLI | High |
| **Packages** | `packages/sdk/` - Python SDK for ACOG API (used by CLI and external integrations) | Medium |
| **Testing** | `apps/api/tests/e2e/` - End-to-end pipeline tests with mocked external services | High |
| **Infra** | `infra/k8s/` - Kubernetes manifests for production deployment | Medium |
| **Infra** | `infra/terraform/` - Infrastructure as Code for AWS/GCP resources | Medium |
| **Monitoring** | `infra/monitoring/` - Prometheus, Grafana, and alerting configs | High |
| **Docs** | `docs/api/openapi.yml` - Auto-generated OpenAPI specification | High |

### Monorepo Tooling Evolution

**MVP (Now):**
- Simple folder structure with independent package managers
- Manual coordination via Makefile
- Shared `.env` at root

**Future:**
- Consider `turborepo` or `nx` for optimized builds and caching
- Consider `pants` or `bazel` for Python monorepo management
- Add `changesets` for versioning and changelogs

### Repository Structure Evolution

```
acog/                           # Future state
├── apps/
│   ├── api/
│   ├── web/
│   ├── cli/
│   └── docs/                   # Docusaurus or similar for docs site
│
├── packages/
│   ├── shared-types/           # OpenAPI-generated types
│   ├── sdk-python/             # Python SDK
│   ├── sdk-typescript/         # TypeScript SDK (future)
│   └── ui/                     # Shared UI component library
│
├── infra/
│   ├── docker/
│   ├── k8s/
│   ├── terraform/
│   └── monitoring/
│
└── tools/                      # Development tooling
    ├── scripts/
    └── generators/             # Code generators
```

---

## Trade-offs

### What We Gain

1. **Single source of truth** - All code, configs, and docs in one place
2. **Atomic changes** - API and consumer changes in single PRs
3. **Simplified CI/CD** - One pipeline with smart path filtering
4. **Shared tooling** - Docker Compose, env files, Makefile work everywhere
5. **Developer experience** - Clone once, run everything

### What We Give Up

1. **Independent versioning** - Components share version (mitigated by semantic versioning)
2. **Selective access** - Everyone with repo access sees all code (acceptable for small team)
3. **Build isolation** - Changes to shared code affect all consumers (mitigated by path-based CI)

### Key Constraints

1. **Git performance** - Monorepos can slow down with large binary assets
   - Mitigation: Use Git LFS for any large files, keep assets in S3
2. **CI time** - Full builds take longer
   - Mitigation: Path-based job triggering, build caching
3. **Learning curve** - Developers must understand the whole structure
   - Mitigation: Clear documentation, consistent conventions

---

## Next Steps

### Immediate (Sprint 0)

1. [ ] Initialize repository with folder structure
2. [ ] Set up `apps/api/` with FastAPI skeleton and health endpoint
3. [ ] Set up `apps/web/` with Next.js skeleton
4. [ ] Set up `apps/cli/` with Typer skeleton
5. [ ] Create Docker Compose configuration
6. [ ] Set up GitHub Actions CI pipeline
7. [ ] Write initial README with setup instructions

### Following Sprint (Sprint 1)

1. [ ] Implement backend core module (`config.py`, `database.py`, `security.py`)
2. [ ] Create initial Alembic migrations for Channel and Episode models
3. [ ] Implement Channel CRUD endpoints
4. [ ] Create frontend dashboard shell with routing
5. [ ] Implement CLI auth and channel commands

---

## Appendix: File Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Python modules | `snake_case.py` | `channel_service.py` |
| Python classes | `PascalCase` | `ChannelService` |
| TypeScript files | `kebab-case.tsx` | `channel-form.tsx` |
| React components | `PascalCase` | `ChannelForm` |
| Database tables | `snake_case` (plural) | `channels`, `episodes` |
| API endpoints | `kebab-case` (plural) | `/api/v1/channels` |
| Environment vars | `SCREAMING_SNAKE_CASE` | `DATABASE_URL` |
| Docker services | `kebab-case` | `acog-api` |

---

*This document is part of the ACOG Architecture Decision Records. Changes should be reviewed and approved before implementation.*
