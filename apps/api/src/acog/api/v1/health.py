"""
Health check endpoints.

Provides system health information for monitoring and load balancers.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from acog import __version__
from acog.core.config import Settings, get_settings
from acog.core.database import get_db
from acog.schemas.common import HealthResponse

router = APIRouter()


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Returns the health status of the API and its dependencies.",
)
async def health_check(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> HealthResponse:
    """
    Perform health check on the API and its dependencies.

    Checks:
    - Database connectivity
    - Redis connectivity (if configured)
    - S3/MinIO connectivity (if configured)

    Returns:
        HealthResponse with overall status and individual check results
    """
    checks: dict[str, dict[str, Any]] = {}
    overall_healthy = True

    # Database health check
    db_status = await check_database(db)
    checks["database"] = db_status
    if db_status["status"] != "healthy":
        overall_healthy = False

    # Redis health check
    redis_status = await check_redis(settings)
    checks["redis"] = redis_status
    if redis_status["status"] != "healthy":
        # Redis failure is degraded, not unhealthy
        pass

    # S3/MinIO health check
    s3_status = await check_s3(settings)
    checks["storage"] = s3_status
    if s3_status["status"] != "healthy":
        # Storage failure is degraded, not unhealthy
        pass

    # Determine overall status
    if overall_healthy:
        if all(c["status"] == "healthy" for c in checks.values()):
            overall_status = "healthy"
        else:
            overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        version=__version__,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
        checks=checks,
    )


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Simple liveness check for Kubernetes probes.",
)
async def liveness() -> dict[str, str]:
    """
    Kubernetes liveness probe endpoint.

    Returns a simple OK response if the application is running.
    This does not check dependencies - use /health for full status.
    """
    return {"status": "ok"}


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Readiness check for Kubernetes probes.",
)
async def readiness(
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Kubernetes readiness probe endpoint.

    Checks if the application is ready to receive traffic.
    Verifies database connectivity.
    """
    db_status = await check_database(db)

    if db_status["status"] == "healthy":
        return {"status": "ready"}
    else:
        return {"status": "not_ready", "reason": "database_unavailable"}


async def check_database(db: Session) -> dict[str, Any]:
    """
    Check database connectivity.

    Args:
        db: Database session

    Returns:
        Health check result for database
    """
    try:
        # Execute a simple query to verify connectivity
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        return {
            "status": "healthy",
            "message": "Database connection successful",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
        }


async def check_redis(settings: Settings) -> dict[str, Any]:
    """
    Check Redis connectivity.

    Args:
        settings: Application settings

    Returns:
        Health check result for Redis
    """
    try:
        import redis

        client = redis.from_url(settings.redis_url)
        client.ping()
        client.close()
        return {
            "status": "healthy",
            "message": "Redis connection successful",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}",
        }


async def check_s3(settings: Settings) -> dict[str, Any]:
    """
    Check S3/MinIO connectivity.

    Args:
        settings: Application settings

    Returns:
        Health check result for S3/MinIO
    """
    try:
        import boto3
        from botocore.config import Config

        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )

        s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=config,
        )

        # Try to list buckets to verify connectivity
        s3_client.list_buckets()
        return {
            "status": "healthy",
            "message": "S3/MinIO connection successful",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"S3/MinIO connection failed: {str(e)}",
        }
