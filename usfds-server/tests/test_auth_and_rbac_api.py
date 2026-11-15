"""M2-M4 acceptance tests for Authentication & 3-Scope RBAC API."""
from uuid import uuid4

from usfds_core.domain.entities.enums import UserStatus
from usfds_core.domain.entities.system import User
from usfds_infra.database.repos.auth import SqlUserRepository
from usfds_infra.security import PasswordHasher


def test_required_mode_auth_lifecycle(server_settings, monkeypatch):
	"""ISS-006: In required mode, login -> me -> refresh -> logout lifecycle works and disabled users are blocked."""
	from fastapi.testclient import TestClient
	from usfds_server import dependencies
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		# Mode endpoint is public
		mode_res = test_client.get("/api/v1/auth/mode")
		assert mode_res.status_code == 200
		assert mode_res.json()["data"]["auth_mode"] == "required"

		# /auth/me without token -> 401
		assert test_client.get("/api/v1/auth/me").status_code == 401

		# Login with valid credentials
		login_res = test_client.post(
			"/api/v1/auth/login",
			json={"username": "admin", "password": "AdminPass123!"},
		)
		assert login_res.status_code == 200
		tokens = login_res.json()["data"]
		access_token = tokens["access_token"]
		refresh_token = tokens["refresh_token"]
		assert access_token and refresh_token

		# /auth/me with Bearer token
		me_res = test_client.get(
			"/api/v1/auth/me",
			headers={"Authorization": f"Bearer {access_token}"},
		)
		assert me_res.status_code == 200
		assert me_res.json()["data"]["username"] == "admin"
		assert me_res.json()["data"]["is_system_admin"] is True

		# Refresh token rotation
		refresh_res = test_client.post(
			"/api/v1/auth/refresh",
			json={"refresh_token": refresh_token},
		)
		assert refresh_res.status_code == 200
		new_refresh = refresh_res.json()["data"]["refresh_token"]
		assert new_refresh != refresh_token

		# Old refresh token is now invalid
		assert test_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).status_code == 401

		# Logout revokes the new refresh token
		logout_res = test_client.post(
			"/api/v1/auth/logout",
			json={"refresh_token": new_refresh},
			headers={"Authorization": f"Bearer {access_token}"},
		)
		assert logout_res.status_code == 200
		assert test_client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh}).status_code == 401

		# Disabled user cannot log in
		hasher = PasswordHasher()
		with dependencies._session_factory() as session:
			user_repo = SqlUserRepository(session)
			user_repo.save(
				User(
					user_id=uuid4(),
					username="locked_user",
					email="locked@usfds.local",
					password_hash=hasher.hash("Secret123!"),
					status=UserStatus.DISABLED,
				)
			)
			session.commit()

		disabled_login = test_client.post(
			"/api/v1/auth/login",
			json={"username": "locked_user", "password": "Secret123!"},
		)
		assert disabled_login.status_code == 401


def test_local_auto_mode_bootstraps_admin(client):
	"""ISS-006: In local_auto mode, /auth/mode returns local_auto and /auth/me returns bootstrap admin without Bearer."""
	mode_res = client.get("/api/v1/auth/mode")
	assert mode_res.status_code == 200
	assert mode_res.json()["data"]["auth_mode"] == "local_auto"

	me_res = client.get("/api/v1/auth/me")
	assert me_res.status_code == 200
	data = me_res.json()["data"]
	assert data["username"] == "admin"
	assert data["is_system_admin"] is True


