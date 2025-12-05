"""
Base HTTP client with retry logic and common utilities.

This module provides a base class for all external API integrations with:
- Retry logic with exponential backoff
- Rate limiting support
- Comprehensive logging
- Error handling
"""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, TypeVar

import httpx

from acog.core.config import Settings, get_settings
from acog.core.exceptions import ExternalServiceError, RateLimitError

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class UsageMetrics:
    """
    Tracks usage metrics for external API calls.

    Attributes:
        provider: Name of the service provider
        units_used: Number of units consumed (characters, credits, etc.)
        unit_type: Type of unit (characters, credits, seconds, etc.)
        estimated_cost_usd: Estimated cost in USD
        request_count: Number of API requests made
        latency_ms: Total latency in milliseconds
    """

    provider: str
    units_used: int = 0
    unit_type: str = "units"
    estimated_cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    request_count: int = 0
    latency_ms: int = 0

    def add_units(self, units: int, cost_per_unit: Decimal | None = None) -> None:
        """
        Add units to the usage tracker.

        Args:
            units: Number of units to add
            cost_per_unit: Cost per unit in USD (optional)
        """
        self.units_used += units
        if cost_per_unit is not None:
            self.estimated_cost_usd += Decimal(str(units)) * cost_per_unit

    def record_request(self, latency_ms: int) -> None:
        """
        Record an API request with its latency.

        Args:
            latency_ms: Request latency in milliseconds
        """
        self.request_count += 1
        self.latency_ms += latency_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for storage/logging."""
        return {
            "provider": self.provider,
            "units_used": self.units_used,
            "unit_type": self.unit_type,
            "estimated_cost_usd": float(self.estimated_cost_usd),
            "request_count": self.request_count,
            "latency_ms": self.latency_ms,
        }


@dataclass
class MediaResult:
    """
    Result container for media generation operations.

    Attributes:
        data: The generated media data (bytes or URL)
        content_type: MIME type of the content
        duration_ms: Duration in milliseconds (for audio/video)
        file_size_bytes: Size in bytes
        provider_job_id: External job ID for tracking
        metadata: Additional provider-specific metadata
        usage: Usage metrics for this operation
    """

    data: bytes | str  # bytes for downloaded content, str for URL
    content_type: str
    duration_ms: int | None = None
    file_size_bytes: int | None = None
    provider_job_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    usage: UsageMetrics | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Get duration in seconds."""
        if self.duration_ms is not None:
            return self.duration_ms / 1000.0
        return None


