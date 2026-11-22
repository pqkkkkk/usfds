"""M3 acceptance tests for ActorContext and can_list / can_read / can_create / can_mutate."""
from uuid import uuid4

import pytest

from usfds_core.domain.entities.auth import (
	AccessTarget,
	ActorContext,
	PermissionDeniedError,
	ProjectPermissions,
)
from usfds_core.domain.entities.enums import GrantScope
from usfds_core.services.auth.access_logic import (
	can_create,
	can_list,
	can_mutate,
	can_read,
	sanitize_actor_context,
)


def test_actor_context_and_four_access_checks():
	"""ISS-006: ActorContext + can_list / can_read / can_create / can_mutate enforce 3-scope RBAC."""
	user_id = uuid4()
	other_user_id = uuid4()
	proj_a = uuid4()
	proj_b = uuid4()

	raw_actor = ActorContext(
		user_id=user_id,
		username="analyst",
		projects=[
			ProjectPermissions(
				project_id=proj_a,
				role_keys=["fraud_analyst"],
				permissions={
					"rule:read": [GrantScope.PROJECT],
					"rule:update": [GrantScope.OWN],
					"case:read": [GrantScope.PROJECT],
					# Even if DB had a SYSTEM grant on a project branch, sanitize drops it
					"user:read": [GrantScope.SYSTEM],
				},
			)
		],
		system_role_keys=["system_member"],
		system_permissions={
			"project:create": [GrantScope.SYSTEM],
			# Even if DB had a PROJECT grant on system branch, sanitize drops it
			"rule:delete": [GrantScope.PROJECT],
		},
		is_system_admin=False,
	)

	actor = sanitize_actor_context(raw_actor)
	assert "user:read" not in actor.projects[0].permissions
	assert "rule:delete" not in actor.system_permissions

	# can_read: PROJECT scope allows any owner in Project A, denies Project B
	assert can_read(actor, "rule:read", AccessTarget(project_id=proj_a, owner_id=other_user_id)) is True
	assert can_read(actor, "rule:read", AccessTarget(project_id=proj_b, owner_id=user_id)) is False

	# can_mutate: OWN scope allows only own resource in Project A
	assert can_mutate(actor, "rule:update", AccessTarget(project_id=proj_a, owner_id=user_id)) is True
	assert can_mutate(actor, "rule:update", AccessTarget(project_id=proj_a, owner_id=other_user_id)) is False
	assert can_mutate(actor, "rule:update", AccessTarget(project_id=proj_b, owner_id=user_id)) is False

	# can_create: OWN scope allows creating for self, denies creating for another owner
	assert can_create(actor, "rule:update", AccessTarget(project_id=proj_a, owner_id=user_id), has_membership=True) is True
	assert can_create(actor, "rule:update", AccessTarget(project_id=proj_a, owner_id=other_user_id), has_membership=True) is False

	# can_list: returns scoped filters; requesting forbidden Project B raises PermissionDeniedError
	filters = can_list(actor, "rule:update", active_project_ids=[proj_a, proj_b])
	assert len(filters) == 1
	assert filters[0].project_ids == [proj_a]
	assert filters[0].owner_id == user_id

	with pytest.raises(PermissionDeniedError):
		can_list(actor, "rule:update", active_project_ids=[proj_a, proj_b], requested_project_ids=[proj_b])


def test_authz_project_scope_and_list_owner_helpers():
	"""ISS-043: require_project_scope and resolve_project_list_owner resolve OWN, PROJECT, and deny missing scope."""
	from usfds_core.services.auth.authz_service import AuthzService

	user_id = uuid4()
	proj_a = uuid4()
	proj_b = uuid4()
	proj_c = uuid4()

	actor = sanitize_actor_context(
		ActorContext(
			user_id=user_id,
			username="analyst",
			projects=[
				ProjectPermissions(
					project_id=proj_a,
					role_keys=["custom_own"],
					permissions={"rule:read": [GrantScope.OWN]},
				),
				ProjectPermissions(
					project_id=proj_b,
					role_keys=["data_scientist"],
					permissions={"rule:read": [GrantScope.PROJECT]},
				),
			],
			system_role_keys=["system_member"],
			system_permissions={},
			is_system_admin=False,
		)
	)
	authz = AuthzService(user_repo=None, role_repo=None, permission_repo=None, member_repo=None)  # type: ignore[arg-type]

	assert authz.require_project_scope(actor, "rule:read", proj_a) == GrantScope.OWN
	assert authz.resolve_project_list_owner(actor, "rule:read", proj_a) == user_id

	assert authz.require_project_scope(actor, "rule:read", proj_b) == GrantScope.PROJECT
	assert authz.resolve_project_list_owner(actor, "rule:read", proj_b) is None

	with pytest.raises(PermissionDeniedError):
		authz.require_project_scope(actor, "rule:read", proj_c)
	with pytest.raises(PermissionDeniedError):
		authz.resolve_project_list_owner(actor, "rule:read", proj_c)
