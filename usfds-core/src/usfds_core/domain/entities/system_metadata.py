from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import (
	ColumnCategory,
	ColumnMlRole,
	LogicalDataType,
)


@dataclass
class SystemColumnMetadata:
	"""Canonical column metadata definition managed by the system."""

	column_key: str
	display_name: str
	category: Union[ColumnCategory, str] = ColumnCategory.DOMAIN
	logical_type: Union[LogicalDataType, str] = LogicalDataType.STRING
	is_required: bool = False
	ml_role: Union[ColumnMlRole, str] = ColumnMlRole.FEATURE
	aliases: List[str] = field(default_factory=list)
	description: Optional[str] = None
	is_active: bool = True
	display_order: int = 100
	metadata_id: UUID = field(default_factory=uuid4)
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	updated_at: Optional[datetime] = None


__all__ = ["SystemColumnMetadata"]
