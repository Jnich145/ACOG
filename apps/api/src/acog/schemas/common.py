"""
Common schemas shared across multiple endpoints.

This module provides base schemas for API responses, pagination,
error handling, and other shared functionality.
"""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Type variable for generic response data
T = TypeVar("T")


class PaginationParams(BaseModel):
    """
    Query parameters for paginated list endpoints.

    Attributes:
        page: Page number (1-indexed)
        page_size: Number of items per page
    """

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
    )

    @property
    def offset(self) -> int:
        """Calculate database offset from page number."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit (alias for page_size)."""
        return self.page_size


class PaginationMeta(BaseModel):
    """
    Pagination metadata included in list responses.

    Attributes:
        page: Current page number (1-indexed)
        page_size: Number of items per page
        total_items: Total number of items across all pages
        total_pages: Total number of pages
        has_next: Whether there is a next page
        has_prev: Whether there is a previous page
    """

    page: int = Field(ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(ge=1, description="Number of items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")

    @classmethod
    def create(
        cls,
        page: int,
        page_size: int,
        total_items: int,
    ) -> "PaginationMeta":
        """
        Create pagination metadata from query parameters and total count.

        Args:
            page: Current page number
            page_size: Items per page
            total_items: Total items matching the query

        Returns:
            PaginationMeta instance
        """
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class ApiResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.

    All successful API responses follow this structure with data and meta fields.

    Attributes:
        data: Response payload
        meta: Response metadata (request_id, pagination, etc.)
    """

    data: T
    meta: dict[str, Any] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    """
    Detailed error information.

    Attributes:
        code: Machine-readable error code
        message: Human-readable error message
        details: Additional error context
    """

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context",
    )


class ErrorResponse(BaseModel):
    """
    Standard error response wrapper.

    All error responses follow this structure for consistent error handling.

    Attributes:
        error: Error details
    """

    error: ErrorDetail


class HealthResponse(BaseModel):
    """
    Health check response schema.

    Attributes:
        status: Overall health status
        version: Application version
        environment: Current environment
        timestamp: Server timestamp
        checks: Individual health check results
    """

    status: str = Field(description="Overall health status (healthy, degraded, unhealthy)")
    version: str = Field(description="Application version")
    environment: str = Field(description="Current environment")
    timestamp: datetime = Field(description="Server timestamp")
    checks: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Individual health check results",
    )


class TimestampSchema(BaseModel):
    """
    Base schema mixin providing timestamp fields.

    Used by all resource schemas to include consistent timestamp handling.
    """

    created_at: datetime = Field(description="When the resource was created")
    updated_at: datetime = Field(description="When the resource was last updated")
    deleted_at: datetime | None = Field(
        default=None,
        description="When the resource was soft-deleted",
    )


class UUIDSchema(BaseModel):
    """
    Base schema mixin providing UUID id field.
    """

    id: UUID = Field(description="Unique identifier")


class BaseResourceSchema(UUIDSchema, TimestampSchema):
    """
    Base schema for all resource responses.

    Combines UUID and timestamp fields.
    """

    model_config = ConfigDict(from_attributes=True)


class DeleteResponse(BaseModel):
    """
    Response schema for delete operations.

    Attributes:
        id: ID of the deleted resource
        deleted_at: Timestamp of deletion
    """

    id: UUID = Field(description="ID of the deleted resource")
    deleted_at: datetime = Field(description="Timestamp of deletion")


class BulkOperationResponse(BaseModel):
    """
    Response schema for bulk operations.

    Attributes:
        success_count: Number of successful operations
        failure_count: Number of failed operations
        failures: Details of failed operations
    """

    success_count: int = Field(description="Number of successful operations")
    failure_count: int = Field(description="Number of failed operations")
    failures: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Details of failed operations",
    )
