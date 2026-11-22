"""Authorization enforcement and management service."""
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from usfds_core.domain.entities.auth import (
	AccessTarget,
	ActorContext,
	AuthenticationError,
	BaseQueryFilter,
	Permission,
	PermissionDeniedError,
	ProjectActorContext,
	ProjectMember,
	Role,
	RolePermission,
)
from usfds_core.domain.entities.enums import GrantScope, RoleScope, UserStatus
from usfds_core.repositories.base_rbac_repo import (
	IPermissionRepository,
	IProjectMemberRepository,
	IRoleRepository,
)
from usfds_core.repositories.base_user_repo import IUserRepository
from usfds_core.services.auth.access_logic import (
	assert_grant_scopes,
	can_create as _can_create,
	can_list as _can_list,
	can_mutate as _can_mutate,
	can_read as _can_read,
	delegation_refusal,
	effective_scope,
	is_valid_role_key,
	role_change_refusal,
	sanitize_actor_context,
	super_admin_refusal,
)


class AuthzService:
	"""Loads ActorContext and enforces/manages 3-scope RBAC."""

	def __init__(
		self,
		user_repo: IUserRepository,
		role_repo: IRoleRepository,
		permission_repo: IPermissionRepository,
		member_repo: IProjectMemberRepository,
	) -> None:
		self.user_repo = user_repo
		self.role_repo = role_repo
		self.permission_repo = permission_repo
		self.member_repo = member_repo

	def get_actor_context(self, user_id: UUID) -> ActorContext:
		actor = self.user_repo.load_actor_context(user_id)
		if actor is None:
			raise AuthenticationError("Actor context not found")
		if str(actor.status) != UserStatus.ACTIVE.value:
			raise AuthenticationError("User account is disabled")
		return sanitize_actor_context(actor)

	def can_read(self, actor: ActorContext, permission: str, target: AccessTarget) -> bool:
		return _can_read(actor, permission, target)

	def can_mutate(self, actor: ActorContext, permission: str, target: AccessTarget) -> bool:
		return _can_mutate(actor, permission, target)

	def can_create(self, actor: ActorContext, permission: str, target: AccessTarget) -> bool:
		has_membership = self.member_repo.has_active_membership(actor.user_id, target.project_id)
		return _can_create(actor, permission, target, has_membership=has_membership)

	def can_list(
		self,
		actor: ActorContext,
		permission: str,
		active_project_ids: List[UUID],
		requested_project_ids: Optional[List[UUID]] = None,
	) -> List[BaseQueryFilter]:
		return _can_list(actor, permission, active_project_ids, requested_project_ids)

	def require_system_permission(self, actor: ActorContext, permission: str) -> None:
		if effective_scope(actor, permission, None) is None:
			raise PermissionDeniedError(f"Missing system permission: {permission}")

	def require_project_scope(self, actor: ActorContext, permission: str, project_id: UUID) -> GrantScope:
		scope = effective_scope(actor, permission, project_id)
		if scope is None:
			raise PermissionDeniedError(f"Missing permission {permission} on project {project_id}")
		return scope

	def resolve_project_list_owner(self, actor: ActorContext, permission: str, project_id: UUID) -> Optional[UUID]:
		filters = self.can_list(actor, permission, [project_id], [project_id])
		if not filters:
			raise PermissionDeniedError(f"Missing permission {permission} on project {project_id}")
		return filters[0].owner_id

	def require_project_permission(
		self,
		actor: ActorContext,
		permission: str,
		project_id: UUID,
		owner_id: Optional[UUID] = None,
		action: str = "read",
	) -> None:
		target = AccessTarget(project_id=project_id, owner_id=owner_id)
		if action == "create":
			allowed = self.can_create(actor, permission, target)
		elif action == "mutate":
			allowed = self.can_mutate(actor, permission, target)
		else:
			allowed = self.can_read(actor, permission, target)
		if not allowed:
			raise PermissionDeniedError(f"Missing permission {permission} on project {project_id}")

	def _resolve_role_grants(self, role_id: UUID) -> List[Tuple[str, GrantScope]]:
		perm_by_id: Dict[UUID, Permission] = {p.permission_id: p for p in self.permission_repo.list_all()}
		grants: List[Tuple[str, GrantScope]] = []
		for rp in self.role_repo.get_role_permissions(role_id):
			perm = perm_by_id.get(rp.permission_id)
			if perm is not None:
				grants.append((perm.code, rp.grant_scope))
		return grants

	def list_roles(self, actor: ActorContext, scope: Optional[RoleScope] = None) -> List[Tuple[Role, List[Tuple[str, GrantScope]]]]:
		if not actor.is_system_admin and effective_scope(actor, "role:read", None) is None:
			# Allow project_admins to list PROJECT roles for member assignment UI
			if scope != RoleScope.PROJECT or not any("project_admin" in p.role_keys for p in actor.projects):
				raise PermissionDeniedError("Missing permission: role:read")
		roles = self.role_repo.list_all(scope)
		perm_by_id: Dict[UUID, Permission] = {p.permission_id: p for p in self.permission_repo.list_all()}
		result: List[Tuple[Role, List[Tuple[str, GrantScope]]]] = []
		for r in roles:
			grants: List[Tuple[str, GrantScope]] = []
			for rp in self.role_repo.get_role_permissions(r.role_id):
				p = perm_by_id.get(rp.permission_id)
				if p is not None:
					grants.append((p.code, rp.grant_scope))
			result.append((r, grants))
		return result

	def list_permissions(self, actor: ActorContext) -> List[Permission]:
		self.require_system_permission(actor, "role:read")
		return self.permission_repo.list_all()

	def create_role(
		self,
		actor: ActorContext,
		name: str,
		display_name: str,
		scope: RoleScope,
		description: Optional[str] = None,
	) -> Role:
		self.require_system_permission(actor, "role:manage")
		if not is_valid_role_key(name):
			raise ValueError(f"Invalid role key: {name}")
		if self.role_repo.get_by_scope_and_name(scope, name) is not None:
			raise ValueError(f"Role {name} already exists in scope {scope.value}")
		role = Role(
			role_id=uuid4(),
			name=name,
			display_name=display_name,
			scope=scope,
			description=description,
			is_system=False,
		)
		return self.role_repo.save(role)

	def set_role_permissions(
		self,
		actor: ActorContext,
		role_id: UUID,
		grants: List[Tuple[str, GrantScope]],
	) -> List[RolePermission]:
		self.require_system_permission(actor, "role:manage")
		role = self.role_repo.get_by_id(role_id)
		if role is None:
			raise ValueError(f"Role {role_id} not found")
		refusal = super_admin_refusal(actor.is_system_admin, role.name, grants)
		if refusal:
			raise PermissionDeniedError(refusal)
		assert_grant_scopes(role.scope, grants)
		perm_by_code = {p.code: p for p in self.permission_repo.list_all()}
		rp_list: List[RolePermission] = []
		for perm_key, grant_scope in grants:
			perm = perm_by_code.get(perm_key)
			if perm is None:
				raise ValueError(f"Unknown permission key: {perm_key}")
			rp_list.append(RolePermission(role_id=role.role_id, permission_id=perm.permission_id, grant_scope=grant_scope))
		return self.role_repo.set_role_permissions(role.role_id, rp_list)

	def set_system_user_roles(self, actor: ActorContext, target_user_id: UUID, role_keys: List[str]) -> List[str]:
		self.require_system_permission(actor, "user:update")
		target_user = self.user_repo.get_by_id(target_user_id)
		if target_user is None:
			raise ValueError(f"User {target_user_id} not found")
		role_ids: List[UUID] = []
		resolved_keys: List[str] = []
		for key in dict.fromkeys(role_keys):
			role = self.role_repo.get_by_scope_and_name(RoleScope.SYSTEM, key)
			if role is None:
				raise ValueError(f"Unknown SYSTEM role: {key}")
			grants = self._resolve_role_grants(role.role_id)
			refusal = super_admin_refusal(actor.is_system_admin, role.name, grants)
			if refusal:
				raise PermissionDeniedError(refusal)
			role_ids.append(role.role_id)
			resolved_keys.append(role.name)
		self.role_repo.set_system_user_roles(target_user_id, role_ids, assigned_by=actor.user_id)
		return resolved_keys

	def list_project_members(self, actor: ActorContext, project_id: UUID) -> List[ProjectActorContext]:
		self.require_project_permission(actor, "project_member:read", project_id, action="read")
		return self.member_repo.load_project_actor_context(project_id)

	def add_project_member(
		self,
		actor: ActorContext,
		project_id: UUID,
		target_user_id: UUID,
		role_id: UUID,
	) -> ProjectMember:
		self.require_project_permission(actor, "project_member:manage", project_id, action="mutate")
		target_user = self.user_repo.get_by_id(target_user_id)
		if target_user is None:
			raise ValueError(f"User {target_user_id} not found")
		role = self.role_repo.get_by_id(role_id)
		if role is None:
			raise ValueError(f"Role {role_id} not found")
		if role.scope != RoleScope.PROJECT:
			raise PermissionDeniedError(f"Role {role.name} is not a PROJECT role")
		grants = self._resolve_role_grants(role.role_id)
		caller_project_ids = [p.project_id for p in actor.projects]
		refusal = delegation_refusal(
			actor=actor,
			caller_project_ids=caller_project_ids,
			project_id=project_id,
			role_name=role.name,
			role_scope=role.scope,
			grants=grants,
		)
		if refusal:
			raise PermissionDeniedError(refusal)
		return self.member_repo.add_member(project_id, target_user_id, role_id, added_by=actor.user_id)

	def update_project_member_role(
		self,
		actor: ActorContext,
		project_id: UUID,
		target_user_id: UUID,
		current_role_id: UUID,
		new_role_id: UUID,
	) -> ProjectMember:
		self.require_project_permission(actor, "project_member:manage", project_id, action="mutate")
		current_role = self.role_repo.get_by_id(current_role_id)
		new_role = self.role_repo.get_by_id(new_role_id)
		if current_role is None or new_role is None:
			raise ValueError("Role not found")
		if new_role.scope != RoleScope.PROJECT:
			raise PermissionDeniedError(f"Role {new_role.name} is not a PROJECT role")
		existing_roles = self.member_repo.list_user_roles_in_project(project_id, target_user_id)
		existing_names = [r.name for r in existing_roles]
		target_grants = self._resolve_role_grants(new_role.role_id)
		caller_project_ids = [p.project_id for p in actor.projects]
		refusal = role_change_refusal(
			actor=actor,
			caller_project_ids=caller_project_ids,
			project_id=project_id,
			existing_role_names=existing_names,
			target_role_name=new_role.name,
			target_role_scope=new_role.scope,
			target_grants=target_grants,
		)
		if refusal:
			raise PermissionDeniedError(refusal)
		if current_role.name == "project_admin" and new_role.name != "project_admin":
			if self.member_repo.count_role_members_in_project(project_id, "project_admin") <= 1:
				raise ValueError("Cannot downgrade the last project_admin in the project")
		self.member_repo.remove_member(project_id, target_user_id, current_role_id)
		return self.member_repo.add_member(project_id, target_user_id, new_role_id, added_by=actor.user_id)

	def remove_project_member(
		self,
		actor: ActorContext,
		project_id: UUID,
		target_user_id: UUID,
		role_id: UUID,
	) -> bool:
		self.require_project_permission(actor, "project_member:manage", project_id, action="mutate")
		role = self.role_repo.get_by_id(role_id)
		if role is None:
			raise ValueError(f"Role {role_id} not found")
		if role.name == "project_admin":
			if self.member_repo.count_role_members_in_project(project_id, "project_admin") <= 1:
				raise ValueError("Cannot remove the last project_admin in the project")
		return self.member_repo.remove_member(project_id, target_user_id, role_id)

	def remove_user_from_project(
		self,
		actor: ActorContext,
		project_id: UUID,
		target_user_id: UUID,
	) -> int:
		self.require_project_permission(actor, "project_member:manage", project_id, action="mutate")
		existing_roles = self.member_repo.list_user_roles_in_project(project_id, target_user_id)
		if any(r.name == "project_admin" for r in existing_roles):
			if self.member_repo.count_role_members_in_project(project_id, "project_admin") <= 1:
				raise ValueError("Cannot remove the last project_admin in the project")
		return self.member_repo.remove_user_from_project(project_id, target_user_id)

	def set_project_member_roles(
		self,
		actor: ActorContext,
		project_id: UUID,
		target_user_id: UUID,
		role_ids: List[UUID],
	) -> List[ProjectMember]:
		self.require_project_permission(actor, "project_member:manage", project_id, action="mutate")
		unique_role_ids = list(dict.fromkeys(role_ids))
		if not unique_role_ids:
			raise ValueError("At least one role_id is required")
		target_user = self.user_repo.get_by_id(target_user_id)
		if target_user is None:
			raise ValueError(f"User {target_user_id} not found")

		existing_roles = self.member_repo.list_user_roles_in_project(project_id, target_user_id)
		existing_names = [r.name for r in existing_roles]
		caller_project_ids = [p.project_id for p in actor.projects]

		resolved_roles: List[Role] = []
		for rid in unique_role_ids:
			role = self.role_repo.get_by_id(rid)
			if role is None:
				raise ValueError(f"Role {rid} not found")
			if role.scope != RoleScope.PROJECT:
				raise PermissionDeniedError(f"Role {role.name} is not a PROJECT role")
			target_grants = self._resolve_role_grants(role.role_id)
			refusal = role_change_refusal(
				actor=actor,
				caller_project_ids=caller_project_ids,
				project_id=project_id,
				existing_role_names=existing_names,
				target_role_name=role.name,
				target_role_scope=role.scope,
				target_grants=target_grants,
			)
			if refusal:
				raise PermissionDeniedError(refusal)
			resolved_roles.append(role)

		had_admin = "project_admin" in existing_names
		will_have_admin = any(r.name == "project_admin" for r in resolved_roles)
		if had_admin and not will_have_admin:
			if self.member_repo.count_role_members_in_project(project_id, "project_admin") <= 1:
				raise ValueError("Cannot downgrade the last project_admin in the project")

		self.member_repo.remove_user_from_project(project_id, target_user_id)
		return [
			self.member_repo.add_member(project_id, target_user_id, r.role_id, added_by=actor.user_id)
			for r in resolved_roles
		]
