# ACOG

**Automated Content Orchestration & Generation** is an experimental stack by [Justin Nichols](https://github.com/Jnich145) for coordinating channels, episode plans, scripts, metadata, and generated media assets.

It combines a FastAPI backend, Celery workers, and a Next.js dashboard. This is development code, not a claim of an operating publishing service or production-ready media pipeline.

## Repository map

| Component | Responsibility |
| --- | --- |
| [API](apps/api/README.md) | Channels, episodes, jobs, assets, and pipeline endpoints |
| [Dashboard](apps/dashboard/README.md) | Channel/episode views and pipeline controls |
| [Worker tasks](apps/api/src/acog/workers/tasks/pipeline.py) | Planning, scripting, metadata, and media stages |
| [Provider clients](apps/api/src/acog/integrations) | OpenAI, ElevenLabs, HeyGen, Runway, and object storage adapters |
| [Development services](docker-compose.yml) | PostgreSQL, Redis, and MinIO |

The code supports placeholder media with `MEDIA_MODE=fake`, the default in [settings](apps/api/src/acog/core/config.py). That setting applies to media stages; it does not make text planning, scripting, and metadata generation offline or free of provider calls.

## Local development starting point

The API declares Python `>=3.12,<3.14` and uses Poetry. The dashboard uses npm with a committed package lock. Install the required tools before following the component guides.

```bash
git clone https://github.com/Jnich145/ACOG.git
cd ACOG
cp apps/api/.env.example apps/api/.env
cp apps/dashboard/.env.example apps/dashboard/.env.local
```

Edit the local environment files with your own development settings. The example provider keys are placeholders. Set a unique `SECRET_KEY`, review the database/storage settings, and choose the intended media mode.

The Compose file starts infrastructure only; it does not launch the API, worker, or dashboard:

```bash
docker compose up -d postgres redis minio minio-init
```

Its ports are published with development credentials, and the initialization service makes the asset bucket anonymously downloadable. Use a disposable local environment with synthetic data; this file is not a production deployment configuration.

In separate terminals, from the repository root:

```bash
# API
cd apps/api
poetry install
poetry run alembic upgrade head
poetry run uvicorn acog.main:app --reload
```

```bash
# Worker
cd apps/api
poetry run celery -A acog.workers.celery_app:celery_app worker --loglevel=info
```

```bash
# Dashboard
cd apps/dashboard
npm ci
npm run dev
```

The configured defaults are API `http://localhost:8000` and dashboard `http://localhost:3000`. These commands match repository entry points; the complete stack and live provider integrations were not run during this documentation refresh.

## Validation and current limits

The API contains pytest coverage and lint/type-check configuration; the dashboard exposes lint and type-check scripts. See the component guides for commands. A result should identify the command, revision, and configured dependencies rather than infer passing tests from their presence.

- Live provider compatibility, generated media quality, and end-to-end publishing require separate verification.
- Fake media is a workflow-development aid, not completed production content.
- Deployment hardening and authenticated storage need work before handling real customer data.
- Existing component documentation and licensing statements remain in place. This overview does not assign new rights or company ownership.
