"""API schemas for System Column Metadata Management (/api/v1/system-metadata)."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SystemColumnMetadataResponse(BaseModel):
	metadata_id: UUID
	column_key: str
	display_name: str
	category: str
	logical_type: str
	is_required: bool
	ml_role: str
	aliases: List[str] = Field(default_factory=list)
	description: Optional[str] = None
	is_active: bool
	display_order: int
	created_at: Optional[datetime] = None
	updated_at: Optional[datetime] = None


class CreateSystemColumnRequest(BaseModel):
	column_key: str = Field(..., min_length=2, max_length=64)
	display_name: str = Field(..., min_length=1, max_length=150)
	logical_type: str = Field(default="STRING")
	is_required: bool = Field(default=False)
	ml_role: str = Field(default="FEATURE")
	aliases: List[str] = Field(default_factory=list)
	description: Optional[str] = None
	is_active: bool = Field(default=True)
	display_order: int = Field(default=100)


class UpdateSystemColumnRequest(BaseModel):
	column_key: Optional[str] = Field(default=None, min_length=2, max_length=64)
	display_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
	logical_type: Optional[str] = None
	is_required: Optional[bool] = None
	ml_role: Optional[str] = None
	aliases: Optional[List[str]] = None
	description: Optional[str] = None
	is_active: Optional[bool] = None
	display_order: Optional[int] = None


__all__ = [
	"SystemColumnMetadataResponse",
	"CreateSystemColumnRequest",
	"UpdateSystemColumnRequest",
]
