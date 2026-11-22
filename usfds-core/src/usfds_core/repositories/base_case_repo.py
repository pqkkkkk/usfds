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

	def get_case_ids_by_events(self, project_id: UUID, event_ids: list[str]) -> dict[str, str]:
		"""event_id -> case_id for the given events of one project (override with a single IN query)."""
		found = {event_id: self.get_by_event(project_id, event_id) for event_id in event_ids}
		return {event_id: str(case.case_id) for event_id, case in found.items() if case is not None}


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