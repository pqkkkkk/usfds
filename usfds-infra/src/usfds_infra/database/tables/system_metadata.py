"""ORM table for system & domain column metadata registry (ISS-007)."""
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import Boolean, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from usfds_infra.database.base import Base, TimestampMixin


class SystemColumnMetadataModel(Base, TimestampMixin):
	"""SQLAlchemy model for canonical system and domain column metadata."""

	__tablename__ = "system_column_metadata"

	metadata_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	column_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
	display_name: Mapped[str] = mapped_column(String(150), nullable=False)
	category: Mapped[str] = mapped_column(String(32), nullable=False, default="DOMAIN", index=True)
	logical_type: Mapped[str] = mapped_column(String(32), nullable=False, default="STRING")
	is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	ml_role: Mapped[str] = mapped_column(String(32), nullable=False, default="FEATURE")
	aliases: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
	description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
	display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
