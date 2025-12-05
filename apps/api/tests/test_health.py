"""
Tests for health check endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check_returns_200(self, client: TestClient) -> None:
        """Health endpoint should return 200 OK."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_check_response_structure(self, client: TestClient) -> None:
        """Health response should have expected structure."""
        response = client.get("/api/v1/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "environment" in data
        assert "timestamp" in data
        assert "checks" in data

    def test_health_check_includes_all_services(self, client: TestClient) -> None:
        """Health check should include database, redis, and storage checks."""
        response = client.get("/api/v1/health")
        data = response.json()

        checks = data.get("checks", {})
        assert "database" in checks
        assert "redis" in checks
        assert "storage" in checks

    def test_root_endpoint(self, client: TestClient) -> None:
        """Root endpoint should return API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "ACOG API"


class TestRateLimiting:
    """Tests for rate limiting middleware."""

    def test_rate_limit_headers_present(self, client: TestClient) -> None:
        """Rate limit headers should be present in response."""
        response = client.get("/api/v1/channels")

        # Check headers are present (case-insensitive in requests)
        headers = {k.lower(): v for k, v in response.headers.items()}
        assert "x-ratelimit-limit" in headers
        assert "x-ratelimit-remaining" in headers
        assert "x-ratelimit-reset" in headers

    def test_rate_limit_excluded_for_health(self, client: TestClient) -> None:
        """Health endpoints should be excluded from rate limiting."""
        # Make many requests to health - should not trigger rate limit
        for _ in range(10):
            response = client.get("/api/v1/health")
            assert response.status_code == 200
