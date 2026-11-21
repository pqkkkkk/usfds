"""Domain service for managing canonical System & Domain column metadata (ISS-007)."""
from datetime import datetime, timezone
import re
from typing import Dict, Iterable, List, Optional, Set, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import (
	ColumnCategory,
	ColumnMlRole,
	LogicalDataType,
)
from usfds_core.domain.entities.system_metadata import SystemColumnMetadata
from usfds_core.domain.schemas.system_metadata import (
	CORE_COLUMN_KEYS,
	build_non_ml_columns,
)
from usfds_core.repositories.base_system_metadata_repo import ISystemColumnMetadataRepository

_COLUMN_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def _normalize_aliases(column_key: str, aliases: Optional[Iterable[str]]) -> List[str]:
	result: List[str] = []
	seen: Set[str] = set()
	raw_items = [column_key, *(aliases or [])]
	for item in raw_items:
		cleaned = str(item).strip()
		if not cleaned:
			continue
		lower = cleaned.lower()
		if lower not in seen:
			seen.add(lower)
			result.append(cleaned)
	return result


def _as_enum(value: Union[str, LogicalDataType, ColumnMlRole], enum_cls):
	if isinstance(value, enum_cls):
		return value
	try:
		return enum_cls(str(value).strip().upper())
	except ValueError as err:
		allowed = ", ".join(e.value for e in enum_cls)
		raise ValueError(f"Giá trị '{value}' không hợp lệ cho {enum_cls.__name__}. Cho phép: {allowed}.") from err


