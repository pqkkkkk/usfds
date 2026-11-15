"""FastAPI dependency providers for Authentication & RBAC."""
from typing import Optional
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from usfds_core.domain.entities.auth import ActorContext, AuthenticationError
from usfds_core.domain.entities.enums import AuthMode
from usfds_core.domain.entities.system import User
from usfds_core.services.auth.auth_service import AuthService
from usfds_core.services.auth.authz_service import AuthzService
from usfds_infra.database.repos.auth import (
	SqlPermissionRepository,
	SqlProjectMemberRepository,
	SqlRoleRepository,
	SqlUserRepository,
	SqlUserSessionRepository,
)
from usfds_infra.security import JwtTokenProvider, PasswordHasher
from usfds_server.config import settings
from usfds_server.dependencies import get_db


def get_password_hasher() -> PasswordHasher:
	return PasswordHasher()


def get_token_provider() -> JwtTokenProvider:
	return JwtTokenProvider(secret_key=settings.jwt_secret)


def get_user_repo(db: Session = Depends(get_db)) -> SqlUserRepository:
	return SqlUserRepository(db)


def get_session_repo(db: Session = Depends(get_db)) -> SqlUserSessionRepository:
	return SqlUserSessionRepository(db)


def get_role_repo(db: Session = Depends(get_db)) -> SqlRoleRepository:
	return SqlRoleRepository(db)


def get_permission_repo(db: Session = Depends(get_db)) -> SqlPermissionRepository:
	return SqlPermissionRepository(db)


def get_project_member_repo(db: Session = Depends(get_db)) -> SqlProjectMemberRepository:
	return SqlProjectMemberRepository(db)


def get_auth_service(
	user_repo: SqlUserRepository = Depends(get_user_repo),
	session_repo: SqlUserSessionRepository = Depends(get_session_repo),
	role_repo: SqlRoleRepository = Depends(get_role_repo),
	password_hasher: PasswordHasher = Depends(get_password_hasher),
	token_provider: JwtTokenProvider = Depends(get_token_provider),
) -> AuthService:
	return AuthService(
		user_repo=user_repo,
		session_repo=session_repo,
		role_repo=role_repo,
		password_hasher=password_hasher,
		token_provider=token_provider,
		access_token_expire_minutes=settings.access_token_expire_minutes,
		refresh_token_expire_days=settings.refresh_token_expire_days,
	)


def get_current_user(
	authorization: Optional[str] = Header(default=None),
	auth_service: AuthService = Depends(get_auth_service),
	user_repo: SqlUserRepository = Depends(get_user_repo),
) -> User:
	"""Resolve the authenticated User from Bearer JWT (required) or bootstrap admin (local_auto)."""
	if settings.auth_mode == AuthMode.LOCAL_AUTO.value:
		if authorization and authorization.startswith("Bearer "):
			token = authorization[len("Bearer "):].strip()
			if token:
				return auth_service.verify_access_token(token)
		user = user_repo.get_by_username(settings.bootstrap_admin_username)
		if user is None:
			raise AuthenticationError("Bootstrap local admin user not initialized")
		return user

	if not authorization or not authorization.startswith("Bearer "):
		raise AuthenticationError("Authentication required")
	token = authorization[len("Bearer "):].strip()
	if not token:
		raise AuthenticationError("Authentication required")
	return auth_service.verify_access_token(token)


def get_authz_service(
	user_repo: SqlUserRepository = Depends(get_user_repo),
	role_repo: SqlRoleRepository = Depends(get_role_repo),
	permission_repo: SqlPermissionRepository = Depends(get_permission_repo),
	member_repo: SqlProjectMemberRepository = Depends(get_project_member_repo),
) -> AuthzService:
	return AuthzService(
		user_repo=user_repo,
		role_repo=role_repo,
		permission_repo=permission_repo,
		member_repo=member_repo,
	)


def get_actor_context(
	current_user: User = Depends(get_current_user),
	authz_service: AuthzService = Depends(get_authz_service),
) -> ActorContext:
	"""Load the sanitized ActorContext for the current user."""
	return authz_service.get_actor_context(current_user.user_id)


def require_system_permission(permission_code: str):
	"""FastAPI dependency enforcing a SYSTEM-scoped permission."""
	def _dep(
		actor: ActorContext = Depends(get_actor_context),
		authz: AuthzService = Depends(get_authz_service),
	) -> ActorContext:
		authz.require_system_permission(actor, permission_code)
		return actor
	return _dep
