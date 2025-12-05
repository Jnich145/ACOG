# ACOG API

Backend API for the Automated Content Orchestration & Generation Engine.

## Overview

ACOG API is a FastAPI-based backend that provides:

- Channel management with AI personas
- Episode creation and pipeline orchestration
- Integration with OpenAI, ElevenLabs, HeyGen, and Runway
- Async task processing with Celery
- S3/MinIO object storage for assets

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- MinIO (for local development) or AWS S3

### Setup

1. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install dependencies**:
   ```bash
   cd apps/api
   poetry install
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start services** (PostgreSQL, Redis, MinIO):
   ```bash
   # From the repository root
   docker compose up -d postgres redis minio
   ```

5. **Run database migrations**:
   ```bash
   poetry run alembic upgrade head
   ```

6. **Start the API**:
   ```bash
   poetry run uvicorn acog.main:app --reload
   ```

The API will be available at http://localhost:8000

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Project Structure

```
apps/api/
├── alembic/                    # Database migrations
│   ├── versions/               # Migration files
│   └── env.py                  # Migration environment
├── src/
│   └── acog/                   # Main application package
│       ├── api/                # HTTP layer - routers and endpoints
│       │   └── v1/             # API version 1
│       ├── core/               # Application foundation
│       │   ├── config.py       # Settings via pydantic-settings
│       │   ├── database.py     # SQLAlchemy engine and session
│       │   ├── security.py     # JWT tokens, password hashing
│       │   ├── exceptions.py   # Custom exception classes
│       │   └── dependencies.py # FastAPI dependency injection
│       ├── models/             # SQLAlchemy ORM models
│       ├── schemas/            # Pydantic request/response schemas
│       ├── services/           # Business logic layer (Phase 2)
│       ├── workers/            # Celery tasks (Phase 2)
│       └── integrations/       # External API clients (Phase 2)
├── tests/                      # Test suite
├── pyproject.toml              # Python project configuration
├── Dockerfile                  # Multi-stage Docker build
└── .env.example                # Example environment variables
```

## API Endpoints

### Health
- `GET /api/v1/health` - Full health check
- `GET /api/v1/health/live` - Liveness probe
- `GET /api/v1/health/ready` - Readiness probe

### Authentication
- `POST /api/v1/auth/login` - Get access token
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user

### Channels
- `POST /api/v1/channels` - Create channel
- `GET /api/v1/channels` - List channels
- `GET /api/v1/channels/{id}` - Get channel
- `PUT /api/v1/channels/{id}` - Update channel
- `DELETE /api/v1/channels/{id}` - Delete channel

### Episodes
- `POST /api/v1/episodes` - Create episode
- `GET /api/v1/episodes` - List episodes
- `GET /api/v1/episodes/{id}` - Get episode
- `PUT /api/v1/episodes/{id}` - Update episode
- `DELETE /api/v1/episodes/{id}` - Delete episode
- `POST /api/v1/episodes/{id}/cancel` - Cancel episode

### Assets
- `GET /api/v1/assets` - List assets
- `GET /api/v1/assets/{id}` - Get asset
- `GET /api/v1/assets/{id}/download` - Get download URL
- `DELETE /api/v1/assets/{id}` - Delete asset

### Jobs
- `GET /api/v1/jobs` - List jobs
- `GET /api/v1/jobs/{id}` - Get job
- `POST /api/v1/jobs/{id}/cancel` - Cancel job
- `POST /api/v1/jobs/{id}/retry` - Retry job

### Pipeline
- `POST /api/v1/pipeline/episodes/{id}/trigger` - Trigger stage
- `POST /api/v1/pipeline/episodes/{id}/advance` - Advance pipeline
- `GET /api/v1/pipeline/episodes/{id}/status` - Get pipeline status

## Development

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test file
poetry run pytest tests/test_channels.py -v
```

### Code Quality

```bash
# Lint code
poetry run ruff check src tests

# Format code
poetry run ruff format src tests

# Type checking
poetry run mypy src
```

### Database Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1

# View migration history
poetry run alembic history
```

## Docker

### Build Image

```bash
# Development image
docker build --target development -t acog-api:dev .

# Production image
docker build --target production -t acog-api:prod .
```

### Run Container

```bash
docker run -p 8000:8000 --env-file .env acog-api:prod
```

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - JWT signing key (min 32 characters)
- `OPENAI_API_KEY` - OpenAI API key
- `S3_*` - Object storage configuration

## Contributing

1. Create a feature branch from `develop`
2. Make your changes with proper tests
3. Run linting and type checking
4. Submit a pull request

## License

Proprietary - All rights reserved
