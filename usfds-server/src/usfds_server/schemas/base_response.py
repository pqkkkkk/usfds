from typing import Generic, List, Optional, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ResourceOwnerDto(BaseModel):
    """Public owner summary joined from `users` for resource display."""
    model_config = ConfigDict(extra="ignore")

    user_id: UUID
    username: str
    full_name: Optional[str] = None


class CursorPage(BaseModel, Generic[T]):
    """Cursor-based pagination payload for infinite-scroll list endpoints."""
    model_config = ConfigDict(extra="ignore")

    items: List[T]
    nextCursor: Optional[str] = None


class ApiResponse(BaseModel, Generic[T]):
    """Unified HTTP response envelope for all client-facing APIs."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    success: bool = Field(default=True, description="Indicates whether the request was successful")
    statusCode: int = Field(default=200, description="HTTP status code")
    data: Optional[T] = Field(default=None, description="Response data payload")
    message: Optional[str] = Field(default="Success", description="Informational message")
    error: Optional[str] = Field(default=None, description="Error details when success is False")

    @classmethod
    def ok(
        cls,
        data: T,
        message: str = "Success",
        status_code: int = 200,
    ) -> "ApiResponse[T]":
        return cls(
            success=True,
            statusCode=status_code,
            data=data,
            message=message,
            error=None,
        )

    @classmethod
    def fail(
        cls,
        error: str,
        status_code: int = 400,
        message: Optional[str] = None,
    ) -> "ApiResponse[None]":
        return cls(
            success=False,
            statusCode=status_code,
            data=None,
            message=message or error,
            error=error,
        )


__all__ = ["ApiResponse", "CursorPage", "ResourceOwnerDto"]
