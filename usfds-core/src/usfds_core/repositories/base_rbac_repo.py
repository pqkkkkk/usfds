"""Repository interfaces for Roles, Permissions, and Project Members."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from uuid import UUID

from usfds_core.domain.entities.auth import (
	Permission,
	ProjectActorContext,
	ProjectMember,
	Role,
	RolePermission,
)
from usfds_core.domain.entities.enums import RoleScope


class IRoleRepository(ABC):
	"""Abstract repository for RBAC roles and role-permission mappings."""

	@abstractmethod
	def save(self, role: Role) -> Role:
		pass

	@abstractmethod
	def get_by_id(self, role_id: UUID) -> Optional[Role]:
		pass

	@abstractmethod
	def get_by_scope_and_name(self, scope: RoleScope, name: str) -> Optional[Role]:
		pass

	@abstractmethod
	def list_all(self, scope: Optional[RoleScope] = None) -> List[Role]:
		pass

	@abstractmethod
	def get_role_permissions(self, role_id: UUID) -> List[RolePermission]:
		pass

	@abstractmethod
	def set_role_permissions(self, role_id: UUID, grants: List[RolePermission]) -> List[RolePermission]:
		pass

	@abstractmethod
	def get_system_user_role_ids(self, user_id: UUID) -> List[UUID]:
		pass

	@abstractmethod
	def set_system_user_roles(self, user_id: UUID, role_ids: List[UUID], assigned_by: Optional[UUID] = None) -> None:
		pass

	@abstractmethod
	def count_role_assignments(self, role_id: UUID) -> Dict[str, int]:
		pass

	@abstractmethod
	def delete(self, role_id: UUID) -> bool:
		pass


class IPermissionRepository(ABC):
	"""Abstract repository for RBAC permission catalog."""

	@abstractmethod
	def save(self, permission: Permission) -> Permission:
		pass

	@abstractmethod
	def get_by_id(self, permission_id: UUID) -> Optional[Permission]:
		pass

	@abstractmethod
	def get_by_code(self, code: str) -> Optional[Permission]:
		pass

	@abstractmethod
	def list_all(self) -> List[Permission]:
		pass


class IProjectMemberRepository(ABC):
	"""Abstract repository for project membership and ActorContext loading."""

	@abstractmethod
	def add_member(
		self,
		project_id: UUID,
		user_id: UUID,
		role_id: UUID,
		added_by: Optional[UUID] = None,
	) -> ProjectMember:
		pass

	@abstractmethod
	def remove_member(self, project_id: UUID, user_id: UUID, role_id: UUID) -> bool:
		pass

	@abstractmethod
	def remove_user_from_project(self, project_id: UUID, user_id: UUID) -> int:
		pass

	@abstractmethod
	def list_members(self, project_id: UUID) -> List[ProjectMember]:
		pass

	@abstractmethod
	def list_user_roles_in_project(self, project_id: UUID, user_id: UUID) -> List[Role]:
		pass

	@abstractmethod
	def list_user_project_ids(self, user_id: UUID) -> List[UUID]:
		pass

	@abstractmethod
	def has_active_membership(self, user_id: UUID, project_id: UUID) -> bool:
		pass

	@abstractmethod
	def count_role_members_in_project(self, project_id: UUID, role_name: str) -> int:
		pass

	@abstractmethod
	def load_project_actor_context(
		self,
		project_id: UUID,
		user_id: Optional[UUID] = None,
	) -> List[ProjectActorContext]:
		pass
