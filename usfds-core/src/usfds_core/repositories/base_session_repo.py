"""Repository interface for UserSession persistence."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.auth import UserSession


class IUserSessionRepository(ABC):
	"""Abstract repository for refresh token sessions."""

	@abstractmethod
	def save(self, session: UserSession) -> UserSession:
		pass

	@abstractmethod
	def get_by_id(self, session_id: UUID) -> Optional[UserSession]:
		pass

	@abstractmethod
	def get_by_refresh_token_hash(self, token_hash: str) -> Optional[UserSession]:
		pass

	@abstractmethod
	def list_for_user(self, user_id: UUID) -> List[UserSession]:
		pass

	@abstractmethod
	def revoke_session(self, session_id: UUID, revoked_at: datetime) -> bool:
		pass

	@abstractmethod
	def revoke_all_for_user(self, user_id: UUID, revoked_at: datetime) -> int:
		pass
