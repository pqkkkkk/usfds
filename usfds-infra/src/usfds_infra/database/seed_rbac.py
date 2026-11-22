"""Idempotent RBAC seeding and legacy project member backfill."""
from typing import Dict, List, Tuple
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from usfds_core.domain.entities.enums import GrantScope, RoleScope, UserStatus
from usfds_core.domain.entities.auth import Permission, Role, RolePermission
from usfds_core.domain.entities.system import User
from usfds_infra.database.models import PermissionModel, ProjectModel, RolePermissionModel, SystemUserRoleModel
from usfds_infra.database.repos.auth import (
	SqlPermissionRepository,
	SqlProjectMemberRepository,
	SqlRoleRepository,
	SqlUserRepository,
)

# (code, resource, action, default_scope, description)
PERMISSION_CATALOG: List[Tuple[str, str, str, GrantScope, str]] = [
	("user:read", "user", "read", GrantScope.SYSTEM, "View users"),
	("user:create", "user", "create", GrantScope.SYSTEM, "Create users"),
	("user:update", "user", "update", GrantScope.SYSTEM, "Update users and status"),
	("user:reset_password", "user", "reset_password", GrantScope.SYSTEM, "Reset user passwords"),
	("role:read", "role", "read", GrantScope.SYSTEM, "View roles and permissions"),
	("role:manage", "role", "manage", GrantScope.SYSTEM, "Create/update roles and role permissions"),
	("model_builtin:manage", "model_builtin", "manage", GrantScope.SYSTEM, "Manage built-in models"),
	("system_metadata:manage", "system_metadata", "manage", GrantScope.SYSTEM, "Manage system column metadata"),
	("audit:system_read", "audit", "system_read", GrantScope.SYSTEM, "Read system-wide audit logs"),
	("own:profile_read", "own", "profile_read", GrantScope.OWN, "Read own profile"),
	("own:profile_update", "own", "profile_update", GrantScope.OWN, "Update own profile"),
	("own:password_change", "own", "password_change", GrantScope.OWN, "Change own password"),
	("own:session_manage", "own", "session_manage", GrantScope.OWN, "Manage own sessions"),
	("project:create", "project", "create", GrantScope.SYSTEM, "Create new projects"),
	("project:list_all", "project", "list_all", GrantScope.SYSTEM, "List all projects across system"),
	("project:list_own", "project", "list_own", GrantScope.OWN, "List projects where user is a member"),
	("project:read", "project", "read", GrantScope.PROJECT, "View project details"),
	("project:update", "project", "update", GrantScope.PROJECT, "Update project settings"),
	("project:delete", "project", "delete", GrantScope.PROJECT, "Delete project"),
	("project:reset_schema", "project", "reset_schema", GrantScope.PROJECT, "Reset project RAW schema"),
	("project_member:read", "project_member", "read", GrantScope.PROJECT, "List project members"),
	("project_member:manage", "project_member", "manage", GrantScope.PROJECT, "Add/remove project members"),
	("dataset:create", "dataset", "create", GrantScope.PROJECT, "Create/upload datasets"),
	("dataset:read", "dataset", "read", GrantScope.PROJECT, "View datasets and profiles"),
	("dataset:update", "dataset", "update", GrantScope.PROJECT, "Update/preprocess datasets"),
	("dataset:delete", "dataset", "delete", GrantScope.PROJECT, "Delete datasets"),
	("dataset:export", "dataset", "export", GrantScope.PROJECT, "Export/download datasets"),
	("model:create", "model", "create", GrantScope.PROJECT, "Register models"),
	("model:read", "model", "read", GrantScope.PROJECT, "View models and versions"),
	("model:update", "model", "update", GrantScope.PROJECT, "Update models and versions"),
	("training:create", "training", "create", GrantScope.PROJECT, "Start training runs"),
	("training:read", "training", "read", GrantScope.PROJECT, "View training runs"),
	("deployment:deploy", "deployment", "deploy", GrantScope.PROJECT, "Deploy model version"),
	("deployment:undeploy", "deployment", "undeploy", GrantScope.PROJECT, "Undeploy model version"),
	("rule:create", "rule", "create", GrantScope.PROJECT, "Create rules"),
	("rule:read", "rule", "read", GrantScope.PROJECT, "View rules"),
	("rule:update", "rule", "update", GrantScope.PROJECT, "Update rules"),
	("rule:delete", "rule", "delete", GrantScope.PROJECT, "Delete rules"),
	("rule:dry_run", "rule", "dry_run", GrantScope.PROJECT, "Dry-run rules"),
	("rule:deploy", "rule", "deploy", GrantScope.PROJECT, "Deploy/activate rules"),
	("rule:undeploy", "rule", "undeploy", GrantScope.PROJECT, "Deactivate rules"),
	("detection:create", "detection", "create", GrantScope.PROJECT, "Run batch detection"),
	("detection:read", "detection", "read", GrantScope.PROJECT, "View detection jobs and results"),
	("detection:export", "detection", "export", GrantScope.PROJECT, "Export detection job results"),
	("case:create", "case", "create", GrantScope.PROJECT, "Create investigation cases from detection"),
	("case:read", "case", "read", GrantScope.PROJECT, "View investigation cases"),
	("case:assign", "case", "assign", GrantScope.PROJECT, "Assign investigation cases"),
	("case:claim", "case", "claim", GrantScope.PROJECT, "Claim unassigned cases"),
	("case:manual_review", "case", "manual_review", GrantScope.PROJECT, "Perform manual case review"),
	("case:escalate", "case", "escalate", GrantScope.PROJECT, "Escalate cases"),
	("case:reopen", "case", "reopen", GrantScope.PROJECT, "Reopen closed cases"),
	("blacklist:manage", "blacklist", "manage", GrantScope.PROJECT, "Manage entity blacklist"),
	("report:read", "report", "read", GrantScope.PROJECT, "View insight reports"),
	("report:create", "report", "create", GrantScope.PROJECT, "Generate insight reports"),
	("report:export", "report", "export", GrantScope.PROJECT, "Export insight reports"),
	("audit:read", "audit", "read", GrantScope.PROJECT, "Read project/case audit logs"),
]

