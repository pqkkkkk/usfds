"""SQLAlchemy repository for canonical system & domain column metadata (ISS-007)."""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from usfds_core.domain.entities.enums import (
	ColumnCategory,
	ColumnMlRole,
	LogicalDataType,
)
from usfds_core.domain.entities.system_metadata import SystemColumnMetadata
from usfds_core.repositories.base_system_metadata_repo import ISystemColumnMetadataRepository
from usfds_infra.database.models import SystemColumnMetadataModel


class SqlSystemColumnMetadataRepository(ISystemColumnMetadataRepository):
	"""SQLAlchemy implementation of ISystemColumnMetadataRepository."""

	def __init__(self, session: Session) -> None:
		self.session = session

	@staticmethod
	def _to_entity(model: SystemColumnMetadataModel) -> SystemColumnMetadata:
		try:
			category_val: ColumnCategory | str = ColumnCategory(model.category)
		except ValueError:
			category_val = model.category
		try:
			logical_type_val: LogicalDataType | str = LogicalDataType(model.logical_type)
		except ValueError:
			logical_type_val = model.logical_type
		try:
			ml_role_val: ColumnMlRole | str = ColumnMlRole(model.ml_role)
		except ValueError:
			ml_role_val = model.ml_role

		return SystemColumnMetadata(
			metadata_id=UUID(model.metadata_id),
			column_key=model.column_key,
			display_name=model.display_name,
			category=category_val,
			logical_type=logical_type_val,
			is_required=bool(model.is_required),
			ml_role=ml_role_val,
			aliases=list(model.aliases or []),
			description=model.description,
			is_active=bool(model.is_active),
			display_order=int(model.display_order),
			created_at=model.created_at,
			updated_at=model.updated_at,
		)

	def list_all(self, include_inactive: bool = False) -> List[SystemColumnMetadata]:
		stmt = select(SystemColumnMetadataModel)
		if not include_inactive:
			stmt = stmt.where(SystemColumnMetadataModel.is_active.is_(True))
		stmt = stmt.order_by(
			SystemColumnMetadataModel.display_order.asc(),
			SystemColumnMetadataModel.column_key.asc(),
		)
		rows = self.session.execute(stmt).scalars().all()
		return [self._to_entity(r) for r in rows]

	def get_by_id(self, metadata_id: UUID) -> Optional[SystemColumnMetadata]:
		model = self.session.get(SystemColumnMetadataModel, str(metadata_id))
		return self._to_entity(model) if model else None

	def get_by_key(self, column_key: str) -> Optional[SystemColumnMetadata]:
		key_lower = column_key.strip().lower()
		stmt = select(SystemColumnMetadataModel).where(
			func.lower(SystemColumnMetadataModel.column_key) == key_lower
		)
		model = self.session.execute(stmt).scalar_one_or_none()
		return self._to_entity(model) if model else None

	def save(self, metadata: SystemColumnMetadata) -> SystemColumnMetadata:
		model = self.session.get(SystemColumnMetadataModel, str(metadata.metadata_id))
		category_str = metadata.category.value if hasattr(metadata.category, "value") else str(metadata.category)
		ltype_str = metadata.logical_type.value if hasattr(metadata.logical_type, "value") else str(metadata.logical_type)
		role_str = metadata.ml_role.value if hasattr(metadata.ml_role, "value") else str(metadata.ml_role)

		if model is None:
			model = SystemColumnMetadataModel(
				metadata_id=str(metadata.metadata_id),
				column_key=metadata.column_key,
				display_name=metadata.display_name,
				category=category_str,
				logical_type=ltype_str,
				is_required=bool(metadata.is_required),
				ml_role=role_str,
				aliases=list(metadata.aliases or []),
				description=metadata.description,
				is_active=bool(metadata.is_active),
				display_order=int(metadata.display_order),
				created_at=metadata.created_at or datetime.now(timezone.utc),
				updated_at=metadata.updated_at or datetime.now(timezone.utc),
			)
			self.session.add(model)
		else:
			model.column_key = metadata.column_key
			model.display_name = metadata.display_name
			model.category = category_str
			model.logical_type = ltype_str
			model.is_required = bool(metadata.is_required)
			model.ml_role = role_str
			model.aliases = list(metadata.aliases or [])
			model.description = metadata.description
			model.is_active = bool(metadata.is_active)
			model.display_order = int(metadata.display_order)
			model.updated_at = datetime.now(timezone.utc)

		self.session.flush()
		return self._to_entity(model)

	def delete(self, metadata_id: UUID) -> None:
		self.session.execute(
			delete(SystemColumnMetadataModel).where(
				SystemColumnMetadataModel.metadata_id == str(metadata_id)
			)
		)
		self.session.flush()