def test_router_rbac_isolation_and_storage_guard(server_settings, monkeypatch):
	"""ISS-006: In required mode, users are isolated to their member projects and storage presigned URLs are guarded."""
	from fastapi.testclient import TestClient
	from usfds_core.domain.entities.enums import RoleScope
	from usfds_core.domain.entities.system import Project
	from usfds_infra.database.repos.auth import SqlProjectMemberRepository, SqlRoleRepository, SqlUserRepository
	from usfds_infra.database.repos.project import SqliteProjectRepository
	from usfds_server import dependencies
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		hasher = PasswordHasher()
		p1_id = uuid4()
		p2_id = uuid4()
		p3_id = uuid4()
		u1_id = uuid4()
		with dependencies._session_factory() as session:
			user_repo = SqlUserRepository(session)
			role_repo = SqlRoleRepository(session)
			proj_repo = SqliteProjectRepository(session)
			member_repo = SqlProjectMemberRepository(session)

			user_repo.save(
				User(
					user_id=u1_id,
					username="alice",
					email="alice@usfds.local",
					password_hash=hasher.hash("AlicePass123!"),
					status=UserStatus.ACTIVE,
				)
			)
			sys_member = role_repo.get_by_scope_and_name(RoleScope.SYSTEM, "system_member")
			role_repo.set_system_user_roles(u1_id, [sys_member.role_id])

			proj_repo.save(Project(project_id=p1_id, project_name="Project 1", user_id=u1_id))
			proj_repo.save(Project(project_id=p2_id, project_name="Project 2", user_id=uuid4()))
			proj_repo.save(Project(project_id=p3_id, project_name="Project 3", user_id=uuid4()))

			ds_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "data_scientist")
			member_repo.add_member(p1_id, u1_id, ds_role.role_id)

			from usfds_core.domain.entities.auth import Role
			no_read_role = role_repo.save(
				Role(
					role_id=uuid4(),
					name="no_project_read",
					display_name="No Project Read",
					scope=RoleScope.PROJECT,
				)
			)
			member_repo.add_member(p3_id, u1_id, no_read_role.role_id)
			session.commit()

		login_res = test_client.post("/api/v1/auth/login", json={"username": "alice", "password": "AlicePass123!"})
		assert login_res.status_code == 200
		token = login_res.json()["data"]["access_token"]
		headers = {"Authorization": f"Bearer {token}"}

		# Alice sees only Project 1 in list_projects (p2 not member, p3 lacks project:read)
		list_res = test_client.get("/api/v1/projects", headers=headers)
		assert list_res.status_code == 200
		pids = [p["project_id"] for p in list_res.json()["data"]]
		assert str(p1_id) in pids
		assert str(p2_id) not in pids
		assert str(p3_id) not in pids

		# Alice can read Project 1, but gets 403 on Project 2
		assert test_client.get(f"/api/v1/projects/{p1_id}", headers=headers).status_code == 200
		assert test_client.get(f"/api/v1/projects/{p2_id}", headers=headers).status_code == 403

		# Storage presigned-download for Project 2 object_key returns 403
		dl_res = test_client.get(
			"/api/v1/storage/presigned-download",
			params={"object_key": f"uploads/dataset_raw/{p2_id}/file.csv"},
			headers=headers,
		)
		assert dl_res.status_code == 403


