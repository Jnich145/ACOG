"""
OpenAI API client wrapper for ACOG content generation.

This module provides a robust wrapper around the OpenAI Python SDK with:
- Retry logic with exponential backoff
- Token usage tracking
- Cost estimation
- Structured JSON output support
- Comprehensive error handling and logging
"""

import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, TypeVar

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel

from acog.core.config import Settings, get_settings
from acog.core.exceptions import ExternalServiceError, RateLimitError as ACOGRateLimitError

logger = logging.getLogger(__name__)

# Type variable for structured output parsing
T = TypeVar("T", bound=BaseModel)


# OpenAI pricing per 1K tokens (as of late 2024 / early 2025)
# These should be updated as pricing changes
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o-2024-11-20": {"input": 0.0025, "output": 0.01},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "o1": {"input": 0.015, "output": 0.06},
    "o1-mini": {"input": 0.003, "output": 0.012},
    "o1-preview": {"input": 0.015, "output": 0.06},
}


@dataclass
class TokenUsage:
    """
    Tracks token usage and cost for an OpenAI API call.

    Attributes:
        input_tokens: Number of tokens in the prompt/input
        output_tokens: Number of tokens in the completion/output
        total_tokens: Total tokens used (input + output)
        model: The model that was used
        estimated_cost_usd: Estimated cost in USD based on model pricing
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    estimated_cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))

    def calculate_cost(self, model: str) -> Decimal:
        """
        Calculate estimated cost based on token usage and model pricing.

        Args:
            model: The OpenAI model name

        Returns:
            Estimated cost in USD as Decimal
        """
        self.model = model
        pricing = MODEL_PRICING.get(model, {"input": 0.01, "output": 0.03})

        input_cost = Decimal(str(self.input_tokens / 1000)) * Decimal(str(pricing["input"]))
        output_cost = Decimal(str(self.output_tokens / 1000)) * Decimal(str(pricing["output"]))

        self.estimated_cost_usd = input_cost + output_cost
        return self.estimated_cost_usd

    def to_dict(self) -> dict[str, Any]:
        """Convert usage to dictionary for storage/logging."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "estimated_cost_usd": float(self.estimated_cost_usd),
        }


@dataclass
class CompletionResult:
    """
    Result container for OpenAI completion calls.

    Attributes:
        content: The generated text content
        usage: Token usage and cost information
        model: The model used for generation
        finish_reason: Why the model stopped generating
        raw_response: Original API response for debugging
    """

    content: str
    usage: TokenUsage
    model: str
    finish_reason: str
    raw_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for storage."""
        return {
            "content": self.content,
            "usage": self.usage.to_dict(),
            "model": self.model,
            "finish_reason": self.finish_reason,
        }


@dataclass
class JsonCompletionResult(CompletionResult):
    """
    Result container for structured JSON completions.

    Attributes:
        parsed_content: The parsed JSON as a dictionary
    """

    parsed_content: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for storage."""
        result = super().to_dict()
        result["parsed_content"] = self.parsed_content
        return result