class BaseHTTPClient(ABC):
    """
    Abstract base class for HTTP API clients.

    Provides common functionality for external API integrations:
    - Async HTTP client with connection pooling
    - Retry logic with exponential backoff
    - Rate limiting support with retry-after handling
    - Request/response logging
    - Error handling and conversion to ACOG exceptions

    Subclasses must implement:
    - service_name: Property returning the service name
    - _get_headers(): Method returning default headers
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        settings: Settings | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: float = 60.0,
    ) -> None:
        """
        Initialize the HTTP client.

        Args:
            base_url: Base URL for API requests
            api_key: API key for authentication
            settings: Application settings instance
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds between retries
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._settings = settings or get_settings()
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._timeout = timeout

        # Create async HTTP client
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

        # Track cumulative usage
        self._total_usage = UsageMetrics(provider=self.service_name)

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the name of the service for logging and error messages."""
        pass

    @abstractmethod
    def _get_headers(self) -> dict[str, str]:
        """Return default headers for API requests."""
        pass

    @property
    def total_usage(self) -> UsageMetrics:
        """Get cumulative usage metrics for this client instance."""
        return self._total_usage

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._client.aclose()

    async def __aenter__(self) -> "BaseHTTPClient":
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        await self.close()

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Args:
            attempt: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds before next retry
        """
        delay = min(self._base_delay * (2**attempt), self._max_delay)
        # Add jitter (10-30% of delay)
        jitter = delay * (0.1 + 0.2 * random.random())
        return delay + jitter

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            headers: Additional headers to include
            params: Query parameters
            json_data: JSON body data
            data: Form data
            files: File uploads
            timeout: Request-specific timeout override

        Returns:
            httpx.Response object

        Raises:
            ExternalServiceError: If request fails after retries
            RateLimitError: If rate limit is exceeded after retries
        """
        url = f"{self._base_url}/{path.lstrip('/')}"
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                start_time = time.time()

                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_data,
                    data=data,
                    files=files,
                    timeout=timeout or self._timeout,
                )

                elapsed_ms = int((time.time() - start_time) * 1000)
                self._total_usage.record_request(elapsed_ms)

                # Log the request
                logger.info(
                    f"{self.service_name} API request",
                    extra={
                        "method": method,
                        "url": url,
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                        "attempt": attempt + 1,
                    },
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else self._calculate_backoff(attempt)

                    logger.warning(
                        f"{self.service_name} rate limit hit, retrying",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": round(delay, 2),
                        },
                    )

                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise RateLimitError(
                            message=f"{self.service_name} rate limit exceeded after retries",
                            retry_after=int(delay),
                        )

                # Handle server errors with retry
                if response.status_code >= 500:
                    delay = self._calculate_backoff(attempt)

                    logger.warning(
                        f"{self.service_name} server error, retrying",
                        extra={
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": round(delay, 2),
                        },
                    )

                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(delay)
                        continue
                    else:
                        response.raise_for_status()

                # Handle client errors (no retry)
                if response.status_code >= 400:
                    error_body = ""
                    try:
                        error_body = response.text
                    except Exception:
                        pass

                    logger.error(
                        f"{self.service_name} API client error",
                        extra={
                            "status_code": response.status_code,
                            "error": error_body[:500],
                        },
                    )

                    raise ExternalServiceError(
                        service=self.service_name,
                        message=f"{self.service_name} API error: {response.status_code}",
                        original_error=error_body[:500],
                    )

                return response

            except httpx.TimeoutException as e:
                last_error = e
                delay = self._calculate_backoff(attempt)

                logger.warning(
                    f"{self.service_name} request timeout, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": round(delay, 2),
                    },
                )

                if attempt < self._max_retries - 1:
                    await asyncio.sleep(delay)

            except httpx.RequestError as e:
                last_error = e
                delay = self._calculate_backoff(attempt)

                logger.warning(
                    f"{self.service_name} connection error, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": round(delay, 2),
                        "error": str(e),
                    },
                )

                if attempt < self._max_retries - 1:
                    await asyncio.sleep(delay)

            except (ExternalServiceError, RateLimitError):
                # Re-raise our own errors
                raise

        # All retries exhausted
        error_msg = str(last_error) if last_error else "Unknown error"
        logger.error(
            f"{self.service_name} request failed after all retries",
            extra={
                "max_retries": self._max_retries,
                "error": error_msg,
            },
        )

        raise ExternalServiceError(
            service=self.service_name,
            message=f"{self.service_name} API call failed after retries",
            original_error=error_msg,
        )

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a GET request."""
        return await self._request("GET", path, params=params, headers=headers)

    async def _post(
        self,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a POST request."""
        return await self._request(
            "POST",
            path,
            json_data=json_data,
            data=data,
            files=files,
            headers=headers,
        )

    async def _delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a DELETE request."""
        return await self._request("DELETE", path, headers=headers)


class SyncBaseHTTPClient(ABC):
    """
    Synchronous version of BaseHTTPClient for non-async contexts.

    Provides the same functionality as BaseHTTPClient but using synchronous
    HTTP calls. Useful for Celery workers and other sync contexts.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        settings: Settings | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: float = 60.0,
    ) -> None:
        """
        Initialize the synchronous HTTP client.

        Args:
            base_url: Base URL for API requests
            api_key: API key for authentication
            settings: Application settings instance
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds between retries
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._settings = settings or get_settings()
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._timeout = timeout

        # Create sync HTTP client
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

        # Track cumulative usage
        self._total_usage = UsageMetrics(provider=self.service_name)

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the name of the service for logging and error messages."""
        pass

    @abstractmethod
    def _get_headers(self) -> dict[str, str]:
        """Return default headers for API requests."""
        pass

    @property
    def total_usage(self) -> UsageMetrics:
        """Get cumulative usage metrics for this client instance."""
        return self._total_usage

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._client.close()

    def __enter__(self) -> "SyncBaseHTTPClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Args:
            attempt: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds before next retry
        """
        delay = min(self._base_delay * (2**attempt), self._max_delay)
        jitter = delay * (0.1 + 0.2 * random.random())
        return delay + jitter

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """
        Make a synchronous HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            headers: Additional headers to include
            params: Query parameters
            json_data: JSON body data
            data: Form data
            files: File uploads
            timeout: Request-specific timeout override

        Returns:
            httpx.Response object

        Raises:
            ExternalServiceError: If request fails after retries
            RateLimitError: If rate limit is exceeded after retries
        """
        url = f"{self._base_url}/{path.lstrip('/')}"
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                start_time = time.time()

                response = self._client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_data,
                    data=data,
                    files=files,
                    timeout=timeout or self._timeout,
                )

                elapsed_ms = int((time.time() - start_time) * 1000)
                self._total_usage.record_request(elapsed_ms)

                logger.info(
                    f"{self.service_name} API request",
                    extra={
                        "method": method,
                        "url": url,
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                        "attempt": attempt + 1,
                    },
                )

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else self._calculate_backoff(attempt)

                    logger.warning(
                        f"{self.service_name} rate limit hit, retrying",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": round(delay, 2),
                        },
                    )

                    if attempt < self._max_retries - 1:
                        time.sleep(delay)
                        continue
                    else:
                        raise RateLimitError(
                            message=f"{self.service_name} rate limit exceeded after retries",
                            retry_after=int(delay),
                        )

                if response.status_code >= 500:
                    delay = self._calculate_backoff(attempt)

                    logger.warning(
                        f"{self.service_name} server error, retrying",
                        extra={
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": round(delay, 2),
                        },
                    )

                    if attempt < self._max_retries - 1:
                        time.sleep(delay)
                        continue
                    else:
                        response.raise_for_status()

                if response.status_code >= 400:
                    error_body = ""
                    try:
                        error_body = response.text
                    except Exception:
                        pass

                    logger.error(
                        f"{self.service_name} API client error",
                        extra={
                            "status_code": response.status_code,
                            "error": error_body[:500],
                        },
                    )

                    raise ExternalServiceError(
                        service=self.service_name,
                        message=f"{self.service_name} API error: {response.status_code}",
                        original_error=error_body[:500],
                    )

                return response

            except httpx.TimeoutException as e:
                last_error = e
                delay = self._calculate_backoff(attempt)

                logger.warning(
                    f"{self.service_name} request timeout, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": round(delay, 2),
                    },
                )

                if attempt < self._max_retries - 1:
                    time.sleep(delay)

            except httpx.RequestError as e:
                last_error = e
                delay = self._calculate_backoff(attempt)

                logger.warning(
                    f"{self.service_name} connection error, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": round(delay, 2),
                        "error": str(e),
                    },
                )

                if attempt < self._max_retries - 1:
                    time.sleep(delay)

            except (ExternalServiceError, RateLimitError):
                raise

        error_msg = str(last_error) if last_error else "Unknown error"
        logger.error(
            f"{self.service_name} request failed after all retries",
            extra={
                "max_retries": self._max_retries,
                "error": error_msg,
            },
        )

        raise ExternalServiceError(
            service=self.service_name,
            message=f"{self.service_name} API call failed after retries",
            original_error=error_msg,
        )

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a GET request."""
        return self._request("GET", path, params=params, headers=headers)

    def _post(
        self,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a POST request."""
        return self._request(
            "POST",
            path,
            json_data=json_data,
            data=data,
            files=files,
            headers=headers,
        )

    def _delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a DELETE request."""
        return self._request("DELETE", path, headers=headers)
