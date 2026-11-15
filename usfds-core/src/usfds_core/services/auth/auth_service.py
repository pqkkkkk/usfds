"""Authentication and user account lifecycle service."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from usfds_core.domain.entities.auth import AuthenticationError, UserSession
from usfds_core.domain.entities.enums import RoleScope, UserStatus
from usfds_core.domain.entities.system import User
from usfds_core.repositories.base_rbac_repo import IRoleRepository
from usfds_core.repositories.base_session_repo import IUserSessionRepository
from usfds_core.repositories.base_user_repo import IUserRepository
from usfds_core.services.auth.security import IPasswordHasher, ITokenProvider


class AuthService:
	"""Handles sign-in, token rotation, logout, self-service profile, and user account management."""

	def __init__(
		self,
		user_repo: IUserRepository,
		session_repo: IUserSessionRepository,
		role_repo: IRoleRepository,
		password_hasher: IPasswordHasher,
		token_provider: ITokenProvider,
		access_token_expire_minutes: int = 30,
		refresh_token_expire_days: int = 7,
	) -> None:
		self.user_repo = user_repo
		self.session_repo = session_repo
		self.role_repo = role_repo
		self.password_hasher = password_hasher
		self.token_provider = token_provider
		self.access_token_expire_minutes = access_token_expire_minutes
		self.refresh_token_expire_days = refresh_token_expire_days

	def login(
		self,
		username: str,
		password: str,
		user_agent: Optional[str] = None,
		ip_address: Optional[str] = None,
	) -> Tuple[User, str, str]:
		user = self.user_repo.get_by_username(username.strip())
		if user is None or not user.password_hash:
			raise AuthenticationError("Invalid username or password")
		if str(user.status) != UserStatus.ACTIVE.value:
			raise AuthenticationError("User account is disabled")
		if not self.password_hasher.verify(password, user.password_hash):
			raise AuthenticationError("Invalid username or password")

		now = datetime.now(timezone.utc)
		user.last_login_at = now
		user = self.user_repo.save(user)

		access_token = self.token_provider.create_access_token(
			user.user_id,
			user.username,
			timedelta(minutes=self.access_token_expire_minutes),
		)
		raw_refresh, refresh_hash = self.token_provider.generate_refresh_token()
		session = UserSession(
			user_id=user.user_id,
			refresh_token_hash=refresh_hash,
			expires_at=now + timedelta(days=self.refresh_token_expire_days),
			user_agent=user_agent,
			ip_address=ip_address,
		)
		self.session_repo.save(session)
		return user, access_token, raw_refresh

	def refresh(self, raw_refresh_token: str) -> Tuple[User, str, str]:
		token_hash = self.token_provider.hash_refresh_token(raw_refresh_token)
		session = self.session_repo.get_by_refresh_token_hash(token_hash)
		now = datetime.now(timezone.utc)

		if session is None or session.revoked_at is not None:
			raise AuthenticationError("Invalid or revoked refresh token")
		expires_at = session.expires_at
		if expires_at.tzinfo is None:
			expires_at = expires_at.replace(tzinfo=timezone.utc)
		if expires_at <= now:
			raise AuthenticationError("Refresh token expired")

		user = self.user_repo.get_by_id(session.user_id)
		if user is None or str(user.status) != UserStatus.ACTIVE.value:
			raise AuthenticationError("User account is disabled or missing")

		# Rotate refresh token
		self.session_repo.revoke_session(session.session_id, now)
		new_access = self.token_provider.create_access_token(
			user.user_id,
			user.username,
			timedelta(minutes=self.access_token_expire_minutes),
		)
		new_raw_refresh, new_refresh_hash = self.token_provider.generate_refresh_token()
		self.session_repo.save(
			UserSession(
				user_id=user.user_id,
				refresh_token_hash=new_refresh_hash,
				expires_at=now + timedelta(days=self.refresh_token_expire_days),
				user_agent=session.user_agent,
				ip_address=session.ip_address,
			)
		)
		return user, new_access, new_raw_refresh

	def logout(self, raw_refresh_token: str) -> None:
		token_hash = self.token_provider.hash_refresh_token(raw_refresh_token)
		session = self.session_repo.get_by_refresh_token_hash(token_hash)
		if session is not None and session.revoked_at is None:
			self.session_repo.revoke_session(session.session_id, datetime.now(timezone.utc))

	def verify_access_token(self, token: str) -> User:
		payload = self.token_provider.decode_access_token(token)
		sub = payload.get("sub")
		if not sub:
			raise AuthenticationError("Invalid access token")
		try:
			user_id = UUID(str(sub))
		except ValueError as exc:
			raise AuthenticationError("Invalid access token subject") from exc
		user = self.user_repo.get_by_id(user_id)
		if user is None or str(user.status) != UserStatus.ACTIVE.value:
			raise AuthenticationError("User account is disabled or missing")
		return user

	def update_own_profile(
		self,
		user_id: UUID,
		full_name: Optional[str] = None,
		email: Optional[str] = None,
	) -> User:
		user = self.user_repo.get_by_id(user_id)
		if user is None:
			raise LookupError(f"User {user_id} not found")
		if email is not None:
			cleaned_email = email.strip() or None
			if cleaned_email:
				existing = self.user_repo.get_by_email(cleaned_email)
				if existing is not None and existing.user_id != user_id:
					raise ValueError("Email is already in use")
			user.email = cleaned_email
		if full_name is not None:
			user.full_name = full_name.strip() or None
		return self.user_repo.save(user)

	def change_password(self, user_id: UUID, current_password: str, new_password: str) -> None:
		if len(new_password) < 6:
			raise ValueError("New password must be at least 6 characters")
		user = self.user_repo.get_by_id(user_id)
		if user is None:
			raise LookupError(f"User {user_id} not found")
		if not self.password_hasher.verify(current_password, user.password_hash):
			raise AuthenticationError("Current password is incorrect")
		user.password_hash = self.password_hasher.hash(new_password)
		self.user_repo.save(user)

	def create_user(
		self,
		username: str,
		password: str,
		email: Optional[str] = None,
		full_name: Optional[str] = None,
		system_role_names: Optional[List[str]] = None,
		assigned_by: Optional[UUID] = None,
	) -> User:
		clean_username = username.strip()
		if not clean_username:
			raise ValueError("Username is required")
		if len(password) < 6:
			raise ValueError("Password must be at least 6 characters")
		if self.user_repo.get_by_username(clean_username) is not None:
			raise ValueError(f"Username '{clean_username}' already exists")
		clean_email = email.strip() if email else None
		if clean_email and self.user_repo.get_by_email(clean_email) is not None:
			raise ValueError(f"Email '{clean_email}' already exists")

		user = self.user_repo.save(
			User(
				username=clean_username,
				email=clean_email,
				full_name=full_name.strip() if full_name else None,
				password_hash=self.password_hasher.hash(password),
				status=UserStatus.ACTIVE,
			)
		)
		role_names = system_role_names or ["system_member"]
		role_ids: List[UUID] = []
		for rname in role_names:
			role = self.role_repo.get_by_scope_and_name(RoleScope.SYSTEM, rname)
			if role is None:
				raise ValueError(f"Unknown system role: {rname}")
			role_ids.append(role.role_id)
		self.role_repo.set_system_user_roles(user.user_id, role_ids, assigned_by=assigned_by)
		return user

	def list_users(self) -> List[User]:
		return self.user_repo.list_all()

	def get_user(self, user_id: UUID) -> User:
		user = self.user_repo.get_by_id(user_id)
		if user is None:
			raise LookupError(f"User {user_id} not found")
		return user

	def update_user(
		self,
		user_id: UUID,
		full_name: Optional[str] = None,
		email: Optional[str] = None,
	) -> User:
		return self.update_own_profile(user_id, full_name=full_name, email=email)

	def set_user_status(self, user_id: UUID, status: UserStatus) -> User:
		user = self.user_repo.get_by_id(user_id)
		if user is None:
			raise LookupError(f"User {user_id} not found")
		user.status = status
		saved = self.user_repo.save(user)
		if status == UserStatus.DISABLED:
			self.session_repo.revoke_all_for_user(user_id, datetime.now(timezone.utc))
		return saved

	def reset_password(self, user_id: UUID, new_password: str) -> None:
		if len(new_password) < 6:
			raise ValueError("Password must be at least 6 characters")
		user = self.user_repo.get_by_id(user_id)
		if user is None:
			raise LookupError(f"User {user_id} not found")
		user.password_hash = self.password_hasher.hash(new_password)
		self.user_repo.save(user)
		self.session_repo.revoke_all_for_user(user_id, datetime.now(timezone.utc))
