"""Security protocol interfaces for password hashing and JWT/token operations."""
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Dict, Tuple
from uuid import UUID


class IPasswordHasher(ABC):
	"""Abstract password hasher."""

	@abstractmethod
	def hash(self, password: str) -> str:
		pass

	@abstractmethod
	def verify(self, password: str, password_hash: str) -> bool:
		pass


class ITokenProvider(ABC):
	"""Abstract access/refresh token provider."""

	@abstractmethod
	def create_access_token(
		self,
		user_id: UUID,
		username: str,
		expires_delta: timedelta,
	) -> str:
		pass

	@abstractmethod
	def decode_access_token(self, token: str) -> Dict[str, Any]:
		pass

	@abstractmethod
	def generate_refresh_token(self) -> Tuple[str, str]:
		"""Return (raw_token, token_hash)."""
		pass

	@abstractmethod
	def hash_refresh_token(self, raw_token: str) -> str:
		pass
