"""Domain entities and errors for Authentication & 3-Scope RBAC."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import GrantScope, RoleScope, UserStatus


class AuthenticationError(Exception):
	"""Raised when authentication fails or a token/session is invalid."""


class PermissionDeniedError(PermissionError):
	"""Raised when an actor lacks the required permission or scope."""

	def __init__(self, message: str = "Permission denied", code: str = "FORBIDDEN") -> None:
		super().__init__(message)
		self.code = code


@dataclass
class Role:
	"""RBAC role definition at SYSTEM or PROJECT scope."""
	name: str
	display_name: str
	scope: Union[RoleScope, str]
	role_id: UUID = field(default_factory=uuid4)
	is_system: bool = False
	description: Optional[str] = None
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Permission:
	"""Catalog entry for a resource:action permission."""
	code: str
	resource: str
	action: str
	scope: Union[GrantScope, str]
	permission_id: UUID = field(default_factory=uuid4)
	description: Optional[str] = None


@dataclass
class RolePermission:
	"""Permission grant attached to a role with a specific grant scope."""
	role_id: UUID
	permission_id: UUID
	grant_scope: Union[GrantScope, str] = GrantScope.PROJECT


@dataclass
class ProjectMember:
	"""Membership linking a user and a role inside a project."""
	project_id: UUID
	user_id: UUID
	role_id: UUID
	added_by: Optional[UUID] = None
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserSession:
	"""Refresh token session for a user."""
	user_id: UUID
	refresh_token_hash: str
	expires_at: datetime
	session_id: UUID = field(default_factory=uuid4)
	revoked_at: Optional[datetime] = None
	user_agent: Optional[str] = None
	ip_address: Optional[str] = None
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ProjectPermissions:
	"""Resolved permissions for an actor inside a single project."""
	project_id: UUID
	role_keys: List[str] = field(default_factory=list)
	permissions: Dict[str, List[GrantScope]] = field(default_factory=dict)


@dataclass
class ProjectActorContext:
	"""Resolved authorization context for a single member inside a single project."""
	project_id: UUID
	user_id: UUID
	username: str
	full_name: Optional[str] = None
	email: Optional[str] = None
	status: Union[UserStatus, str] = UserStatus.ACTIVE
	roles: List[Role] = field(default_factory=list)
	role_keys: List[str] = field(default_factory=list)
	permissions: Dict[str, List[GrantScope]] = field(default_factory=dict)
	added_by: Optional[UUID] = None
	created_at: Optional[datetime] = None


@dataclass
class ActorContext:
	"""Central authorization context loaded once per request."""
	user_id: UUID
	username: str
	status: Union[UserStatus, str] = UserStatus.ACTIVE
	projects: List[ProjectPermissions] = field(default_factory=list)
	system_role_keys: List[str] = field(default_factory=list)
	system_permissions: Dict[str, List[GrantScope]] = field(default_factory=dict)
	is_system_admin: bool = False


@dataclass
class AccessTarget:
	"""Target resource for can_read / can_create / can_mutate checks."""
	project_id: UUID
	owner_id: Optional[UUID] = None


@dataclass
class BaseQueryFilter:
	"""Scoped query filter returned by can_list."""
	project_ids: List[UUID]
	owner_id: Optional[UUID] = None
