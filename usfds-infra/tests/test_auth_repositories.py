"""M1 acceptance tests for Auth/RBAC ORM tables, repositories, and idempotent seeding."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from usfds_core.domain.entities.enums import GrantScope, RoleScope, UserStatus
from usfds_core.domain.entities.system import Project, User
from usfds_infra.database.repos.auth import (
	SqlPermissionRepository,
	SqlProjectMemberRepository,
	SqlRoleRepository,
	SqlUserRepository,
)
from usfds_infra.database.repos.project import SqliteProjectRepository
from usfds_infra.database.seed_rbac import seed_rbac


def test_schema_supports_multi_role_per_project_and_idempotent_seed(db_session):
	"""ISS-006: seed_rbac is idempotent, backfills legacy projects, and project_members supports multiple roles per user."""
	project_repo = SqliteProjectRepository(db_session)
	user_repo = SqlUserRepository(db_session)
	role_repo = SqlRoleRepository(db_session)
	member_repo = SqlProjectMemberRepository(db_session)

	legacy_owner_id = uuid4()
	user_repo.save(
		User(
			user_id=legacy_owner_id,
			username="legacy_owner",
			email="legacy_owner@usfds.local",
			full_name="Legacy Owner",
			password_hash="hashed",
			status=UserStatus.ACTIVE,
		)
	)
	legacy_project = Project(
		project_id=uuid4(),
		project_name="Legacy Fraud Project",
		user_id=legacy_owner_id,
	)
	project_repo.save(legacy_project)
	db_session.flush()

	# Run seed twice to verify idempotency
	seed_rbac(db_session, bootstrap_password_hash="hashed-pw")
	db_session.flush()
	seed_rbac(db_session, bootstrap_password_hash="hashed-pw")
	db_session.flush()

	roles = role_repo.list_all()
	role_names = {r.name for r in roles}
	assert {"system_admin", "system_member", "project_admin", "data_scientist", "fraud_analyst"}.issubset(role_names)

	# Legacy project should have been backfilled with a project_admin member
	members = member_repo.list_members(legacy_project.project_id)
	assert len(members) >= 1
	project_admin_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "project_admin")
	assert project_admin_role is not None
	assert any(m.role_id == project_admin_role.role_id for m in members)

	# Create a new user and assign TWO roles in the same project
	analyst_user = User(
		username="dual_role_user",
		email="dual@usfds.local",
		full_name="Dual Role User",
		password_hash="hashed",
		status=UserStatus.ACTIVE,
	)
	user_repo.save(analyst_user)
	db_session.flush()

	ds_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "data_scientist")
	fa_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "fraud_analyst")
	assert ds_role is not None and fa_role is not None

	member_repo.add_member(legacy_project.project_id, analyst_user.user_id, ds_role.role_id)
	member_repo.add_member(legacy_project.project_id, analyst_user.user_id, fa_role.role_id)
	db_session.flush()

	user_roles = member_repo.list_user_roles_in_project(legacy_project.project_id, analyst_user.user_id)
	assert len(user_roles) == 2

	actor = user_repo.load_actor_context(analyst_user.user_id)
	assert actor is not None
	assert actor.is_system_admin is False
	proj_ctx = next((p for p in actor.projects if p.project_id == legacy_project.project_id), None)
	assert proj_ctx is not None
	assert set(proj_ctx.role_keys) == {"data_scientist", "fraud_analyst"}
	# Permissions from both roles are merged
	assert "model:create" in proj_ctx.permissions
	assert "case:claim" in proj_ctx.permissions


def test_load_actor_context_and_load_project_actor_context(db_session):
	"""Verify system-wide load_actor_context (UserRepo) and project-scoped load_project_actor_context (MemberRepo)."""
	seed_rbac(db_session, bootstrap_password_hash="hashed-pw")

	user_repo = SqlUserRepository(db_session)
	role_repo = SqlRoleRepository(db_session)
	member_repo = SqlProjectMemberRepository(db_session)
	project_repo = SqliteProjectRepository(db_session)

	# Unknown user -> None
	assert user_repo.load_actor_context(uuid4()) is None

	# Create two users and two projects
	alice = User(
		user_id=uuid4(),
		username="alice",
		email="alice@usfds.local",
		full_name="Alice Nguyen",
		password_hash="h",
		status=UserStatus.ACTIVE,
	)
	bob = User(
		user_id=uuid4(),
		username="bob",
		email="bob@usfds.local",
		full_name="Bob Tran",
		password_hash="h",
		status=UserStatus.DISABLED,
	)
	user_repo.save(alice)
	user_repo.save(bob)

	p1 = Project(project_id=uuid4(), project_name="Project 1", user_id=alice.user_id)
	p2 = Project(project_id=uuid4(), project_name="Project 2", user_id=bob.user_id)
	project_repo.save(p1)
	project_repo.save(p2)

	sys_member = role_repo.get_by_scope_and_name(RoleScope.SYSTEM, "system_member")
	role_repo.set_system_user_roles(alice.user_id, [sys_member.role_id])

	ds_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "data_scientist")
	fa_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "fraud_analyst")
	pa_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "project_admin")

	# Alice has 2 roles in p1 and 1 role in p2; Bob has 1 role in p2 only
	member_repo.add_member(p1.project_id, alice.user_id, ds_role.role_id)
	member_repo.add_member(p1.project_id, alice.user_id, fa_role.role_id)
	member_repo.add_member(p2.project_id, alice.user_id, pa_role.role_id)
	member_repo.add_member(p2.project_id, bob.user_id, fa_role.role_id)
	db_session.flush()

	# 1. System-level ActorContext for Alice covers both p1 & p2 and system_member
	alice_actor = user_repo.load_actor_context(alice.user_id)
	assert alice_actor is not None
	assert alice_actor.is_system_admin is False
	assert alice_actor.system_role_keys == ["system_member"]
	assert "project:create" in alice_actor.system_permissions
	assert len(alice_actor.projects) == 2
	p1_perms = next(p for p in alice_actor.projects if p.project_id == p1.project_id)
	assert set(p1_perms.role_keys) == {"data_scientist", "fraud_analyst"}
	# Deduplicated scopes even when both roles grant the same permission (e.g., dataset:read)
	assert len(p1_perms.permissions["dataset:read"]) == len(set(p1_perms.permissions["dataset:read"]))

	# 2. Project-level ProjectActorContext for p1 returns only Alice (1 grouped entry with 2 roles)
	p1_members = member_repo.load_project_actor_context(p1.project_id)
	assert len(p1_members) == 1
	m_alice = p1_members[0]
	assert m_alice.user_id == alice.user_id
	assert m_alice.project_id == p1.project_id
	assert m_alice.full_name == "Alice Nguyen"
	assert {r.name for r in m_alice.roles} == {"data_scientist", "fraud_analyst"}
	assert set(m_alice.role_keys) == {"data_scientist", "fraud_analyst"}
	assert "model:create" in m_alice.permissions
	assert "case:claim" in m_alice.permissions
	# System-only permissions never leak into project-level context
	assert "project:create" not in m_alice.permissions

	# 3. Project-level lookup filtered by user_id
	assert len(member_repo.load_project_actor_context(p1.project_id, user_id=bob.user_id)) == 0
	p2_bob = member_repo.load_project_actor_context(p2.project_id, user_id=bob.user_id)
	assert len(p2_bob) == 1
	assert p2_bob[0].status == UserStatus.DISABLED
	assert p2_bob[0].role_keys == ["fraud_analyst"]


def test_seed_rbac_syncs_builtin_role_own_scopes_idempotently(db_session):
	"""ISS-043: seed_rbac updates built-in role grants to OWN for ds/fa mutations and adds cleanup PROJECT grants to project_admin."""
	from usfds_infra.database.models import RolePermissionModel

	seed_rbac(db_session, bootstrap_password_hash="hashed-pw")
	role_repo = SqlRoleRepository(db_session)
	perm_repo = SqlPermissionRepository(db_session)
	perm_by_id = {p.permission_id: p.code for p in perm_repo.list_all()}
	perm_by_code = {p.code: p.permission_id for p in perm_repo.list_all()}

	ds_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "data_scientist")
	fa_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "fraud_analyst")
	pa_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "project_admin")
	assert ds_role is not None and fa_role is not None and pa_role is not None

	# Simulate legacy DB state where data_scientist had PROJECT scope on rule:update and dataset:delete
	for code in ("rule:update", "dataset:delete"):
		db_session.merge(
			RolePermissionModel(
				role_id=str(ds_role.role_id),
				permission_id=str(perm_by_code[code]),
				grant_scope=GrantScope.PROJECT.value,
			)
		)
	db_session.flush()

	# Re-run seed_rbac twice
	seed_rbac(db_session, bootstrap_password_hash="hashed-pw")
	seed_rbac(db_session, bootstrap_password_hash="hashed-pw")
	db_session.flush()

	ds_grants = {perm_by_id[rp.permission_id]: rp.grant_scope for rp in role_repo.get_role_permissions(ds_role.role_id)}
	for own_code in (
		"dataset:create", "dataset:update", "dataset:delete",
		"model:create", "model:update", "training:create",
		"deployment:deploy", "deployment:undeploy",
		"rule:create", "rule:update", "rule:delete", "rule:deploy", "rule:undeploy",
		"detection:create",
	):
		assert ds_grants.get(own_code) == GrantScope.OWN, f"Expected OWN for {own_code}, got {ds_grants.get(own_code)}"
	for proj_code in (
		"project:read", "dataset:read", "dataset:export",
		"model:read", "training:read", "rule:read", "rule:dry_run",
		"detection:read", "detection:export", "report:read",
	):
		assert ds_grants.get(proj_code) == GrantScope.PROJECT, f"Expected PROJECT for {proj_code}, got {ds_grants.get(proj_code)}"

	fa_grants = {perm_by_id[rp.permission_id]: rp.grant_scope for rp in role_repo.get_role_permissions(fa_role.role_id)}
	assert fa_grants.get("detection:create") == GrantScope.OWN

	pa_grants = {perm_by_id[rp.permission_id]: rp.grant_scope for rp in role_repo.get_role_permissions(pa_role.role_id)}
	for pa_code in ("dataset:delete", "rule:deploy", "rule:undeploy", "rule:delete"):
		assert pa_grants.get(pa_code) == GrantScope.PROJECT, f"Expected PROJECT for project_admin {pa_code}"


def test_user_repo_get_by_ids_returns_map_without_duplicates(db_session):
	"""M1: SqlUserRepository.get_by_ids batch-loads users by IDs and ignores missing/duplicate IDs."""
	user_repo = SqlUserRepository(db_session)
	u1 = user_repo.save(
		User(
			user_id=uuid4(),
			username="batch_u1",
			email="batch_u1@usfds.local",
			full_name="Batch User 1",
			password_hash="hashed",
			status=UserStatus.ACTIVE,
		)
	)
	u2 = user_repo.save(
		User(
			user_id=uuid4(),
			username="batch_u2",
			email="batch_u2@usfds.local",
			full_name="Batch User 2",
			password_hash="hashed",
			status=UserStatus.ACTIVE,
		)
	)
	user_repo.save(
		User(
			user_id=uuid4(),
			username="batch_u3",
			email="batch_u3@usfds.local",
			full_name="Batch User 3",
			password_hash="hashed",
			status=UserStatus.ACTIVE,
		)
	)

	result = user_repo.get_by_ids([u1.user_id, u1.user_id, u2.user_id, uuid4()])
	assert set(result.keys()) == {u1.user_id, u2.user_id}
	assert result[u1.user_id].username == "batch_u1"
	assert result[u1.user_id].full_name == "Batch User 1"
	assert result[u2.user_id].username == "batch_u2"
	assert user_repo.get_by_ids([]) == {}
