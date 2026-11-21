"""Idempotent seeding of default canonical system columns (5 CORE + 2 DOMAIN)."""
from typing import List
from sqlalchemy.orm import Session

from usfds_core.domain.entities.system_metadata import SystemColumnMetadata
from usfds_core.domain.schemas.system_metadata import build_default_system_columns
from usfds_infra.database.repos.system_metadata import SqlSystemColumnMetadataRepository


def seed_system_metadata(session: Session) -> List[SystemColumnMetadata]:
	"""Idempotently seed the 5 CORE columns and 2 default DOMAIN columns (merchant, category)."""
	repo = SqlSystemColumnMetadataRepository(session)
	seeded: List[SystemColumnMetadata] = []
	for default_col in build_default_system_columns():
		existing = repo.get_by_key(default_col.column_key)
		if existing is None:
			seeded.append(repo.save(default_col))
		else:
			seeded.append(existing)
	session.flush()
	return seeded


__all__ = ["seed_system_metadata"]
