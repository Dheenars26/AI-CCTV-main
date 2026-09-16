"""
Common Response Envelopes & Schemas.
"""

from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Any] = Field(default=None, description="Detailed validation or context metadata")


class ErrorResponse(BaseModel):
    success: bool = Field(default=False, description="Success flag (always false for errors)")
    error: ErrorDetail
    request_id: str = Field(..., description="Unique correlation ID for tracing logs")


class ResponseModel(BaseModel, Generic[T]):
    success: bool = Field(default=True, description="Success flag")
    data: T = Field(..., description="Payload data")
    request_id: Optional[str] = Field(default=None, description="Request correlation ID")


class PaginationMeta(BaseModel):
    total: int = Field(..., description="Total count of items matching filter criteria")
    limit: int = Field(..., description="Items per page limit")
    offset: int = Field(..., description="Item offset pagination index")
    page: int = Field(..., description="Current page number (1-indexed)")
    pages: int = Field(..., description="Total pages available")


class PaginatedResponseModel(BaseModel, Generic[T]):
    success: bool = Field(default=True, description="Success flag")
    data: list[T] = Field(..., description="List of item payloads")
    pagination: PaginationMeta = Field(..., description="Pagination metadata envelope")
    request_id: Optional[str] = Field(default=None, description="Request correlation ID")
