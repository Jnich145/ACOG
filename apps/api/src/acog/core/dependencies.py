"""
FastAPI dependency injection functions.

This module provides reusable dependencies for request handling,
including authentication, database sessions, and common parameters.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from acog.core.config import Settings, get_settings
from acog.core.database import get_db
from acog.core.exceptions import AuthenticationError
from acog.core.security import verify_token

# Security scheme for bearer token authentication
security = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security),
    ],
) -> str:
    """
    Dependency to extract and verify the current user from JWT token.

    This dependency requires a valid Bearer token in the Authorization header.

    Args:
        credentials: HTTP Bearer credentials from the request

    Returns:
        User ID extracted from the token subject claim

    Raises:
        AuthenticationError: If no credentials provided or token is invalid

    Example:
        ```python
        @app.get("/protected")
        async def protected_route(
            user_id: str = Depends(get_current_user_id)
        ):
            return {"user_id": user_id}
        ```
    """
    if credentials is None:
        raise AuthenticationError(
            message="Authentication required",
            details={"error": "No credentials provided"},
        )

    token = credentials.credentials
    payload = verify_token(token)

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError(
            message="Invalid token",
            details={"error": "Token has no subject"},
        )

    return str(user_id)


async def get_optional_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security),
    ],
) -> str | None:
    """
    Dependency to optionally extract user ID from JWT token.

    Unlike get_current_user_id, this does not raise an error if
    no credentials are provided. Useful for endpoints that have
    different behavior for authenticated vs unauthenticated users.

    Args:
        credentials: HTTP Bearer credentials from the request

    Returns:
        User ID if valid token provided, None otherwise
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token)
        return payload.get("sub")
    except AuthenticationError:
        return None


class PaginationParams:
    """
    Common pagination parameters for list endpoints.

    Extracts and validates page and page_size query parameters.

    Attributes:
        page: Current page number (1-indexed)
        page_size: Number of items per page
        offset: Calculated offset for database queries
    """

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
        page_size: Annotated[
            int,
            Query(ge=1, le=100, description="Items per page (max 100)"),
        ] = 20,
    ) -> None:
        """
        Initialize pagination parameters.

        Args:
            page: Page number (minimum 1)
            page_size: Items per page (1-100)
        """
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        """Calculate database offset from page number."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit (alias for page_size)."""
        return self.page_size


class SortParams:
    """
    Common sorting parameters for list endpoints.

    Provides sort_by and sort_order query parameters with validation.

    Attributes:
        sort_by: Field name to sort by
        sort_order: Sort direction ('asc' or 'desc')
    """

    def __init__(
        self,
        sort_by: Annotated[
            str,
            Query(description="Field to sort by"),
        ] = "created_at",
        sort_order: Annotated[
            str,
            Query(regex="^(asc|desc)$", description="Sort order"),
        ] = "desc",
    ) -> None:
        """
        Initialize sort parameters.

        Args:
            sort_by: Field name to sort by
            sort_order: Sort direction ('asc' or 'desc')
        """
        self.sort_by = sort_by
        self.sort_order = sort_order

    @property
    def is_descending(self) -> bool:
        """Check if sort order is descending."""
        return self.sort_order == "desc"


def get_idempotency_key(
    x_idempotency_key: Annotated[
        str | None,
        Header(description="Optional idempotency key for POST requests"),
    ] = None,
) -> str | None:
    """
    Extract idempotency key from request header.

    Idempotency keys ensure that duplicate requests (e.g., from
    network retries) produce the same result.

    Args:
        x_idempotency_key: Value from X-Idempotency-Key header

    Returns:
        The idempotency key if provided, None otherwise
    """
    return x_idempotency_key


def validate_uuid(value: str, field_name: str = "id") -> UUID:
    """
    Validate and parse a UUID string.

    Args:
        value: String to parse as UUID
        field_name: Name of the field for error messages

    Returns:
        Parsed UUID object

    Raises:
        ValidationError: If the string is not a valid UUID
    """
    from acog.core.exceptions import ValidationError

    try:
        return UUID(value)
    except ValueError as e:
        raise ValidationError(
            message=f"Invalid UUID format for {field_name}",
            field=field_name,
            details={"value": value, "error": str(e)},
        ) from e


# Type aliases for cleaner dependency injection
DbSession = Annotated[Session, Depends(get_db)]
CurrentUserId = Annotated[str, Depends(get_current_user_id)]
OptionalUserId = Annotated[str | None, Depends(get_optional_user_id)]
Pagination = Annotated[PaginationParams, Depends()]
Sorting = Annotated[SortParams, Depends()]
AppSettings = Annotated[Settings, Depends(get_settings)]
IdempotencyKey = Annotated[str | None, Depends(get_idempotency_key)]