class SystemMetadataService:
	"""CRUD service for SystemColumnMetadata with strict protection of the 5 CORE columns."""

	def __init__(self, metadata_repo: ISystemColumnMetadataRepository) -> None:
		self.metadata_repo = metadata_repo

	def list_columns(self, include_inactive: bool = False) -> List[SystemColumnMetadata]:
		return self.metadata_repo.list_all(include_inactive=include_inactive)

	def get_column(self, metadata_id: UUID) -> SystemColumnMetadata:
		item = self.metadata_repo.get_by_id(metadata_id)
		if item is None:
			raise LookupError(f"Không tìm thấy siêu dữ liệu cột '{metadata_id}'.")
		return item

	def create_column(
		self,
		column_key: str,
		display_name: str,
		logical_type: Union[LogicalDataType, str] = LogicalDataType.STRING,
		is_required: bool = False,
		ml_role: Union[ColumnMlRole, str] = ColumnMlRole.FEATURE,
		aliases: Optional[List[str]] = None,
		description: Optional[str] = None,
		is_active: bool = True,
		display_order: int = 100,
	) -> SystemColumnMetadata:
		key = str(column_key or "").strip().lower()
		if not _COLUMN_KEY_PATTERN.match(key):
			raise ValueError(
				"Mã cột chuẩn (column_key) phải bắt đầu bằng chữ cái thường và chỉ chứa a-z, 0-9, '_' (2-64 ký tự)."
			)
		if key in CORE_COLUMN_KEYS:
			raise ValueError(f"Không thể tạo mới cột trùng khóa hệ thống cốt lõi '{key}'.")
		if self.metadata_repo.get_by_key(key) is not None:
			raise ValueError(f"Cột chuẩn '{key}' đã tồn tại trong hệ thống.")

		name = str(display_name or "").strip()
		if not name:
			raise ValueError("Tên hiển thị (display_name) không được để trống.")

		resolved_type = _as_enum(logical_type, LogicalDataType)
		resolved_role = _as_enum(ml_role, ColumnMlRole)
		normalized_aliases = _normalize_aliases(key, aliases)

		entity = SystemColumnMetadata(
			metadata_id=uuid4(),
			column_key=key,
			display_name=name,
			category=ColumnCategory.DOMAIN,
			logical_type=resolved_type,
			is_required=bool(is_required),
			ml_role=resolved_role,
			aliases=normalized_aliases,
			description=description.strip() if isinstance(description, str) and description.strip() else None,
			is_active=bool(is_active),
			display_order=int(display_order),
			created_at=datetime.now(timezone.utc),
			updated_at=datetime.now(timezone.utc),
		)
		return self.metadata_repo.save(entity)

	def update_column(
		self,
		metadata_id: UUID,
		display_name: Optional[str] = None,
		logical_type: Optional[Union[LogicalDataType, str]] = None,
		is_required: Optional[bool] = None,
		ml_role: Optional[Union[ColumnMlRole, str]] = None,
		aliases: Optional[List[str]] = None,
		description: Optional[str] = None,
		is_active: Optional[bool] = None,
		display_order: Optional[int] = None,
		column_key: Optional[str] = None,
	) -> SystemColumnMetadata:
		existing = self.get_column(metadata_id)
		category_val = existing.category.value if hasattr(existing.category, "value") else str(existing.category)
		is_core = category_val == ColumnCategory.CORE.value or existing.column_key in CORE_COLUMN_KEYS

		if is_core:
			if column_key is not None and str(column_key).strip().lower() != existing.column_key:
				raise ValueError(f"Không thể đổi column_key của cột hệ thống cốt lõi '{existing.column_key}'.")
			if logical_type is not None:
				req_type = _as_enum(logical_type, LogicalDataType)
				existing_type = _as_enum(existing.logical_type, LogicalDataType)
				if req_type != existing_type:
					raise ValueError(f"Không thể đổi kiểu dữ liệu logic của cột hệ thống cốt lõi '{existing.column_key}'.")
			if is_required is False:
				raise ValueError(f"Không thể tắt trạng thái bắt buộc của cột hệ thống cốt lõi '{existing.column_key}'.")
			if is_active is False:
				raise ValueError(f"Không thể vô hiệu hóa cột hệ thống cốt lõi '{existing.column_key}'.")
			if ml_role is not None:
				req_role = _as_enum(ml_role, ColumnMlRole)
				existing_role = _as_enum(existing.ml_role, ColumnMlRole)
				if req_role != existing_role:
					raise ValueError(f"Không thể đổi vai trò ML của cột hệ thống cốt lõi '{existing.column_key}'.")
		else:
			if column_key is not None:
				new_key = str(column_key).strip().lower()
				if new_key != existing.column_key:
					if not _COLUMN_KEY_PATTERN.match(new_key):
						raise ValueError(
							"Mã cột chuẩn (column_key) phải bắt đầu bằng chữ cái thường và chỉ chứa a-z, 0-9, '_' (2-64 ký tự)."
						)
					if new_key in CORE_COLUMN_KEYS:
						raise ValueError(f"Không thể đổi khóa cột trùng với cột hệ thống cốt lõi '{new_key}'.")
					collision = self.metadata_repo.get_by_key(new_key)
					if collision is not None and collision.metadata_id != existing.metadata_id:
						raise ValueError(f"Cột chuẩn '{new_key}' đã tồn tại trong hệ thống.")
					existing.column_key = new_key
			if logical_type is not None:
				existing.logical_type = _as_enum(logical_type, LogicalDataType)
			if is_required is not None:
				existing.is_required = bool(is_required)
			if ml_role is not None:
				existing.ml_role = _as_enum(ml_role, ColumnMlRole)
			if is_active is not None:
				existing.is_active = bool(is_active)

		if display_name is not None:
			cleaned_name = str(display_name).strip()
			if not cleaned_name:
				raise ValueError("Tên hiển thị (display_name) không được để trống.")
			existing.display_name = cleaned_name

		if description is not None:
			existing.description = description.strip() if description.strip() else None

		if aliases is not None:
			existing.aliases = _normalize_aliases(existing.column_key, aliases)
		else:
			existing.aliases = _normalize_aliases(existing.column_key, existing.aliases)

		if display_order is not None:
			existing.display_order = int(display_order)

		existing.updated_at = datetime.now(timezone.utc)
		return self.metadata_repo.save(existing)

	def delete_column(self, metadata_id: UUID) -> None:
		existing = self.get_column(metadata_id)
		category_val = existing.category.value if hasattr(existing.category, "value") else str(existing.category)
		if category_val == ColumnCategory.CORE.value or existing.column_key in CORE_COLUMN_KEYS:
			raise ValueError(f"Không thể xóa cột hệ thống cốt lõi '{existing.column_key}'.")
		self.metadata_repo.delete(metadata_id)

	def get_active_metadata_map(self) -> Dict[str, SystemColumnMetadata]:
		return {m.column_key: m for m in self.list_columns(include_inactive=False)}

	def get_non_ml_columns(self) -> Set[str]:
		return build_non_ml_columns(self.list_columns(include_inactive=False))


__all__ = ["SystemMetadataService"]