def test_admin_user_and_rbac_endpoints(server_settings, monkeypatch):
	"""M4: system_admin can manage users, roles, and project members; fraud_analyst gets 403."""
	from fastapi.testclient import TestClient
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_login = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
		assert admin_login.status_code == 200
		admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['access_token']}"}

		# Create a project as system_admin
		proj_res = test_client.post("/api/v1/projects", json={"project_name": "Admin Project"}, headers=admin_headers)
		assert proj_res.status_code in (200, 201)
		project_id = proj_res.json()["data"]["project_id"]

		# Create a fraud_analyst user via /api/v1/users
		create_user_res = test_client.post(
			"/api/v1/users",
			json={
				"username": "analyst1",
				"email": "analyst1@usfds.local",
				"full_name": "Analyst One",
				"password": "AnalystPass123!",
				"system_roles": ["system_member"],
			},
			headers=admin_headers,
		)
		assert create_user_res.status_code in (200, 201)
		analyst_id = create_user_res.json()["data"]["user_id"]

		# List users as system_admin -> 200
		assert test_client.get("/api/v1/users", headers=admin_headers).status_code == 200

		# List roles & permissions as system_admin -> 200
		roles_res = test_client.get("/api/v1/rbac/roles", headers=admin_headers)
		assert roles_res.status_code == 200
		roles = roles_res.json()["data"]
		analyst_role = next(r for r in roles if r["name"] == "fraud_analyst")

		# Create custom role & set permissions as system_admin
		custom_role_res = test_client.post(
			"/api/v1/rbac/roles",
			json={"name": "custom_reviewer", "display_name": "Custom Reviewer", "scope": "PROJECT", "description": "Test"},
			headers=admin_headers,
		)
		assert custom_role_res.status_code in (200, 201)
		custom_role_id = custom_role_res.json()["data"]["role_id"]

		set_perm_res = test_client.put(
			f"/api/v1/rbac/roles/{custom_role_id}/permissions",
			json={"grants": [{"permission_code": "case:read", "grant_scope": "PROJECT"}]},
			headers=admin_headers,
		)
		assert set_perm_res.status_code == 200

		# Create a project-scoped user directly via POST /members -> 201 and visible in /api/v1/users
		create_member_user_res = test_client.post(
			f"/api/v1/projects/{project_id}/members",
			json={
				"username": "proj_user1",
				"password": "ProjUser123!",
				"full_name": "Project User 1",
				"email": "proj_user1@usfds.local",
				"role_id": analyst_role["role_id"],
			},
			headers=admin_headers,
		)
		assert create_member_user_res.status_code == 201
		proj_user_id = create_member_user_res.json()["data"]["user_id"]
		assert create_member_user_res.json()["data"]["username"] == "proj_user1"
		users_list = test_client.get("/api/v1/users", headers=admin_headers).json()["data"]
		assert any(u["username"] == "proj_user1" for u in users_list)

		# Assign additional role via POST /members/{user_id}/roles & verify GET /members returns 1 grouped actor context
		ds_role = next(r for r in roles if r["name"] == "data_scientist")
		assign_res = test_client.post(
			f"/api/v1/projects/{project_id}/members/{proj_user_id}/roles",
			json={"role_id": ds_role["role_id"]},
			headers=admin_headers,
		)
		assert assign_res.status_code == 201
		assert set(assign_res.json()["data"]["role_keys"]) == {"fraud_analyst", "data_scientist"}

		members_res = test_client.get(f"/api/v1/projects/{project_id}/members", headers=admin_headers)
		assert members_res.status_code == 200
		proj_user_rows = [m for m in members_res.json()["data"] if m["user_id"] == proj_user_id]
		assert len(proj_user_rows) == 1
		assert len(proj_user_rows[0]["roles"]) == 2
		assert "model:create" in proj_user_rows[0]["permissions"]
		assert "case:claim" in proj_user_rows[0]["permissions"]

		assert test_client.put(
			f"/api/v1/projects/{project_id}/members/{proj_user_id}/roles",
			json={"role_ids": [analyst_role["role_id"]]},
			headers=admin_headers,
		).status_code == 200
		assert test_client.delete(
			f"/api/v1/projects/{project_id}/members/{proj_user_id}",
			headers=admin_headers,
		).status_code == 200

		# Verify /api/v1/auth/me returns current actor context
		me_res = test_client.get("/api/v1/auth/me", headers=admin_headers)
		assert me_res.status_code == 200
		assert me_res.json()["data"]["is_system_admin"] is True

		# Add analyst1 as fraud_analyst on project
		add_member_res = test_client.post(
			f"/api/v1/projects/{project_id}/members",
			json={"user_id": analyst_id, "role_id": analyst_role["role_id"]},
			headers=admin_headers,
		)
		assert add_member_res.status_code in (200, 201)

		# Login as analyst1
		analyst_login = test_client.post("/api/v1/auth/login", json={"username": "analyst1", "password": "AnalystPass123!"})
		assert analyst_login.status_code == 200
		analyst_headers = {"Authorization": f"Bearer {analyst_login.json()['data']['access_token']}"}

		# fraud_analyst gets 403 on admin endpoints & member management
		assert test_client.get("/api/v1/users", headers=analyst_headers).status_code == 403
		assert test_client.post(
			f"/api/v1/projects/{project_id}/members",
			json={"username": "x", "password": "Password123!", "role_id": analyst_role["role_id"]},
			headers=analyst_headers,
		).status_code == 403
		assert test_client.post(
			f"/api/v1/projects/{project_id}/members/{analyst_id}/roles",
			json={"role_id": ds_role["role_id"]},
			headers=analyst_headers,
		).status_code == 403
		assert test_client.put(
			f"/api/v1/rbac/roles/{custom_role_id}/permissions",
			json={"grants": [{"permission_code": "case:read", "grant_scope": "PROJECT"}]},
			headers=analyst_headers,
		).status_code == 403
		assert test_client.post(
			f"/api/v1/projects/{project_id}/members",
			json={"user_id": analyst_id, "role_id": custom_role_id},
			headers=analyst_headers,
		).status_code == 403
