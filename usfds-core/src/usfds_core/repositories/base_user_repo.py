"""Repository interface for User persistence."""
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.auth import ActorContext
from usfds_core.domain.entities.system import User


class IUserRepository(ABC):
	"""Abstract repository for User entities."""

	@abstractmethod
	def save(self, user: User) -> User:
		pass

	@abstractmethod
	def get_by_id(self, user_id: UUID) -> Optional[User]:
		pass

	@abstractmethod
	def get_by_username(self, username: str) -> Optional[User]:
		pass

	@abstractmethod
	def get_by_email(self, email: str) -> Optional[User]:
		pass

	@abstractmethod
	def list_all(self) -> List[User]:
		pass

	@abstractmethod
	def delete(self, user_id: UUID) -> bool:
		pass

	@abstractmethod
	def load_actor_context(self, user_id: UUID) -> Optional[ActorContext]:
		pass
