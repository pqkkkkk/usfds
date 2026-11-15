"""Pure domain RBAC logic ported from src.zip (domain/access.ts + features/admin/rbac/rules.ts)."""
import re
from typing import Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from usfds_core.domain.entities.auth import (
	AccessTarget,
	ActorContext,
	BaseQueryFilter,
	PermissionDeniedError,
	ProjectPermissions,
)
from usfds_core.domain.entities.enums import GrantScope, RoleScope

SCOPE_RANK: Dict[GrantScope, int] = {
	GrantScope.OWN: 1,
	GrantScope.PROJECT: 2,
	GrantScope.SYSTEM: 3,
}

PROJECT_SCOPES = {GrantScope.OWN, GrantScope.PROJECT}
SYSTEM_SCOPES = {GrantScope.SYSTEM}

SYSTEM_ONLY_PERMISSIONS = frozenset({
	"user:read",
	"user:create",
	"user:update",
	"user:reset_password",
	"role:read",
	"role:manage",
	"model_builtin:manage",
	"audit:system_read",
	"project:create",
	"project:list_all",
	"project:list_own",
	"own:profile_read",
	"own:profile_update",
	"own:password_change",
	"own:session_manage",
})

PROTECTED_ROLE_KEYS = frozenset({"system_admin"})


def _keep_scopes(permissions: Dict[str, List[GrantScope]], allowed: set[GrantScope]) -> Dict[str, List[GrantScope]]:
	kept: Dict[str, List[GrantScope]] = {}
	for key, scopes in permissions.items():
		valid = [s for s in scopes if s in allowed]
		if valid:
			kept[key] = valid
	return kept


def sanitize_actor_context(actor: ActorContext) -> ActorContext:
	"""Drop scopes outside each role branch: project roles keep OWN/PROJECT, system roles keep SYSTEM."""
	return ActorContext(
		user_id=actor.user_id,
		username=actor.username,
		status=actor.status,
		projects=[
			ProjectPermissions(
				project_id=p.project_id,
				role_keys=list(p.role_keys),
				permissions=_keep_scopes(p.permissions, PROJECT_SCOPES),
			)
			for p in actor.projects
		],
		system_role_keys=list(actor.system_role_keys),
		system_permissions=_keep_scopes(actor.system_permissions, SYSTEM_SCOPES),
		is_system_admin=actor.is_system_admin,
	)


def scope_covers(held: GrantScope, wanted: GrantScope) -> bool:
	return SCOPE_RANK[held] >= SCOPE_RANK[wanted]


def broadest_scope(scopes: Iterable[GrantScope]) -> Optional[GrantScope]:
	best: Optional[GrantScope] = None
	for scope in scopes:
		if best is None or SCOPE_RANK[scope] > SCOPE_RANK[best]:
			best = scope
	return best


def held_scope(
	role_scope: RoleScope,
	held_branch: RoleScope,
	permission_code: str,
	grant: GrantScope,
) -> Optional[GrantScope]:
	if held_branch == RoleScope.SYSTEM:
		return GrantScope.SYSTEM if (role_scope != RoleScope.PROJECT and grant == GrantScope.SYSTEM) else None
	if role_scope == RoleScope.SYSTEM or permission_code in SYSTEM_ONLY_PERMISSIONS:
		return None
	if grant == GrantScope.SYSTEM:
		return None
	return grant


def effective_scope(
	actor: ActorContext,
	permission: str,
	project_id: Optional[UUID] = None,
) -> Optional[GrantScope]:
	"""Broadest scope across the system branch and (optionally) one project."""
	if actor.is_system_admin:
		return GrantScope.SYSTEM
	scopes: List[GrantScope] = list(actor.system_permissions.get(permission, []))
	if project_id is not None:
		proj = next((p for p in actor.projects if p.project_id == project_id), None)
		if proj is not None:
			scopes.extend(proj.permissions.get(permission, []))
	return broadest_scope(scopes)


def permission_projects(actor: ActorContext, permission: str) -> Optional[List[UUID]]:
	"""Return None if held globally (SYSTEM), else sorted list of project_ids holding the permission."""
	if actor.is_system_admin or permission in actor.system_permissions:
		return None
	return sorted(
		[p.project_id for p in actor.projects if permission in p.permissions],
		key=str,
	)


def can_access_record(actor: ActorContext, permission: str, resource: AccessTarget) -> bool:
	scope = effective_scope(actor, permission, resource.project_id)
	if scope is None:
		return False
	if scope == GrantScope.OWN:
		return resource.owner_id is not None and actor.user_id == resource.owner_id
	return True


def can_read(actor: ActorContext, permission: str, resource: AccessTarget) -> bool:
	return can_access_record(actor, permission, resource)


def can_mutate(actor: ActorContext, permission: str, resource: AccessTarget) -> bool:
	return can_access_record(actor, permission, resource)


