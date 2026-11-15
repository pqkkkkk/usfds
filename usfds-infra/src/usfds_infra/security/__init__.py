"""Concrete password hashing (bcrypt) and JWT token provider (PyJWT)."""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Dict, Tuple
from uuid import UUID

import bcrypt
import jwt

from usfds_core.domain.entities.auth import AuthenticationError
from usfds_core.services.auth.security import IPasswordHasher, ITokenProvider


class PasswordHasher(IPasswordHasher):
	"""Bcrypt-based password hasher."""

	def hash(self, password: str) -> str:
		return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

	def verify(self, password: str, password_hash: str) -> bool:
		if not password_hash:
			return False
		try:
			return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
		except ValueError:
			return False


class JwtTokenProvider(ITokenProvider):
	"""HS256 JWT access token + SHA-256 hashed opaque refresh token provider."""

	def __init__(self, secret_key: str, algorithm: str = "HS256") -> None:
		self.secret_key = secret_key
		self.algorithm = algorithm

	def create_access_token(
		self,
		user_id: UUID,
		username: str,
		expires_delta: timedelta,
	) -> str:
		now = datetime.now(timezone.utc)
		payload = {
			"sub": str(user_id),
			"username": username,
			"iat": now,
			"exp": now + expires_delta,
		}
		return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

	def decode_access_token(self, token: str) -> Dict[str, Any]:
		try:
			return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
		except jwt.PyJWTError as exc:
			raise AuthenticationError(f"Invalid or expired token: {exc}") from exc

	def generate_refresh_token(self) -> Tuple[str, str]:
		raw = secrets.token_urlsafe(48)
		return raw, self.hash_refresh_token(raw)

	def hash_refresh_token(self, raw_token: str) -> str:
		return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