class OpenAIClient:
    """
    OpenAI API client wrapper with retry logic and cost tracking.

    This client provides:
    - Automatic retry with exponential backoff for transient errors
    - Token usage and cost tracking
    - Structured JSON output via response_format
    - Comprehensive logging for debugging
    - Rate limit handling

    Example:
        ```python
        client = OpenAIClient()

        # Simple completion
        result = client.complete(
            messages=[{"role": "user", "content": "Hello!"}],
            model="gpt-4o-mini"
        )
        print(result.content)

        # Structured JSON output
        json_result = client.complete_json(
            messages=[{"role": "user", "content": "List 3 colors as JSON"}],
            model="gpt-4o",
            json_schema={"type": "object", "properties": {"colors": {"type": "array"}}}
        )
        print(json_result.parsed_content)
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        settings: Settings | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key (uses settings if not provided)
            settings: Application settings instance
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds between retries
        """
        self._settings = settings or get_settings()
        self._api_key = api_key or self._settings.openai_api_key
        self._client = OpenAI(api_key=self._api_key)
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay

        # Track cumulative usage for the client instance
        self._total_usage = TokenUsage()

    @property
    def total_usage(self) -> TokenUsage:
        """Get cumulative token usage for this client instance."""
        return self._total_usage

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Args:
            attempt: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds before next retry
        """
        import random

        delay = min(self._base_delay * (2 ** attempt), self._max_delay)
        # Add jitter (10-30% of delay)
        jitter = delay * (0.1 + 0.2 * random.random())
        return delay + jitter

    def _update_total_usage(self, usage: TokenUsage) -> None:
        """Update cumulative token usage."""
        self._total_usage.input_tokens += usage.input_tokens
        self._total_usage.output_tokens += usage.output_tokens
        self._total_usage.total_tokens += usage.total_tokens
        self._total_usage.estimated_cost_usd += usage.estimated_cost_usd

    def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        system_message: str | None = None,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Generate a text completion using OpenAI's chat API.

        Implements automatic retry with exponential backoff for transient errors.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: OpenAI model to use (defaults to settings.openai_model_planning)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate (None for model default)
            system_message: Optional system message to prepend
            stop: Stop sequences
            **kwargs: Additional parameters passed to the API

        Returns:
            CompletionResult with generated content and usage info

        Raises:
            ExternalServiceError: If all retry attempts fail
            ACOGRateLimitError: If rate limit is exceeded after retries
        """
        model = model or self._settings.openai_model_planning

        # Prepend system message if provided
        if system_message:
            messages = [{"role": "system", "content": system_message}] + messages

        logger.info(
            "OpenAI completion request",
            extra={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "message_count": len(messages),
            },
        )

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                start_time = time.time()

                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop,
                    **kwargs,
                )

                elapsed_time = time.time() - start_time

                # Extract content
                choice = response.choices[0]
                content = choice.message.content or ""
                finish_reason = choice.finish_reason or "unknown"

                # Track usage
                usage = TokenUsage()
                if response.usage:
                    usage.input_tokens = response.usage.prompt_tokens
                    usage.output_tokens = response.usage.completion_tokens
                    usage.total_tokens = response.usage.total_tokens
                    usage.calculate_cost(model)

                self._update_total_usage(usage)

                logger.info(
                    "OpenAI completion success",
                    extra={
                        "model": model,
                        "elapsed_seconds": round(elapsed_time, 2),
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "estimated_cost_usd": float(usage.estimated_cost_usd),
                        "finish_reason": finish_reason,
                    },
                )

                return CompletionResult(
                    content=content,
                    usage=usage,
                    model=model,
                    finish_reason=finish_reason,
                    raw_response=response.model_dump() if response else None,
                )

            except RateLimitError as e:
                last_error = e
                retry_after = getattr(e, "retry_after", None)
                delay = float(retry_after) if retry_after else self._calculate_backoff(attempt)

                logger.warning(
                    "OpenAI rate limit hit, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": round(delay, 2),
                    },
                )

                if attempt < self._max_retries - 1:
                    time.sleep(delay)
                else:
                    raise ACOGRateLimitError(
                        message="OpenAI rate limit exceeded after retries",
                        retry_after=int(delay),
                    ) from e

            except APIConnectionError as e:
                last_error = e
                delay = self._calculate_backoff(attempt)

                logger.warning(
                    "OpenAI connection error, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": round(delay, 2),
                        "error": str(e),
                    },
                )

                if attempt < self._max_retries - 1:
                    time.sleep(delay)

            except APIStatusError as e:
                # Don't retry on 4xx errors (except rate limit which is handled above)
                if 400 <= e.status_code < 500 and e.status_code != 429:
                    logger.error(
                        "OpenAI API client error",
                        extra={
                            "status_code": e.status_code,
                            "error": str(e),
                        },
                    )
                    raise ExternalServiceError(
                        service="OpenAI",
                        message=f"OpenAI API error: {e.message}",
                        original_error=str(e),
                    ) from e

                last_error = e
                delay = self._calculate_backoff(attempt)

                logger.warning(
                    "OpenAI API error, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "status_code": e.status_code,
                        "delay_seconds": round(delay, 2),
                    },
                )

                if attempt < self._max_retries - 1:
                    time.sleep(delay)

        # All retries exhausted
        error_msg = str(last_error) if last_error else "Unknown error"
        logger.error(
            "OpenAI completion failed after all retries",
            extra={
                "max_retries": self._max_retries,
                "error": error_msg,
            },
        )
        raise ExternalServiceError(
            service="OpenAI",
            message="OpenAI API call failed after retries",
            original_error=error_msg,
        )

    def complete_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        system_message: str | None = None,
        strict: bool = True,
        **kwargs: Any,
    ) -> JsonCompletionResult:
        """
        Generate a structured JSON completion using OpenAI's response_format.

        Uses OpenAI's structured output feature for reliable JSON generation.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: OpenAI model to use (defaults to settings.openai_model_planning)
            json_schema: JSON Schema for the expected response structure
            schema_name: Name for the JSON schema (used in response_format)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            system_message: Optional system message to prepend
            strict: Whether to enforce strict schema adherence
            **kwargs: Additional parameters passed to the API

        Returns:
            JsonCompletionResult with parsed JSON content and usage info

        Raises:
            ExternalServiceError: If generation or parsing fails
            ACOGRateLimitError: If rate limit is exceeded
        """
        model = model or self._settings.openai_model_planning

        # Prepend system message if provided
        if system_message:
            messages = [{"role": "system", "content": system_message}] + messages

        # Build response_format for structured output
        response_format: dict[str, Any] = {"type": "json_object"}

        # Use structured output with schema if provided (for supported models)
        if json_schema:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": strict,
                    "schema": json_schema,
                },
            }

        logger.info(
            "OpenAI JSON completion request",
            extra={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "message_count": len(messages),
                "has_schema": json_schema is not None,
            },
        )

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                start_time = time.time()

                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    **kwargs,
                )

                elapsed_time = time.time() - start_time

                # Extract content
                choice = response.choices[0]
                content = choice.message.content or "{}"
                finish_reason = choice.finish_reason or "unknown"

                # Parse JSON content
                try:
                    parsed_content = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.error(
                        "Failed to parse JSON from OpenAI response",
                        extra={
                            "content": content[:500],
                            "error": str(e),
                        },
                    )
                    raise ExternalServiceError(
                        service="OpenAI",
                        message="Failed to parse JSON response from OpenAI",
                        original_error=str(e),
                    ) from e

                # Track usage
                usage = TokenUsage()
                if response.usage:
                    usage.input_tokens = response.usage.prompt_tokens
                    usage.output_tokens = response.usage.completion_tokens
                    usage.total_tokens = response.usage.total_tokens
                    usage.calculate_cost(model)

                self._update_total_usage(usage)

                logger.info(
                    "OpenAI JSON completion success",
                    extra={
                        "model": model,
                        "elapsed_seconds": round(elapsed_time, 2),
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "estimated_cost_usd": float(usage.estimated_cost_usd),
                        "finish_reason": finish_reason,
                    },
                )

                return JsonCompletionResult(
                    content=content,
                    parsed_content=parsed_content,
                    usage=usage,
                    model=model,
                    finish_reason=finish_reason,
                    raw_response=response.model_dump() if response else None,
                )

            except RateLimitError as e:
                last_error = e
                retry_after = getattr(e, "retry_after", None)
                delay = float(retry_after) if retry_after else self._calculate_backoff(attempt)

                logger.warning(
                    "OpenAI rate limit hit, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": round(delay, 2),
                    },
                )

                if attempt < self._max_retries - 1:
                    time.sleep(delay)
                else:
                    raise ACOGRateLimitError(
                        message="OpenAI rate limit exceeded after retries",
                        retry_after=int(delay),
                    ) from e

            except APIConnectionError as e:
                last_error = e
                delay = self._calculate_backoff(attempt)

                logger.warning(
                    "OpenAI connection error, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": round(delay, 2),
                        "error": str(e),
                    },
                )

                if attempt < self._max_retries - 1:
                    time.sleep(delay)

            except APIStatusError as e:
                if 400 <= e.status_code < 500 and e.status_code != 429:
                    logger.error(
                        "OpenAI API client error",
                        extra={
                            "status_code": e.status_code,
                            "error": str(e),
                        },
                    )
                    raise ExternalServiceError(
                        service="OpenAI",
                        message=f"OpenAI API error: {e.message}",
                        original_error=str(e),
                    ) from e

                last_error = e
                delay = self._calculate_backoff(attempt)

                logger.warning(
                    "OpenAI API error, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "status_code": e.status_code,
                        "delay_seconds": round(delay, 2),
                    },
                )

                if attempt < self._max_retries - 1:
                    time.sleep(delay)

            except ExternalServiceError:
                # Re-raise our own errors
                raise

        # All retries exhausted
        error_msg = str(last_error) if last_error else "Unknown error"
        logger.error(
            "OpenAI JSON completion failed after all retries",
            extra={
                "max_retries": self._max_retries,
                "error": error_msg,
            },
        )
        raise ExternalServiceError(
            service="OpenAI",
            message="OpenAI API call failed after retries",
            original_error=error_msg,
        )

    def complete_with_schema(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        system_message: str | None = None,
        **kwargs: Any,
    ) -> tuple[T, TokenUsage]:
        """
        Generate a structured completion validated against a Pydantic model.

        This method uses the Pydantic model's JSON schema for structured output
        and validates the response against the model.

        Args:
            messages: List of message dicts with 'role' and 'content'
            response_model: Pydantic model class for response validation
            model: OpenAI model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_message: Optional system message
            **kwargs: Additional parameters

        Returns:
            Tuple of (validated_response, token_usage)

        Raises:
            ExternalServiceError: If generation fails or response doesn't match schema
            ValidationError: If response fails Pydantic validation
        """
        # Get JSON schema from Pydantic model
        json_schema = response_model.model_json_schema()

        result = self.complete_json(
            messages=messages,
            model=model,
            json_schema=json_schema,
            schema_name=response_model.__name__,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=system_message,
            **kwargs,
        )

        # Validate against Pydantic model
        try:
            validated = response_model.model_validate(result.parsed_content)
            return validated, result.usage
        except Exception as e:
            logger.error(
                "Failed to validate OpenAI response against schema",
                extra={
                    "schema": response_model.__name__,
                    "content": result.content[:500],
                    "error": str(e),
                },
            )
            raise ExternalServiceError(
                service="OpenAI",
                message=f"Response validation failed for {response_model.__name__}",
                original_error=str(e),
            ) from e


def get_openai_client(settings: Settings | None = None) -> OpenAIClient:
    """
    Factory function to create an OpenAI client.

    Can be used as a FastAPI dependency.

    Args:
        settings: Optional settings override

    Returns:
        Configured OpenAIClient instance
    """
    return OpenAIClient(settings=settings)