def can_create(
	actor: ActorContext,
	permission: str,
	target: AccessTarget,
	has_membership: bool = True,
) -> bool:
	scope = effective_scope(actor, permission, target.project_id)
	if scope is None:
		return False
	if scope == GrantScope.SYSTEM:
		return True
	if not has_membership:
		return False
	if scope == GrantScope.OWN:
		return target.owner_id is None or actor.user_id == target.owner_id
	return True


def group_by_owner(
	actor_id: UUID,
	scoped: List[Tuple[UUID, Optional[GrantScope]]],
) -> List[BaseQueryFilter]:
	every_owner = [pid for pid, scope in scoped if scope in (GrantScope.PROJECT, GrantScope.SYSTEM)]
	own_only = [pid for pid, scope in scoped if scope == GrantScope.OWN]
	filters: List[BaseQueryFilter] = []
	if every_owner:
		filters.append(BaseQueryFilter(project_ids=every_owner, owner_id=None))
	if own_only:
		filters.append(BaseQueryFilter(project_ids=own_only, owner_id=actor_id))
	return filters


def can_list(
	actor: ActorContext,
	permission: str,
	active_project_ids: List[UUID],
	requested_project_ids: Optional[List[UUID]] = None,
) -> List[BaseQueryFilter]:
	active_set = set(active_project_ids)
	requested = list(dict.fromkeys(requested_project_ids)) if requested_project_ids else None
	target_ids = requested if requested is not None else active_project_ids
	scoped: List[Tuple[UUID, Optional[GrantScope]]] = [
		(pid, effective_scope(actor, permission, pid) if pid in active_set else None)
		for pid in target_ids
	]
	denied = [pid for pid, scope in scoped if scope is None]
	if requested is not None and denied:
		raise PermissionDeniedError(f"Missing permission {permission} for projects: {', '.join(str(p) for p in denied)}")
	return group_by_owner(actor.user_id, scoped)


def is_valid_role_key(key: str) -> bool:
	return bool(re.match(r"^[a-z0-9][a-z0-9_-]{1,63}$", key))


def assert_grant_scopes(role_scope: RoleScope, grants: List[Tuple[str, GrantScope]]) -> None:
	allowed = SYSTEM_SCOPES if role_scope == RoleScope.SYSTEM else PROJECT_SCOPES
	for perm_key, scope in grants:
		if scope not in allowed:
			raise PermissionDeniedError(f"Grant scope {scope.value} is not allowed for {role_scope.value} role")
		if role_scope == RoleScope.PROJECT and perm_key in SYSTEM_ONLY_PERMISSIONS:
			raise PermissionDeniedError(f"System-only permission {perm_key} cannot be granted to a PROJECT role")


def assert_scope_change_allowed(
	current_scope: RoleScope,
	next_scope: RoleScope,
	assignment_counts: Dict[str, int],
) -> None:
	if current_scope == next_scope:
		return
	total = sum(assignment_counts.values())
	if total > 0:
		raise ValueError(f"Cannot change role scope while assigned ({total} active assignments)")


def super_admin_refusal(
	caller_is_system_admin: bool,
	role_name: str,
	grants: List[Tuple[str, GrantScope]],
) -> Optional[str]:
	if caller_is_system_admin:
		return None
	if role_name == "system_admin":
		return "Only system_admin can manage or assign system_admin"
	for perm_key, _ in grants:
		if perm_key in SYSTEM_ONLY_PERMISSIONS:
			return f"Only system_admin can grant system-only permission {perm_key}"
	return None


def delegation_refusal(
	actor: ActorContext,
	caller_project_ids: List[UUID],
	project_id: UUID,
	role_name: str,
	role_scope: RoleScope,
	grants: List[Tuple[str, GrantScope]],
) -> Optional[str]:
	if actor.is_system_admin:
		return None
	sup = super_admin_refusal(actor.is_system_admin, role_name, grants)
	if sup:
		return sup
	if role_scope != RoleScope.PROJECT:
		return "Only system_admin can assign SYSTEM roles"
	if project_id not in caller_project_ids:
		return "Caller is not a manager of the target project"
	for perm_key, scope in grants:
		held = effective_scope(actor, perm_key, project_id)
		if held is None or not scope_covers(held, scope):
			return f"Cannot delegate permission {perm_key}:{scope.value} that caller does not hold"
	return None


def role_change_refusal(
	actor: ActorContext,
	caller_project_ids: List[UUID],
	project_id: UUID,
	existing_role_names: List[str],
	target_role_name: str,
	target_role_scope: RoleScope,
	target_grants: List[Tuple[str, GrantScope]],
) -> Optional[str]:
	if actor.is_system_admin:
		return None
	if "system_admin" in existing_role_names:
		return "Only system_admin can modify a system_admin user"
	return delegation_refusal(
		actor=actor,
		caller_project_ids=caller_project_ids,
		project_id=project_id,
		role_name=target_role_name,
		role_scope=target_role_scope,
		grants=target_grants,
	)