BUILTIN_ROLES: List[Tuple[str, str, RoleScope, str]] = [
	("system_admin", "System Administrator", RoleScope.SYSTEM, "Full system and project administration"),
	("system_member", "System Member", RoleScope.SYSTEM, "Standard user with access to own and member projects"),
	("project_admin", "Project Admin", RoleScope.PROJECT, "Project owner/administrator"),
	("data_scientist", "Data Scientist", RoleScope.PROJECT, "Datasets, models, training, rules, and detection"),
	("fraud_analyst", "Fraud Analyst", RoleScope.PROJECT, "Case investigation, blacklist, rule proposals, and reports"),
]

ROLE_GRANTS: Dict[str, List[Tuple[str, GrantScope]]] = {
	"system_admin": [(code, GrantScope.SYSTEM) for code, *_ in PERMISSION_CATALOG],
	"system_member": [
		("project:create", GrantScope.SYSTEM),
		("project:list_own", GrantScope.SYSTEM),
		("own:profile_read", GrantScope.SYSTEM),
		("own:profile_update", GrantScope.SYSTEM),
		("own:password_change", GrantScope.SYSTEM),
		("own:session_manage", GrantScope.SYSTEM),
	],
	"project_admin": [
		("project:read", GrantScope.PROJECT),
		("project:update", GrantScope.PROJECT),
		("project:delete", GrantScope.PROJECT),
		("project:reset_schema", GrantScope.PROJECT),
		("project_member:read", GrantScope.PROJECT),
		("project_member:manage", GrantScope.PROJECT),
		("dataset:read", GrantScope.PROJECT),
		("dataset:delete", GrantScope.PROJECT),
		("dataset:export", GrantScope.PROJECT),
		("model:read", GrantScope.PROJECT),
		("model:update", GrantScope.PROJECT),
		("training:read", GrantScope.PROJECT),
		("deployment:deploy", GrantScope.PROJECT),
		("deployment:undeploy", GrantScope.PROJECT),
		("rule:read", GrantScope.PROJECT),
		("rule:deploy", GrantScope.PROJECT),
		("rule:undeploy", GrantScope.PROJECT),
		("rule:delete", GrantScope.PROJECT),
		("detection:create", GrantScope.PROJECT),
		("detection:read", GrantScope.PROJECT),
		("detection:export", GrantScope.PROJECT),
		("case:create", GrantScope.PROJECT),
		("case:read", GrantScope.PROJECT),
		("case:assign", GrantScope.PROJECT),
		("report:read", GrantScope.PROJECT),
		("report:create", GrantScope.PROJECT),
		("report:export", GrantScope.PROJECT),
		("audit:read", GrantScope.PROJECT),
	],
	"data_scientist": [
		("project:read", GrantScope.PROJECT),
		("dataset:create", GrantScope.OWN),
		("dataset:read", GrantScope.PROJECT),
		("dataset:update", GrantScope.OWN),
		("dataset:delete", GrantScope.OWN),
		("dataset:export", GrantScope.PROJECT),
		("model:create", GrantScope.OWN),
		("model:read", GrantScope.PROJECT),
		("model:update", GrantScope.OWN),
		("training:create", GrantScope.OWN),
		("training:read", GrantScope.PROJECT),
		("deployment:deploy", GrantScope.OWN),
		("deployment:undeploy", GrantScope.OWN),
		("rule:create", GrantScope.OWN),
		("rule:read", GrantScope.PROJECT),
		("rule:update", GrantScope.OWN),
		("rule:delete", GrantScope.OWN),
		("rule:dry_run", GrantScope.PROJECT),
		("rule:deploy", GrantScope.OWN),
		("rule:undeploy", GrantScope.OWN),
		("detection:create", GrantScope.OWN),
		("detection:read", GrantScope.PROJECT),
		("detection:export", GrantScope.PROJECT),
		("report:read", GrantScope.PROJECT),
	],
	"fraud_analyst": [
		("project:read", GrantScope.PROJECT),
		("dataset:read", GrantScope.PROJECT),
		("rule:read", GrantScope.PROJECT),
		("detection:create", GrantScope.OWN),
		("detection:read", GrantScope.PROJECT),
		("detection:export", GrantScope.PROJECT),
		("case:create", GrantScope.PROJECT),
		("case:read", GrantScope.PROJECT),
		("case:claim", GrantScope.PROJECT),
		("case:manual_review", GrantScope.PROJECT),
		("case:escalate", GrantScope.PROJECT),
		("case:reopen", GrantScope.PROJECT),
		("blacklist:manage", GrantScope.PROJECT),
		("report:read", GrantScope.PROJECT),
		("report:create", GrantScope.PROJECT),
		("report:export", GrantScope.PROJECT),
		("audit:read", GrantScope.PROJECT),
	],
}


