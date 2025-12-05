"""
API v1 router aggregation.

This module combines all v1 API routers into a single router
that is mounted at /api/v1.
"""

from fastapi import APIRouter

from acog.api.v1.assets import router as assets_router
from acog.api.v1.auth import router as auth_router
from acog.api.v1.channels import router as channels_router
from acog.api.v1.episodes import router as episodes_router
from acog.api.v1.health import router as health_router
from acog.api.v1.jobs import router as jobs_router
from acog.api.v1.pipeline import router as pipeline_router

api_router = APIRouter()

# Include all routers with their prefixes and tags
api_router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"],
)
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"],
)
api_router.include_router(
    channels_router,
    prefix="/channels",
    tags=["Channels"],
)
api_router.include_router(
    episodes_router,
    prefix="/episodes",
    tags=["Episodes"],
)
api_router.include_router(
    assets_router,
    prefix="/assets",
    tags=["Assets"],
)
api_router.include_router(
    jobs_router,
    prefix="/jobs",
    tags=["Jobs"],
)
api_router.include_router(
    pipeline_router,
    prefix="/pipeline",
    tags=["Pipeline"],
)
