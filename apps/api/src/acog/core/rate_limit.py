"""
Rate limiting middleware for ACOG API.

Supports both in-memory (development) and Redis-based (production) rate limiting
using a sliding window algorithm.
"""

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from acog.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests_per_minute: int = 60
    window_seconds: int = 60
    burst_limit: int = 10  # Max requests in a 1-second burst


class RateLimiterBackend(ABC):
    """Abstract base class for rate limiter backends."""

    @abstractmethod
    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        Check if request is allowed for client.

        Args:
            client_id: Client identifier (usually IP address)

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        pass

    @property
    @abstractmethod
    def max_requests(self) -> int:
        """Return the maximum requests allowed in the window."""
        pass


class InMemoryRateLimiter(RateLimiterBackend):
    """
    In-memory sliding window rate limiter.

    Suitable for single-process development. Not recommended for production
    with multiple workers as state is not shared.
    """

    def __init__(self, window_seconds: int = 60, max_requests: int = 60):
        self.window_seconds = window_seconds
        self._max_requests = max_requests
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    @property
    def max_requests(self) -> int:
        return self._max_requests

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """Check if request is allowed using in-memory tracking."""
        now = time.time()

        # Periodic cleanup to prevent memory growth
        if now - self._last_cleanup > 300:  # Every 5 minutes
            self._cleanup()
            self._last_cleanup = now

        window_start = now - self.window_seconds

        # Get existing requests and filter to current window
        requests = self._requests[client_id]
        requests = [ts for ts in requests if ts > window_start]
        self._requests[client_id] = requests

        # Check if under limit
        remaining = max(0, self._max_requests - len(requests))

        if len(requests) >= self._max_requests:
            return False, 0

        # Record this request
        requests.append(now)
        return True, remaining - 1

    def _cleanup(self) -> None:
        """Remove old entries to prevent memory growth."""
        now = time.time()
        window_start = now - self.window_seconds

        for client_id in list(self._requests.keys()):
            self._requests[client_id] = [
                ts for ts in self._requests[client_id] if ts > window_start
            ]
            if not self._requests[client_id]:
                del self._requests[client_id]


class RedisRateLimiter(RateLimiterBackend):
    """
    Redis-based sliding window rate limiter.

    Uses Redis sorted sets for distributed rate limiting across multiple workers.
    Falls back to allowing requests if Redis is unavailable.
    """

    def __init__(
        self,
        redis_url: str,
        window_seconds: int = 60,
        max_requests: int = 60,
        key_prefix: str = "ratelimit:",
    ):
        self.window_seconds = window_seconds
        self._max_requests = max_requests
        self.key_prefix = key_prefix
        self._redis: Any = None
        self._redis_url = redis_url

    @property
    def max_requests(self) -> int:
        return self._max_requests

    def _get_redis(self) -> Any:
        """Lazy initialization of Redis connection."""
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(self._redis_url, decode_responses=True)
                # Test connection
                self._redis.ping()
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
                self._redis = None
        return self._redis

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """Check if request is allowed using Redis sorted sets."""
        redis_client = self._get_redis()

        if redis_client is None:
            # Fail open - allow request if Redis is unavailable
            logger.warning("Redis unavailable, allowing request without rate limiting")
            return True, self._max_requests - 1

        try:
            now = time.time()
            window_start = now - self.window_seconds
            key = f"{self.key_prefix}{client_id}"

            # Use pipeline for atomic operations
            pipe = redis_client.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            pipe.zcard(key)

            # Add current request with timestamp as score
            pipe.zadd(key, {str(now): now})

            # Set expiry on the key
            pipe.expire(key, self.window_seconds + 1)

            results = pipe.execute()

            # results[1] is the count before adding current request
            current_count = results[1]
            remaining = max(0, self._max_requests - current_count - 1)

            if current_count >= self._max_requests:
                # Remove the request we just added since it's over limit
                redis_client.zrem(key, str(now))
                return False, 0

            return True, remaining

        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            # Fail open on errors
            return True, self._max_requests - 1


# Global rate limiter instance
_rate_limiter: RateLimiterBackend | None = None


def get_rate_limiter() -> RateLimiterBackend:
    """
    Get or create the global rate limiter instance.

    Uses Redis in production, in-memory for development.
    """
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_settings()

        if settings.is_development:
            # Use in-memory for development (faster, no Redis required)
            _rate_limiter = InMemoryRateLimiter(
                window_seconds=60,
                max_requests=100,  # More lenient in development
            )
            logger.info("Using in-memory rate limiter (development mode)")
        else:
            # Use Redis for production (distributed, multi-worker safe)
            _rate_limiter = RedisRateLimiter(
                redis_url=settings.redis_url,
                window_seconds=60,
                max_requests=60,
            )
            logger.info("Using Redis rate limiter (production mode)")

    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the rate limiter instance (useful for testing)."""
    global _rate_limiter
    _rate_limiter = None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.

    Limits requests per client IP using a sliding window algorithm.
    Excludes health check endpoints from rate limiting.
    """

    # Paths excluded from rate limiting
    EXCLUDED_PATHS = {
        "/",
        "/health",
        "/api/v1/health",
        "/api/v1/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Paths with stricter rate limits (e.g., auth endpoints)
    STRICT_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    }

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request and apply rate limiting."""
        # Skip rate limiting for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Get client identifier
        client_ip = self._get_client_ip(request)

        # Check rate limit
        rate_limiter = get_rate_limiter()
        is_allowed, remaining = rate_limiter.is_allowed(client_ip)

        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again later.",
                        "details": {
                            "retry_after_seconds": 60,
                        },
                    }
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(rate_limiter.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + 60),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request.

        Handles X-Forwarded-For header for proxied requests.
        """
        # Check for forwarded header (when behind proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header (common with nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"


__all__ = [
    "RateLimitMiddleware",
    "RateLimiterBackend",
    "InMemoryRateLimiter",
    "RedisRateLimiter",
    "get_rate_limiter",
    "reset_rate_limiter",
    "RateLimitConfig",
]