def seed_rbac(
	session: Session,
	bootstrap_username: str = "admin",
	bootstrap_password_hash: str = "",
	bootstrap_email: str = "admin@usfds.local",
	bootstrap_full_name: str = "System Administrator",
) -> User:
	"""Idempotently seed permissions, built-in roles, bootstrap admin, and backfill project_members."""
	perm_repo = SqlPermissionRepository(session)
	role_repo = SqlRoleRepository(session)
	user_repo = SqlUserRepository(session)
	member_repo = SqlProjectMemberRepository(session)

	# Remove obsolete permissions (e.g. rule:propose removed in ISS-037) idempotently
	obsolete_perm = perm_repo.get_by_code("rule:propose")
	if obsolete_perm is not None:
		session.execute(
			delete(RolePermissionModel).where(RolePermissionModel.permission_id == str(obsolete_perm.permission_id))
		)
		session.execute(
			delete(PermissionModel).where(PermissionModel.permission_id == str(obsolete_perm.permission_id))
		)
		session.flush()

	perm_by_code: Dict[str, Permission] = {}
	for code, resource, action, scope, desc in PERMISSION_CATALOG:
		existing = perm_repo.get_by_code(code)
		if existing is None:
			existing = perm_repo.save(
				Permission(code=code, resource=resource, action=action, scope=scope, description=desc)
			)
		perm_by_code[code] = existing

	role_by_name: Dict[str, Role] = {}
	for name, display_name, scope, desc in BUILTIN_ROLES:
		existing = role_repo.get_by_scope_and_name(scope, name)
		if existing is None:
			existing = role_repo.save(
				Role(name=name, display_name=display_name, scope=scope, is_system=True, description=desc)
			)
		role_by_name[name] = existing

	for role_name, grants in ROLE_GRANTS.items():
		role = role_by_name[role_name]
		existing_rp = {
			rp.permission_id: str(rp.grant_scope.value if hasattr(rp.grant_scope, "value") else rp.grant_scope)
			for rp in role_repo.get_role_permissions(role.role_id)
		}
		for code, grant_scope in grants:
			perm = perm_by_code[code]
			if existing_rp.get(perm.permission_id) != grant_scope.value:
				session.merge(
					RolePermissionModel(
						role_id=str(role.role_id),
						permission_id=str(perm.permission_id),
						grant_scope=grant_scope.value,
					)
				)
	session.flush()

	admin_user = user_repo.get_by_username(bootstrap_username)
	if admin_user is None:
		admin_user = user_repo.save(
			User(
				username=bootstrap_username,
				email=bootstrap_email,
				full_name=bootstrap_full_name,
				password_hash=bootstrap_password_hash,
				status=UserStatus.ACTIVE,
			)
		)
	elif bootstrap_password_hash and not admin_user.password_hash:
		admin_user.password_hash = bootstrap_password_hash
		admin_user = user_repo.save(admin_user)

	sys_admin_role = role_by_name["system_admin"]
	existing_sys_roles = role_repo.get_system_user_role_ids(admin_user.user_id)
	if sys_admin_role.role_id not in existing_sys_roles:
		session.add(
			SystemUserRoleModel(
				user_id=str(admin_user.user_id),
				role_id=str(sys_admin_role.role_id),
				assigned_by=str(admin_user.user_id),
			)
		)
		session.flush()

	# Backfill legacy projects that have no project_admin member yet
	proj_admin_role = role_by_name["project_admin"]
	projects = session.execute(select(ProjectModel).order_by(ProjectModel.created_at.asc())).scalars().all()
	for proj in projects:
		pid = UUID(proj.project_id)
		if member_repo.count_role_members_in_project(pid, "project_admin") == 0:
			owner = user_repo.get_by_id(UUID(proj.user_id))
			target_uid = owner.user_id if owner is not None else admin_user.user_id
			member_repo.add_member(pid, target_uid, proj_admin_role.role_id, added_by=admin_user.user_id)

	session.flush()
	return admin_user
