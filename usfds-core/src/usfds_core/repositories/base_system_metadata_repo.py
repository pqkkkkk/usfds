from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.system_metadata import SystemColumnMetadata


class ISystemColumnMetadataRepository(ABC):
	"""Repository interface for canonical system & domain column metadata."""

	@abstractmethod
	def list_all(self, include_inactive: bool = False) -> List[SystemColumnMetadata]:
		"""List column metadata definitions ordered by display_order and column_key."""
		raise NotImplementedError

	@abstractmethod
	def get_by_id(self, metadata_id: UUID) -> Optional[SystemColumnMetadata]:
		"""Retrieve a column metadata definition by its UUID."""
		raise NotImplementedError

	@abstractmethod
	def get_by_key(self, column_key: str) -> Optional[SystemColumnMetadata]:
		"""Retrieve a column metadata definition by its canonical column_key."""
		raise NotImplementedError

	@abstractmethod
	def save(self, metadata: SystemColumnMetadata) -> SystemColumnMetadata:
		"""Create or update a column metadata definition."""
		raise NotImplementedError

	@abstractmethod
	def delete(self, metadata_id: UUID) -> None:
		"""Delete a column metadata definition by UUID."""
		raise NotImplementedError


__all__ = ["ISystemColumnMetadataRepository"]
