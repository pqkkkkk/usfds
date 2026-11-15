"""M4 acceptance tests for Authz Management (anti-escalation & last project_admin guard)."""
from uuid import uuid4

import pytest

from usfds_core.domain.entities.auth import ActorContext, PermissionDeniedError, ProjectPermissions
from usfds_core.domain.entities.enums import GrantScope, RoleScope
from usfds_core.services.auth.access_logic import (
	assert_grant_scopes,
	assert_scope_change_allowed,
	delegation_refusal,
	super_admin_refusal,
)


def test_delegation_and_system_only_refusal():
	"""ISS-006: project_admin cannot assign system_admin or roles with permissions exceeding their own."""
	proj_a = uuid4()
	proj_b = uuid4()
	admin_id = uuid4()

	actor = ActorContext(
		user_id=admin_id,
		username="proj_admin",
		projects=[
			ProjectPermissions(
				project_id=proj_a,
				role_keys=["project_admin"],
				permissions={
					"project:read": [GrantScope.PROJECT],
					"project_member:manage": [GrantScope.PROJECT],
					"case:read": [GrantScope.PROJECT],
				},
			)
		],
		system_role_keys=["system_member"],
		system_permissions={"project:create": [GrantScope.SYSTEM]},
		is_system_admin=False,
	)

	# 1. Cannot assign system_admin
	refusal = delegation_refusal(
		actor=actor,
		caller_project_ids=[proj_a],
		project_id=proj_a,
		role_name="system_admin",
		role_scope=RoleScope.SYSTEM,
		grants=[],
	)
	assert refusal is not None

	# 2. Cannot assign a role in Project B (not a member/admin there)
	refusal_b = delegation_refusal(
		actor=actor,
		caller_project_ids=[proj_a],
		project_id=proj_b,
		role_name="fraud_analyst",
		role_scope=RoleScope.PROJECT,
		grants=[("case:read", GrantScope.PROJECT)],
	)
	assert refusal_b is not None

	# 3. Cannot assign a role granting a permission the caller doesn't hold (model:create)
	refusal_escalate = delegation_refusal(
		actor=actor,
		caller_project_ids=[proj_a],
		project_id=proj_a,
		role_name="data_scientist",
		role_scope=RoleScope.PROJECT,
		grants=[("model:create", GrantScope.PROJECT)],
	)
	assert refusal_escalate is not None

	# 4. Can assign a role whose grants are covered by caller's permissions
	ok = delegation_refusal(
		actor=actor,
		caller_project_ids=[proj_a],
		project_id=proj_a,
		role_name="case_viewer",
		role_scope=RoleScope.PROJECT,
		grants=[("case:read", GrantScope.PROJECT)],
	)
	assert ok is None

	# 5. PROJECT role cannot grant SYSTEM-only permission or SYSTEM scope
	with pytest.raises(PermissionDeniedError):
		assert_grant_scopes(RoleScope.PROJECT, [("user:create", GrantScope.PROJECT)])
	with pytest.raises(PermissionDeniedError):
		assert_grant_scopes(RoleScope.PROJECT, [("case:read", GrantScope.SYSTEM)])

	# 6. Non-system_admin cannot manage protected system_admin role
	assert super_admin_refusal(False, "system_admin", []) is not None
	assert super_admin_refusal(True, "system_admin", []) is None

	# 7. Cannot change role scope while assigned
	with pytest.raises(ValueError):
		assert_scope_change_allowed(RoleScope.PROJECT, RoleScope.SYSTEM, {"system": 0, "project": 1})


def test_cannot_remove_last_project_admin():
	"""ISS-006: Removing or downgrading the last project_admin in a project is rejected."""
	from unittest.mock import MagicMock
	from usfds_core.domain.entities.auth import Role
	from usfds_core.services.auth.authz_service import AuthzService

	proj_a = uuid4()
	user_id = uuid4()
	admin_role_id = uuid4()
	viewer_role_id = uuid4()

	user_repo = MagicMock()
	role_repo = MagicMock()
	perm_repo = MagicMock()
	member_repo = MagicMock()

	admin_role = Role(role_id=admin_role_id, name="project_admin", display_name="Project Admin", scope=RoleScope.PROJECT, is_system=True)
	viewer_role = Role(role_id=viewer_role_id, name="fraud_analyst", display_name="Fraud Analyst", scope=RoleScope.PROJECT, is_system=True)

	role_repo.get_by_id.side_effect = lambda rid: admin_role if rid == admin_role_id else viewer_role
	member_repo.list_user_roles_in_project.return_value = [admin_role]
	member_repo.count_role_members_in_project.return_value = 1

	sys_admin_actor = ActorContext(user_id=uuid4(), username="admin", is_system_admin=True)
	svc = AuthzService(user_repo, role_repo, perm_repo, member_repo)

	with pytest.raises(ValueError, match="last project_admin"):
		svc.remove_project_member(sys_admin_actor, proj_a, user_id, admin_role_id)

	with pytest.raises(ValueError, match="last project_admin"):
		svc.update_project_member_role(sys_admin_actor, proj_a, user_id, admin_role_id, viewer_role_id)
