"""
Custom exception classes for the ACOG application.

These exceptions provide structured error handling throughout the application
and are mapped to appropriate HTTP status codes in the API layer.
"""

from typing import Any


class ACOGException(Exception):
    """
    Base exception for all ACOG-specific errors.

    Provides a consistent interface for error handling with support for
    error codes, messages, and additional details.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code for client handling
        details: Additional error details (optional)
        status_code: HTTP status code to return (default: 500)
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        """
        Initialize the exception.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            details: Additional error context
            status_code: HTTP status code
        """
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception to dictionary for JSON response.

        Returns:
            Dictionary representation of the error
        """
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class NotFoundError(ACOGException):
    """
    Raised when a requested resource is not found.

    Maps to HTTP 404 Not Found.

    Attributes:
        resource_type: Type of resource that was not found
        resource_id: Identifier of the resource
    """

    def __init__(
        self,
        resource_type: str,
        resource_id: str | None = None,
        message: str | None = None,
    ) -> None:
        """
        Initialize NotFoundError.

        Args:
            resource_type: Type of resource (e.g., "Channel", "Episode")
            resource_id: ID of the resource that was not found
            message: Custom error message (optional)
        """
        if message is None:
            if resource_id:
                message = f"{resource_type} with ID '{resource_id}' not found"
            else:
                message = f"{resource_type} not found"

        super().__init__(
            message=message,
            code="NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": resource_id},
            status_code=404,
        )


class ValidationError(ACOGException):
    """
    Raised when request validation fails.

    Maps to HTTP 422 Unprocessable Entity.

    Used for semantic validation errors beyond basic schema validation
    (which is handled by Pydantic and returns 422 automatically).
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize ValidationError.

        Args:
            message: Description of the validation error
            field: Name of the field that failed validation (optional)
            details: Additional validation context
        """
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=error_details,
            status_code=422,
        )


class AuthenticationError(ACOGException):
    """
    Raised when authentication fails.

    Maps to HTTP 401 Unauthorized.

    Used when credentials are missing, invalid, or expired.
    """

    def __init__(
        self,
        message: str = "Authentication required",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize AuthenticationError.

        Args:
            message: Description of the authentication error
            details: Additional error context
        """
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            details=details or {},
            status_code=401,
        )


class AuthorizationError(ACOGException):
    """
    Raised when authorization fails.

    Maps to HTTP 403 Forbidden.

    Used when a user is authenticated but lacks permission
    to access a resource or perform an action.
    """

    def __init__(
        self,
        message: str = "Permission denied",
        resource: str | None = None,
        action: str | None = None,
    ) -> None:
        """
        Initialize AuthorizationError.

        Args:
            message: Description of the authorization error
            resource: Resource the user tried to access
            action: Action the user tried to perform
        """
        details: dict[str, Any] = {}
        if resource:
            details["resource"] = resource
        if action:
            details["action"] = action

        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            details=details,
            status_code=403,
        )


class ConflictError(ACOGException):
    """
    Raised when an operation conflicts with the current state.

    Maps to HTTP 409 Conflict.

    Used for duplicate entries, concurrent modifications,
    or state conflicts.
    """

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize ConflictError.

        Args:
            message: Description of the conflict
            resource_type: Type of resource involved in the conflict
            details: Additional conflict context
        """
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type

        super().__init__(
            message=message,
            code="CONFLICT",
            details=error_details,
            status_code=409,
        )


class ExternalServiceError(ACOGException):
    """
    Raised when an external service call fails.

    Maps to HTTP 502 Bad Gateway or 503 Service Unavailable.

    Used for errors from OpenAI, ElevenLabs, HeyGen, etc.
    """

    def __init__(
        self,
        service: str,
        message: str,
        original_error: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        """
        Initialize ExternalServiceError.

        Args:
            service: Name of the external service
            message: Description of the error
            original_error: Original error message from the service
            retry_after: Seconds to wait before retrying (optional)
        """
        details: dict[str, Any] = {"service": service}
        if original_error:
            details["original_error"] = original_error
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            details=details,
            status_code=502,
        )


class RateLimitError(ACOGException):
    """
    Raised when rate limit is exceeded.

    Maps to HTTP 429 Too Many Requests.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        """
        Initialize RateLimitError.

        Args:
            message: Description of the rate limit error
            retry_after: Seconds to wait before retrying
        """
        details: dict[str, Any] = {}
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details=details,
            status_code=429,
        )


class PipelineError(ACOGException):
    """
    Raised when a pipeline operation fails.

    Maps to HTTP 500 Internal Server Error.

    Used for errors during episode pipeline processing.
    """

    def __init__(
        self,
        message: str,
        stage: str,
        episode_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize PipelineError.

        Args:
            message: Description of the pipeline error
            stage: Pipeline stage where the error occurred
            episode_id: ID of the episode being processed
            details: Additional error context
        """
        error_details = details or {}
        error_details["stage"] = stage
        if episode_id:
            error_details["episode_id"] = episode_id

        super().__init__(
            message=message,
            code="PIPELINE_ERROR",
            details=error_details,
            status_code=500,
        )
