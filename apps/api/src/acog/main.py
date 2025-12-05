"""
FastAPI application entry point.

This module initializes the FastAPI application with all middleware,
exception handlers, and routers.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from acog import __version__
from acog.api.v1 import api_router
from acog.core.config import get_settings
from acog.core.exceptions import ACOGException
from acog.core.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown events for the application.
    """
    # Startup
    settings = get_settings()
    print(f"Starting ACOG API v{__version__} in {settings.environment} mode")

    yield

    # Shutdown
    print("Shutting down ACOG API")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title="ACOG API",
        description="Automated Content Orchestration & Generation Engine",
        version=__version__,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # Register exception handlers
    register_exception_handlers(app)

    # Register middleware
    register_middleware(app)

    # Include API routers
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register custom exception handlers.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(ACOGException)
    async def acog_exception_handler(
        request: Request,
        exc: ACOGException,
    ) -> JSONResponse:
        """Handle ACOG-specific exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        settings = get_settings()

        # Log the error
        print(f"Unhandled exception: {exc}")

        # In development, include the error details
        if settings.is_development:
            details = {"error_type": type(exc).__name__, "error": str(exc)}
        else:
            details = {}

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": details,
                }
            },
        )


def register_middleware(app: FastAPI) -> None:
    """
    Register application middleware.

    Args:
        app: FastAPI application instance
    """

    @app.middleware("http")
    async def add_request_id(request: Request, call_next: Any) -> Any:
        """Add unique request ID to each request."""
        request_id = str(uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response

    @app.middleware("http")
    async def add_process_time(request: Request, call_next: Any) -> Any:
        """Add processing time header to response."""
        start_time = datetime.now(UTC)
        response = await call_next(request)
        process_time = (datetime.now(UTC) - start_time).total_seconds()
        response.headers["X-Process-Time"] = str(process_time)
        return response


# Create the application instance
app = create_app()


# Root endpoint
@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint returning API information."""
    return {
        "name": "ACOG API",
        "version": __version__,
        "docs": "/docs",
    }
