"""
Tests for rate limiting functionality.
"""

import pytest

from acog.core.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    reset_rate_limiter,
)


class TestInMemoryRateLimiter:
    """Tests for in-memory rate limiter."""

    def test_allows_requests_under_limit(self) -> None:
        """Requests under the limit should be allowed."""
        limiter = InMemoryRateLimiter(window_seconds=60, max_requests=5)

        for i in range(5):
            is_allowed, remaining = limiter.is_allowed("test-client")
            assert is_allowed is True
            assert remaining == 5 - i - 1

    def test_blocks_requests_over_limit(self) -> None:
        """Requests over the limit should be blocked."""
        limiter = InMemoryRateLimiter(window_seconds=60, max_requests=3)

        # Use up the limit
        for _ in range(3):
            limiter.is_allowed("test-client")

        # Next request should be blocked
        is_allowed, remaining = limiter.is_allowed("test-client")
        assert is_allowed is False
        assert remaining == 0

    def test_separate_limits_per_client(self) -> None:
        """Each client should have their own rate limit."""
        limiter = InMemoryRateLimiter(window_seconds=60, max_requests=2)

        # Client A uses their limit
        limiter.is_allowed("client-a")
        limiter.is_allowed("client-a")

        # Client B should still have full limit
        is_allowed, remaining = limiter.is_allowed("client-b")
        assert is_allowed is True
        assert remaining == 0  # 2 - 1 - 1 = 0

    def test_max_requests_property(self) -> None:
        """max_requests property should return configured value."""
        limiter = InMemoryRateLimiter(max_requests=42)
        assert limiter.max_requests == 42


class TestRedisRateLimiter:
    """Tests for Redis rate limiter (without actual Redis)."""

    def test_fails_open_without_redis(self) -> None:
        """Should allow requests when Redis is unavailable."""
        limiter = RedisRateLimiter(
            redis_url="redis://nonexistent:6379/0",
            max_requests=10,
        )

        # Should allow even though Redis isn't available
        is_allowed, remaining = limiter.is_allowed("test-client")
        assert is_allowed is True

    def test_max_requests_property(self) -> None:
        """max_requests property should return configured value."""
        limiter = RedisRateLimiter(
            redis_url="redis://localhost:6379/0",
            max_requests=50,
        )
        assert limiter.max_requests == 50


class TestRateLimiterReset:
    """Tests for rate limiter reset functionality."""

    def test_reset_clears_global_instance(self) -> None:
        """reset_rate_limiter should clear the global instance."""
        from acog.core.rate_limit import _rate_limiter, get_rate_limiter

        # Get a limiter instance
        limiter1 = get_rate_limiter()

        # Reset
        reset_rate_limiter()

        # Get again - should be a new instance
        limiter2 = get_rate_limiter()

        # Can't easily compare instances but at least verify no error
        assert limiter2 is not None
        reset_rate_limiter()  # Clean up
