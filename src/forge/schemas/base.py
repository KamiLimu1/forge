"""Base Pydantic schemas and utilities."""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampSchema(BaseSchema):
    """Schema mixin for timestamp fields."""

    created_at: datetime
    updated_at: datetime


class SuccessResponse(BaseSchema):
    """Standard success response."""

    success: bool = True
    message: str


class ErrorDetail(BaseSchema):
    """Error detail for validation errors."""

    loc: list[str | int]
    msg: str
    type: str


class ErrorResponse(BaseSchema):
    """Standardized error response format."""

    success: bool = False
    error: str
    detail: str | list[ErrorDetail] | None = None


class PaginatedResponse(BaseSchema, Generic[DataT]):
    """Generic paginated response wrapper."""

    items: list[DataT]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginationParams(BaseSchema):
    """Query parameters for pagination."""

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size
