from abc import ABC, abstractmethod
from uuid import UUID

from usfds_core.domain.entities.case import AuditLog, Case, EntityBlacklist


class CaseConflictError(ValueError):
	pass


class ICaseRepository(ABC):
	@abstractmethod
	def save(self, case: Case, expected_version: int | None = None) -> Case:
		raise NotImplementedError

	@abstractmethod
	def get_by_id(self, case_id: UUID) -> Case | None:
		raise NotImplementedError

	@abstractmethod
	def get_by_event(self, project_id: UUID, event_id: str) -> Case | None:
		raise NotImplementedError

	@abstractmethod
	def list_by_project(self, project_id: UUID) -> list[Case]:
		raise NotImplementedError


class IBlacklistRepository(ABC):
	@abstractmethod
	def save(self, entry: EntityBlacklist) -> EntityBlacklist:
		raise NotImplementedError

	@abstractmethod
	def list_by_project(self, project_id: UUID) -> list[EntityBlacklist]:
		raise NotImplementedError


class IAuditRepository(ABC):
	@abstractmethod
	def append(self, log: AuditLog) -> None:
		raise NotImplementedError

	@abstractmethod
	def list_for_entity(self, project_id: UUID, entity_type: str, entity_id: str) -> list[AuditLog]:
		raise NotImplementedError