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

			admin_user = user_repo.get_by_username("admin")
			proj_repo.save(Project(project_id=p1_id, project_name="Project 1", user_id=u1_id))
			proj_repo.save(Project(project_id=p2_id, project_name="Project 2", user_id=admin_user.user_id))
			proj_repo.save(Project(project_id=p3_id, project_name="Project 3", user_id=admin_user.user_id))

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
		pids = [p["project_id"] for p in list_res.json()["data"]["items"]]
		assert str(p1_id) in pids
		assert str(p2_id) not in pids
		assert str(p3_id) not in pids

		# Alice can read Project 1, but gets 403 on Project 2
		assert test_client.get(f"/api/v1/projects/{p1_id}", headers=headers).status_code == 200
		assert test_client.get(f"/api/v1/projects/{p2_id}", headers=headers).status_code == 403

		# Storage presigned-download for Project 2 object_key returns 403
		dl_res = test_client.get(
			"/api/v1/storage/presigned-download",
			params={"object_key": f"uploads/dataset_raw/{p2_id}/file.csv", "project_id": str(p2_id)},
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


def test_all_project_routers_enforce_permissions_without_rule_propose(server_settings, monkeypatch):
	"""ISS-037: Permission catalog removes rule:propose, adds detection:export & case:create, fixes user/member perms, and all project routers enforce 403."""
	from fastapi.testclient import TestClient
	from usfds_core.domain.entities.dataset import Dataset
	from usfds_core.domain.entities.detection import DetectionJob
	from usfds_core.domain.entities.enums import RuleAction, RuleStatus
	from usfds_infra.database.repos.dataset import SqliteDatasetRepository
	from usfds_infra.database.repos.detection import SqliteDetectionJobRepository
	from usfds_infra.database.repos.rule import SqliteRuleRepository
	from usfds_core.domain.entities.rule import Rule
	from usfds_server import dependencies
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_login = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
		admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['access_token']}"}

		# 1. Permission catalog has detection:export & case:create and does NOT have rule:propose
		perms = test_client.get("/api/v1/rbac/permissions", headers=admin_headers).json()["data"]
		perm_codes = {p["code"] for p in perms}
		assert "rule:propose" not in perm_codes
		assert "detection:export" in perm_codes
		assert "case:create" in perm_codes

		# 2. Setup project + dataset + rule + detection job
		proj_res = test_client.post("/api/v1/projects", json={"project_name": "Hardened Project"}, headers=admin_headers)
		project_id = proj_res.json()["data"]["project_id"]
		from uuid import UUID
		project_uuid = UUID(project_id)

		ds_id = uuid4()
		rule_id = uuid4()
		job_id = uuid4()
		with dependencies._session_factory() as session:
			admin_id = SqlUserRepository(session).get_by_username("admin").user_id
			SqliteDatasetRepository(session).save(
				Dataset(dataset_id=ds_id, project_id=project_uuid, user_id=admin_id, dataset_name="ds_test")
			)
			SqliteRuleRepository(session).save(
				Rule(
					rule_id=rule_id,
					project_id=project_uuid,
					user_id=admin_id,
					rule_code="R-900",
					name="Test Rule",
					description="Test Rule",
					status=RuleStatus.DRAFT,
					created_by="admin",
				)
			)
			SqliteDetectionJobRepository(session).save(
				DetectionJob(
					job_id=job_id,
					project_id=project_uuid,
					user_id=admin_id,
					job_name="job_test",
					input_path="datasets/raw.csv",
				)
			)
			session.commit()

		# 3. Create fraud_analyst, data_scientist, and a non-super-admin user_manager
		roles = test_client.get("/api/v1/rbac/roles", headers=admin_headers).json()["data"]
		fa_role = next(r for r in roles if r["name"] == "fraud_analyst")
		ds_role = next(r for r in roles if r["name"] == "data_scientist")

		# fraud_analyst has rule:read only (PA-A) and detection:export + case:create
		fa_codes = {g["permission_code"] for g in fa_role["grants"]}
		assert "rule:propose" not in fa_codes
		assert "rule:read" in fa_codes
		assert "rule:create" not in fa_codes
		assert "detection:export" in fa_codes
		assert "case:create" in fa_codes

		um_role = test_client.post(
			"/api/v1/rbac/roles",
			json={
				"name": "user_mgr",
				"display_name": "User Manager",
				"scope": "SYSTEM",
				"grants": [
					{"permission_code": "user:read", "grant_scope": "SYSTEM"},
					{"permission_code": "user:update", "grant_scope": "SYSTEM"},
					{"permission_code": "user:reset_password", "grant_scope": "SYSTEM"},
				],
			},
			headers=admin_headers,
		).json()["data"]

		test_client.post(
			"/api/v1/users",
			json={"username": "um1", "password": "UserMgr123!", "system_roles": ["user_mgr"]},
			headers=admin_headers,
		)
		fa_user = test_client.post(
			f"/api/v1/projects/{project_id}/members",
			json={"username": "fa1", "password": "AnalystPass123!", "role_id": fa_role["role_id"]},
			headers=admin_headers,
		).json()["data"]
		test_client.post(
			f"/api/v1/projects/{project_id}/members",
			json={"username": "ds1", "password": "ScientistPass123!", "role_id": ds_role["role_id"]},
			headers=admin_headers,
		)

		fa_token = test_client.post("/api/v1/auth/login", json={"username": "fa1", "password": "AnalystPass123!"}).json()["data"]["access_token"]
		ds_token = test_client.post("/api/v1/auth/login", json={"username": "ds1", "password": "ScientistPass123!"}).json()["data"]["access_token"]
		um_token = test_client.post("/api/v1/auth/login", json={"username": "um1", "password": "UserMgr123!"}).json()["data"]["access_token"]

		fa_headers = {"Authorization": f"Bearer {fa_token}"}
		ds_headers = {"Authorization": f"Bearer {ds_token}"}
		um_headers = {"Authorization": f"Bearer {um_token}"}

		# 4. user_manager uses user:update and user:reset_password (not missing "user:manage")
		assert test_client.patch(
			f"/api/v1/users/{fa_user['user_id']}/status",
			json={"status": "DISABLED"},
			headers=um_headers,
		).status_code == 200
		assert test_client.patch(
			f"/api/v1/users/{fa_user['user_id']}/status",
			json={"status": "ACTIVE"},
			headers=um_headers,
		).status_code == 200
		assert test_client.post(
			f"/api/v1/users/{fa_user['user_id']}/reset-password",
			json={"new_password": "NewPassword123!"},
			headers=um_headers,
		).status_code == 200

		# 5. list_project_members requires project_member:read (fraud_analyst & data_scientist get 403)
		assert test_client.get(f"/api/v1/projects/{project_id}/members", headers=fa_headers).status_code == 403
		assert test_client.get(f"/api/v1/projects/{project_id}/members", headers=ds_headers).status_code == 403

		# 6. fraud_analyst gets 403 on dataset delete/mapping/fe/export, rule create/update/delete/status/backtest, model/training
		assert test_client.delete(f"/api/v1/datasets/{ds_id}", headers=fa_headers).status_code == 403
		assert test_client.post(
			"/api/v1/rules",
			json={
				"project_id": project_id,
				"rule_code": "R-901",
				"name": "Draft",
				"condition": {"==": [1, 1]},
				"action": RuleAction.REVIEW.value,
				"status": RuleStatus.DRAFT.value,
			},
			headers=fa_headers,
		).status_code == 403
		assert test_client.delete(f"/api/v1/rules/{rule_id}", headers=fa_headers).status_code == 403
		assert test_client.patch(
			f"/api/v1/rules/{rule_id}/status",
			json={"status": "ACTIVE"},
			headers=fa_headers,
		).status_code == 403
		assert test_client.post(
			"/api/v1/rules/evaluate-batch",
			json={"project_id": project_id, "transaction_id": "t1", "raw_features": {}},
			headers=fa_headers,
		).status_code == 403
		assert test_client.get(f"/api/v1/training/models?project_id={project_id}", headers=fa_headers).status_code == 403
		assert test_client.get(f"/api/v1/training/runs?project_id={project_id}", headers=fa_headers).status_code == 403

		# 7. data_scientist gets 403 on investigation sub-endpoints, send-to-investigation, and SAR/executive creation
		assert test_client.get(f"/api/v1/cases/kpis?project_id={project_id}", headers=ds_headers).status_code == 403
		assert test_client.get(f"/api/v1/cases/rule-feedback?project_id={project_id}", headers=ds_headers).status_code == 403
		assert test_client.post(
			f"/api/v1/detection/jobs/{job_id}/send-to-investigation",
			json={"event_ids": ["e1"]},
			headers=ds_headers,
		).status_code == 403
		assert test_client.get(f"/api/v1/reports/executive-summary?project_id={project_id}", headers=ds_headers).status_code == 403
		assert test_client.get(f"/api/v1/reports/overview?project_id={project_id}", headers=ds_headers).status_code == 200


def test_list_and_import_endpoints_require_project_id_and_enforce_permission(server_settings, monkeypatch):
	"""ISS-042: List endpoints and import/training create require project_id and enforce project permissions."""
	from fastapi.testclient import TestClient
	from usfds_core.domain.entities.auth import Role
	from usfds_core.domain.entities.enums import RoleScope
	from usfds_infra.database.repos.auth import SqlProjectMemberRepository, SqlRoleRepository
	from usfds_server import dependencies
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_token = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"}).json()["data"]["access_token"]
		admin_headers = {"Authorization": f"Bearer {admin_token}"}

		project_a = test_client.post("/api/v1/projects", json={"project_name": "Scope List A"}, headers=admin_headers).json()["data"]["project_id"]

		roles = test_client.get("/api/v1/rbac/roles", headers=admin_headers).json()["data"]
		fa_role = next(r for r in roles if r["name"] == "fraud_analyst")
		member_no_ds_role = test_client.post(
			"/api/v1/rbac/roles",
			json={
				"name": "member_no_ds",
				"display_name": "Member Without Dataset Perms",
				"scope": "PROJECT",
				"grants": [{"permission_code": "project:read", "grant_scope": "PROJECT"}],
			},
			headers=admin_headers,
		).json()["data"]

		test_client.post(
			f"/api/v1/projects/{project_a}/members",
			json={"username": "u_nods", "password": "UserNoDs123!", "role_id": member_no_ds_role["role_id"]},
			headers=admin_headers,
		)
		test_client.post(
			f"/api/v1/projects/{project_a}/members",
			json={"username": "fa_list", "password": "FaListPass123!", "role_id": fa_role["role_id"]},
			headers=admin_headers,
		)

		nods_token = test_client.post("/api/v1/auth/login", json={"username": "u_nods", "password": "UserNoDs123!"}).json()["data"]["access_token"]
		fa_token = test_client.post("/api/v1/auth/login", json={"username": "fa_list", "password": "FaListPass123!"}).json()["data"]["access_token"]
		nods_headers = {"Authorization": f"Bearer {nods_token}"}
		fa_headers = {"Authorization": f"Bearer {fa_token}"}

		rf_id = str(dependencies.BUILTIN_RANDOM_FOREST_ID)

		# (a) Missing project_id -> 422
		assert test_client.get("/api/v1/datasets", headers=nods_headers).status_code == 422
		assert test_client.post("/api/v1/datasets/import", json={"file_path": "x.csv"}, headers=nods_headers).status_code == 422
		assert test_client.get("/api/v1/training/models", headers=fa_headers).status_code == 422
		assert test_client.get(f"/api/v1/training/models/{rf_id}/versions", headers=fa_headers).status_code == 422
		assert test_client.get("/api/v1/training/runs", headers=fa_headers).status_code == 422
		assert test_client.post(
			"/api/v1/training/runs",
			json={"model_id": rf_id, "dataset_artifact_id": str(uuid4())},
			headers=fa_headers,
		).status_code == 422

		# (b) With project_id=A but missing permission -> 403
		assert test_client.get(f"/api/v1/datasets?project_id={project_a}", headers=nods_headers).status_code == 403
		assert test_client.post(
			"/api/v1/datasets/import",
			json={"file_path": "x.csv", "project_id": project_a},
			headers=nods_headers,
		).status_code == 403
		assert test_client.get(f"/api/v1/training/models?project_id={project_a}", headers=fa_headers).status_code == 403
		assert test_client.get(f"/api/v1/training/models/{rf_id}/versions?project_id={project_a}", headers=fa_headers).status_code == 403
		assert test_client.get(f"/api/v1/training/runs?project_id={project_a}", headers=fa_headers).status_code == 403
		assert test_client.post(
			"/api/v1/training/runs",
			json={"project_id": project_a, "model_id": rf_id, "dataset_artifact_id": str(uuid4())},
			headers=fa_headers,
		).status_code == 403


def test_get_by_id_endpoints_require_project_id_block_null_and_prevent_oracle(server_settings, monkeypatch):
	"""ISS-042: GET-by-ID endpoints require project_id, block NULL-project models/runs, and prevent 404 vs 403 oracle."""
	from uuid import UUID
	from fastapi.testclient import TestClient
	from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
	from usfds_core.domain.entities.detection import DetectionJob
	from usfds_core.domain.entities.enums import ExecutionType, ModelVersionStatus, PipelineStage, RuleAction, RuleStatus, TrainingRunStatus
	from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
	from usfds_core.domain.entities.rule import Rule, RuleVersion
	from usfds_infra.database.repos.dataset import SqliteDatasetArtifactRepository, SqliteDatasetRepository
	from usfds_infra.database.repos.detection import SqliteDetectionJobRepository
	from usfds_infra.database.repos.model import SqliteModelRepository, SqliteModelVersionRepository, SqliteTrainingRunRepository
	from usfds_infra.database.repos.rule import SqliteRuleRepository, SqliteRuleVersionRepository
	from usfds_server import dependencies
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_token = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"}).json()["data"]["access_token"]
		admin_headers = {"Authorization": f"Bearer {admin_token}"}

		proj_a = test_client.post("/api/v1/projects", json={"project_name": "Oracle A"}, headers=admin_headers).json()["data"]["project_id"]
		proj_b = test_client.post("/api/v1/projects", json={"project_name": "Oracle B"}, headers=admin_headers).json()["data"]["project_id"]
		proj_b_uuid = UUID(proj_b)

		roles = test_client.get("/api/v1/rbac/roles", headers=admin_headers).json()["data"]
		ds_role = next(r for r in roles if r["name"] == "data_scientist")
		fa_role = next(r for r in roles if r["name"] == "fraud_analyst")

		test_client.post(
			f"/api/v1/projects/{proj_a}/members",
			json={"username": "ds_oracle", "password": "DsOracle123!", "role_id": ds_role["role_id"]},
			headers=admin_headers,
		)
		test_client.post(
			f"/api/v1/projects/{proj_a}/members",
			json={"username": "fa_oracle", "password": "FaOracle123!", "role_id": fa_role["role_id"]},
			headers=admin_headers,
		)
		ds_token = test_client.post("/api/v1/auth/login", json={"username": "ds_oracle", "password": "DsOracle123!"}).json()["data"]["access_token"]
		fa_token = test_client.post("/api/v1/auth/login", json={"username": "fa_oracle", "password": "FaOracle123!"}).json()["data"]["access_token"]
		ds_headers = {"Authorization": f"Bearer {ds_token}"}
		fa_headers = {"Authorization": f"Bearer {fa_token}"}

		ds_b = uuid4()
		art_b = uuid4()
		model_b = uuid4()
		ver_b = uuid4()
		run_b = uuid4()
		job_b = uuid4()
		rule_b = uuid4()
		ver_null = uuid4()
		run_null = uuid4()
		rf_id = dependencies.BUILTIN_RANDOM_FOREST_ID

		with dependencies._session_factory() as session:
			admin_id = SqlUserRepository(session).get_by_username("admin").user_id
			SqliteDatasetRepository(session).save(
				Dataset(dataset_id=ds_b, project_id=proj_b_uuid, user_id=admin_id, dataset_name="ds_b")
			)
			SqliteDatasetArtifactRepository(session).save(
				DatasetArtifact(artifact_id=art_b, dataset_id=ds_b, pipeline_stage=PipelineStage.RAW, storage_path="datasets/b/raw.csv")
			)
			SqliteModelRepository(session).save(
				Model(model_id=model_b, project_id=proj_b_uuid, user_id=admin_id, model_name="custom_b", execution_type=ExecutionType.SCRIPT)
			)
			SqliteTrainingRunRepository(session).save(
				TrainingRun(run_id=run_b, project_id=proj_b_uuid, user_id=admin_id, model_id=model_b, version_id=ver_b, run_name="run_b", status=TrainingRunStatus.COMPLETED)
			)
			SqliteModelVersionRepository(session).save(
				ModelVersion(version_id=ver_b, model_id=model_b, project_id=proj_b_uuid, user_id=admin_id, run_id=run_b, semver="v1", artifact_uri="models/b/v1.zip", status=ModelVersionStatus.CANDIDATE)
			)
			SqliteTrainingRunRepository(session).save(
				TrainingRun(run_id=run_null, project_id=None, user_id=admin_id, model_id=rf_id, version_id=ver_null, run_name="run_null", status=TrainingRunStatus.COMPLETED)
			)
			SqliteModelVersionRepository(session).save(
				ModelVersion(version_id=ver_null, model_id=rf_id, project_id=None, user_id=admin_id, run_id=run_null, semver="v1", artifact_uri="models/null/v1.joblib", status=ModelVersionStatus.CANDIDATE)
			)
			SqliteDetectionJobRepository(session).save(
				DetectionJob(job_id=job_b, project_id=proj_b_uuid, user_id=admin_id, job_name="job_b", input_path="datasets/b/raw.csv")
			)
			r_ver_id = uuid4()
			SqliteRuleRepository(session).save(
				Rule(rule_id=rule_b, project_id=proj_b_uuid, user_id=admin_id, rule_code="R-B1", name="Rule B", description="", status=RuleStatus.DRAFT, current_version_id=r_ver_id)
			)
			SqliteRuleVersionRepository(session).save(
				RuleVersion(rule_version_id=r_ver_id, rule_id=rule_b, version_number=1, condition={"==": [1, 1]}, action=RuleAction.REVIEW)
			)
			session.commit()

		get_paths = [
			f"/api/v1/datasets/{ds_b}",
			f"/api/v1/datasets/{ds_b}/artifacts/{art_b}",
			f"/api/v1/training/models/{model_b}",
			f"/api/v1/training/models/{model_b}/versions",
			f"/api/v1/training/versions/{ver_b}",
			f"/api/v1/training/versions/{ver_b}/lineage",
			f"/api/v1/training/runs/{run_b}",
			f"/api/v1/training/runs/{run_b}/lineage",
			f"/api/v1/detection/jobs/{job_b}",
			f"/api/v1/detection/jobs/{job_b}/results",
			f"/api/v1/detection/jobs/{job_b}/export",
			f"/api/v1/rules/{rule_b}",
			f"/api/v1/rules/{rule_b}/versions",
		]

		# (a) Missing project_id -> 422
		for path in get_paths:
			assert test_client.get(path, headers=ds_headers).status_code == 422, path

		# (b) project_id=B -> 403 for both real B IDs and nonexistent random IDs (no 404 oracle)
		for path in get_paths:
			assert test_client.get(path, params={"project_id": proj_b}, headers=ds_headers).status_code == 403, path

		missing_id = uuid4()
		oracle_probe_paths = [
			f"/api/v1/datasets/{missing_id}",
			f"/api/v1/datasets/{missing_id}/artifacts/{uuid4()}",
			f"/api/v1/training/models/{missing_id}",
			f"/api/v1/training/models/{missing_id}/versions",
			f"/api/v1/training/versions/{missing_id}",
			f"/api/v1/training/versions/{missing_id}/lineage",
			f"/api/v1/training/runs/{missing_id}",
			f"/api/v1/training/runs/{missing_id}/lineage",
			f"/api/v1/detection/jobs/{missing_id}",
			f"/api/v1/detection/jobs/{missing_id}/results",
			f"/api/v1/detection/jobs/{missing_id}/export",
			f"/api/v1/rules/{missing_id}",
			f"/api/v1/rules/{missing_id}/versions",
		]
		for path in oracle_probe_paths:
			assert test_client.get(path, params={"project_id": proj_b}, headers=ds_headers).status_code == 403, path

		# (c) project_id=A with B's IDs or NULL-project ModelVersion/TrainingRun -> 404
		for path in get_paths:
			assert test_client.get(path, params={"project_id": proj_a}, headers=ds_headers).status_code == 404, path

		null_paths = [
			f"/api/v1/training/versions/{ver_null}",
			f"/api/v1/training/versions/{ver_null}/lineage",
			f"/api/v1/training/runs/{run_null}",
			f"/api/v1/training/runs/{run_null}/lineage",
		]
		for path in null_paths:
			assert test_client.get(path, params={"project_id": proj_a}, headers=ds_headers).status_code == 404, path

		# (d) Built-in model (project_id=None) -> 200 with model:read on A, 403 without model:read on A
		assert test_client.get(f"/api/v1/training/models/{rf_id}", params={"project_id": proj_a}, headers=ds_headers).status_code == 200
		assert test_client.get(f"/api/v1/training/models/{rf_id}", params={"project_id": proj_a}, headers=fa_headers).status_code == 403


def test_cross_project_training_rule_version_and_storage_download_blocked(server_settings, monkeypatch):
	"""ISS-042: Cross-project training artifact, rule version_id, and storage presigned-download are blocked."""
	import io
	import pandas as pd
	from uuid import UUID
	from fastapi.testclient import TestClient
	from moto import mock_aws
	from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
	from usfds_core.domain.entities.detection import DetectionJob
	from usfds_core.domain.entities.enums import PipelineStage, RuleAction, RuleStatus, ValidationStatus
	from usfds_core.domain.entities.rule import Rule, RuleVersion
	from usfds_infra.database.repos.dataset import SqliteDatasetArtifactRepository, SqliteDatasetRepository
	from usfds_infra.database.repos.detection import SqliteDetectionJobRepository
	from usfds_infra.database.repos.rule import SqliteRuleRepository, SqliteRuleVersionRepository
	from usfds_infra.storage.s3_storage import S3FileStorage
	from usfds_server import dependencies
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with mock_aws():
		s3_storage = S3FileStorage(bucket="usfds", access_key="test", secret_key="test", region="us-east-1")
		with TestClient(app) as test_client:
			monkeypatch.setattr(dependencies, "_storage", s3_storage)

			admin_token = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"}).json()["data"]["access_token"]
			admin_headers = {"Authorization": f"Bearer {admin_token}"}

			proj_a = test_client.post("/api/v1/projects", json={"project_name": "Cross A"}, headers=admin_headers).json()["data"]["project_id"]
			proj_b = test_client.post("/api/v1/projects", json={"project_name": "Cross B"}, headers=admin_headers).json()["data"]["project_id"]

			roles = test_client.get("/api/v1/rbac/roles", headers=admin_headers).json()["data"]
			ds_role = next(r for r in roles if r["name"] == "data_scientist")
			test_client.post(
				f"/api/v1/projects/{proj_a}/members",
				json={"username": "ds_cross", "password": "DsCross123!", "role_id": ds_role["role_id"]},
				headers=admin_headers,
			)
			ds_token = test_client.post("/api/v1/auth/login", json={"username": "ds_cross", "password": "DsCross123!"}).json()["data"]["access_token"]
			ds_headers = {"Authorization": f"Bearer {ds_token}"}

			ds_a = uuid4()
			art_a = uuid4()
			ds_b = uuid4()
			art_b = uuid4()
			job_b = uuid4()
			rule_a = uuid4()
			rv_a = uuid4()
			rule_b = uuid4()
			rv_b = uuid4()

			buf = io.BytesIO()
			pd.DataFrame({"event_id": ["e1", "e2"], "user_id": ["u1", "u2"], "timestamp": ["2026-01-01", "2026-01-02"], "amount": [10.0, 20.0], "label": [0, 1]}).to_parquet(buf, index=False)
			train_key = f"datasets/{ds_b}/artifacts/{art_b}/train.parquet"
			s3_storage.save_bytes(train_key, buf.getvalue())

			with dependencies._session_factory() as session:
				admin_id = SqlUserRepository(session).get_by_username("admin").user_id
				ds_user_id = SqlUserRepository(session).get_by_username("ds_cross").user_id
				ds_repo = SqliteDatasetRepository(session)
				art_repo = SqliteDatasetArtifactRepository(session)
				rule_repo = SqliteRuleRepository(session)
				rv_repo = SqliteRuleVersionRepository(session)
				job_repo = SqliteDetectionJobRepository(session)

				ds_repo.save(Dataset(dataset_id=ds_a, project_id=UUID(proj_a), user_id=ds_user_id, dataset_name="ds_a"))
				art_repo.save(DatasetArtifact(artifact_id=art_a, dataset_id=ds_a, pipeline_stage=PipelineStage.RAW, storage_path=f"datasets/{ds_a}/raw.csv", validation_status=ValidationStatus.PASSED))
				ds_repo.save(Dataset(dataset_id=ds_b, project_id=UUID(proj_b), user_id=admin_id, dataset_name="ds_b"))
				art_repo.save(
					DatasetArtifact(
						artifact_id=art_b,
						dataset_id=ds_b,
						pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
						storage_path=f"datasets/{ds_b}/artifacts/{art_b}",
						output_paths={"train": train_key},
						validation_status=ValidationStatus.PASSED,
						validation_report={"target_column": "label"},
					)
				)
				job_repo.save(DetectionJob(job_id=job_b, project_id=UUID(proj_b), user_id=admin_id, job_name="job_b", input_path="datasets/b/raw.csv"))

				rule_repo.save(Rule(rule_id=rule_a, project_id=UUID(proj_a), user_id=ds_user_id, rule_code="RA", name="Rule A", description="", status=RuleStatus.DRAFT, current_version_id=rv_a))
				rv_repo.save(RuleVersion(rule_version_id=rv_a, rule_id=rule_a, version_number=1, condition={"==": [1, 1]}, action=RuleAction.REVIEW))
				rule_repo.save(Rule(rule_id=rule_b, project_id=UUID(proj_b), user_id=admin_id, rule_code="RB", name="Rule B", description="", status=RuleStatus.DRAFT, current_version_id=rv_b))
				rv_repo.save(RuleVersion(rule_version_id=rv_b, rule_id=rule_b, version_number=1, condition={">": [{"var": "amount"}, 1]}, action=RuleAction.REJECT))
				session.commit()

			# 1. Cross-project dataset_artifact_id in POST /training/runs -> 400
			rf_id = str(dependencies.BUILTIN_RANDOM_FOREST_ID)
			res_train = test_client.post(
				"/api/v1/training/runs",
				json={"project_id": proj_a, "model_id": rf_id, "dataset_artifact_id": str(art_b)},
				headers=ds_headers,
			)
			assert res_train.status_code == 400

			# 2. Cross-project RuleVersion in evaluate & backtest -> 400/404
			res_eval = test_client.post(
				f"/api/v1/rules/{rule_a}/evaluate",
				params={"version_id": str(rv_b)},
				json={"transaction_id": "tx1", "raw_features": {"amount": 100}},
				headers=ds_headers,
			)
			assert res_eval.status_code in (400, 404)

			res_bt = test_client.post(
				"/api/v1/rules/backtest",
				json={"project_id": proj_a, "dataset_artifact_id": str(art_a), "rule_id": str(rule_a), "version_id": str(rv_b)},
				headers=ds_headers,
			)
			assert res_bt.status_code in (400, 404)

			# 3. Storage presigned-download guards
			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"object_key": f"uploads/dataset_raw/{proj_a}/file.csv"},
				headers=ds_headers,
			).status_code == 422

			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"uploads/dataset_raw/{proj_a}/../secret.csv"},
				headers=ds_headers,
			).status_code == 400

			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"uploads/dataset_raw/{proj_b}/file.csv"},
				headers=ds_headers,
			).status_code == 403

			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"exports/datasets/{ds_b}/export.zip"},
				headers=ds_headers,
			).status_code == 403

			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"exports/detection/{job_b}/res.csv"},
				headers=ds_headers,
			).status_code == 403

			# data_scientist does not have report:export on Project A -> 403
			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"exports/reports/{proj_a}/audit.md"},
				headers=ds_headers,
			).status_code == 403


def test_own_scope_list_and_get_by_id_across_core_routers(server_settings, monkeypatch):
	"""ISS-043: Custom role with GrantScope.OWN on read/export filters list endpoints by user_id and enforces 403 vs 404 on get-by-id."""
	import io
	import pandas as pd
	from uuid import UUID
	from fastapi.testclient import TestClient
	from moto import mock_aws
	from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
	from usfds_core.domain.entities.detection import DetectionJob
	from usfds_core.domain.entities.enums import (
		DetectionJobStatus,
		ExecutionType,
		ModelVersionStatus,
		PipelineStage,
		RuleAction,
		RuleStatus,
		TrainingRunStatus,
		ValidationStatus,
	)
	from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
	from usfds_core.domain.entities.rule import Rule, RuleVersion
	from usfds_infra.database.repos.dataset import SqliteDatasetArtifactRepository, SqliteDatasetRepository
	from usfds_infra.database.repos.detection import SqliteDetectionJobRepository
	from usfds_infra.database.repos.model import SqliteModelRepository, SqliteModelVersionRepository, SqliteTrainingRunRepository
	from usfds_infra.database.repos.rule import SqliteRuleRepository, SqliteRuleVersionRepository
	from usfds_infra.storage.s3_storage import S3FileStorage
	from usfds_server import dependencies
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with mock_aws():
		s3_storage = S3FileStorage(bucket="usfds", access_key="test", secret_key="test", region="us-east-1")
		with TestClient(app) as test_client:
			monkeypatch.setattr(dependencies, "_storage", s3_storage)

			admin_token = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"}).json()["data"]["access_token"]
			admin_headers = {"Authorization": f"Bearer {admin_token}"}

			# Create custom PROJECT role with GrantScope.OWN on read & export permissions
			own_role_res = test_client.post(
				"/api/v1/rbac/roles",
				json={"name": "own_reader", "display_name": "Own Reader", "scope": "PROJECT"},
				headers=admin_headers,
			)
			assert own_role_res.status_code == 201, own_role_res.text
			own_role_id = own_role_res.json()["data"]["role_id"]

			own_perms = [
				"project:read",
				"dataset:read",
				"dataset:export",
				"model:read",
				"training:read",
				"rule:read",
				"rule:dry_run",
				"detection:read",
				"detection:export",
			]
			set_perm_res = test_client.put(
				f"/api/v1/rbac/roles/{own_role_id}/permissions",
				json={"grants": [{"permission_code": code, "grant_scope": "OWN"} for code in own_perms]},
				headers=admin_headers,
			)
			assert set_perm_res.status_code == 200, set_perm_res.text

			# Create users u1 and u2
			u1_res = test_client.post(
				"/api/v1/users",
				json={"username": "u1_own", "password": "UserOne123!", "email": "u1@usfds.local", "full_name": "U1", "system_roles": ["system_member"]},
				headers=admin_headers,
			)
			u2_res = test_client.post(
				"/api/v1/users",
				json={"username": "u2_own", "password": "UserTwo123!", "email": "u2@usfds.local", "full_name": "U2", "system_roles": ["system_member"]},
				headers=admin_headers,
			)
			u1_id = UUID(u1_res.json()["data"]["user_id"])
			u2_id = UUID(u2_res.json()["data"]["user_id"])

			u1_token = test_client.post("/api/v1/auth/login", json={"username": "u1_own", "password": "UserOne123!"}).json()["data"]["access_token"]
			u1_headers = {"Authorization": f"Bearer {u1_token}"}

			# u1 creates Project A, admin creates Project B; attach admin as project_admin on A so u1's role can be replaced with own_role_id
			roles = test_client.get("/api/v1/rbac/roles", headers=admin_headers).json()["data"]
			pa_role = next(r for r in roles if r["name"] == "project_admin")
			admin_me = test_client.get("/api/v1/auth/me", headers=admin_headers).json()["data"]
			proj_a = test_client.post("/api/v1/projects", json={"project_name": "Own Proj A"}, headers=u1_headers).json()["data"]["project_id"]
			proj_b = test_client.post("/api/v1/projects", json={"project_name": "Own Proj B"}, headers=admin_headers).json()["data"]["project_id"]
			proj_a_uuid = UUID(proj_a)

			test_client.post(
				f"/api/v1/projects/{proj_a}/members",
				json={"user_id": admin_me["user_id"], "role_id": pa_role["role_id"]},
				headers=admin_headers,
			)
			# Replace u1's role in Project A with own_role_id, and add u2 to Project A with own_role_id
			rep_res = test_client.put(
				f"/api/v1/projects/{proj_a}/members/{u1_id}/roles",
				json={"role_ids": [own_role_id]},
				headers=admin_headers,
			)
			assert rep_res.status_code == 200, rep_res.text
			test_client.post(
				f"/api/v1/projects/{proj_a}/members",
				json={"user_id": str(u2_id), "role_id": own_role_id},
				headers=admin_headers,
			)

			# Also create Project C owned by u2 where u1 is added with own_role_id (project:read:OWN)
			u2_token = test_client.post("/api/v1/auth/login", json={"username": "u2_own", "password": "UserTwo123!"}).json()["data"]["access_token"]
			u2_headers = {"Authorization": f"Bearer {u2_token}"}
			proj_c = test_client.post("/api/v1/projects", json={"project_name": "Own Proj C"}, headers=u2_headers).json()["data"]["project_id"]
			test_client.post(
				f"/api/v1/projects/{proj_c}/members",
				json={"user_id": str(u1_id), "role_id": own_role_id},
				headers=admin_headers,
			)

			# Seed u1 and u2 resources inside Project A
			ds1, ds2 = uuid4(), uuid4()
			art1, art2 = uuid4(), uuid4()
			m1, m2 = uuid4(), uuid4()
			run1, run2 = uuid4(), uuid4()
			ver1, ver2 = uuid4(), uuid4()
			rule1, rule2 = uuid4(), uuid4()
			rv1, rv2 = uuid4(), uuid4()
			job1, job2 = uuid4(), uuid4()
			rf_id = dependencies.BUILTIN_RANDOM_FOREST_ID

			pred_buf = io.BytesIO()
			pd.DataFrame([
				{
					"event_id": "e1",
					"user_id": "cust1",
					"timestamp": "2026-01-01T00:00:00Z",
					"amount": 100.0,
					"model_score": 0.9,
					"triggered_rules": "[]",
					"triggered_rule_details": "[]",
					"rule_action": "ALLOW",
					"final_action": "REJECT",
					"is_flagged": True,
				}
			]).to_parquet(pred_buf, index=False)
			out1 = f"datasets/{proj_a}/inferences/{job1}/predictions.parquet"
			out2 = f"datasets/{proj_a}/inferences/{job2}/predictions.parquet"
			s3_storage.save_bytes(out1, pred_buf.getvalue())
			s3_storage.save_bytes(out2, pred_buf.getvalue())
			s3_storage.save_bytes(f"exports/datasets/{ds1}/b.zip", b"zip1")
			s3_storage.save_bytes(f"exports/datasets/{ds2}/b.zip", b"zip2")
			s3_storage.save_bytes(f"exports/detection/{job1}/r.csv", b"csv1")
			s3_storage.save_bytes(f"exports/detection/{job2}/r.csv", b"csv2")

			with dependencies._session_factory() as session:
				ds_repo = SqliteDatasetRepository(session)
				art_repo = SqliteDatasetArtifactRepository(session)
				m_repo = SqliteModelRepository(session)
				run_repo = SqliteTrainingRunRepository(session)
				ver_repo = SqliteModelVersionRepository(session)
				r_repo = SqliteRuleRepository(session)
				rv_repo = SqliteRuleVersionRepository(session)
				j_repo = SqliteDetectionJobRepository(session)

				for uid, d_id, a_id, m_id, rn_id, v_id, rl_id, rlv_id, jb_id, out_key, suffix in (
					(u1_id, ds1, art1, m1, run1, ver1, rule1, rv1, job1, out1, "1"),
					(u2_id, ds2, art2, m2, run2, ver2, rule2, rv2, job2, out2, "2"),
				):
					ds_repo.save(Dataset(dataset_id=d_id, project_id=proj_a_uuid, user_id=uid, dataset_name=f"ds_{suffix}"))
					art_repo.save(
						DatasetArtifact(
							artifact_id=a_id,
							dataset_id=d_id,
							pipeline_stage=PipelineStage.RAW,
							storage_path=f"datasets/{d_id}/raw.csv",
							validation_status=ValidationStatus.PASSED,
						)
					)
					m_repo.save(Model(model_id=m_id, project_id=proj_a_uuid, user_id=uid, model_name=f"custom_m_{suffix}", execution_type=ExecutionType.SCRIPT))
					run_repo.save(
						TrainingRun(
							run_id=rn_id,
							project_id=proj_a_uuid,
							user_id=uid,
							model_id=rf_id,
							version_id=v_id,
							run_name=f"run_{suffix}",
							status=TrainingRunStatus.COMPLETED,
						)
					)
					ver_repo.save(
						ModelVersion(
							version_id=v_id,
							model_id=rf_id,
							project_id=proj_a_uuid,
							user_id=uid,
							run_id=rn_id,
							semver=f"v{suffix}",
							artifact_uri=f"models/v{suffix}.joblib",
							status=ModelVersionStatus.CANDIDATE,
						)
					)
					r_repo.save(
						Rule(
							rule_id=rl_id,
							project_id=proj_a_uuid,
							user_id=uid,
							rule_code=f"R-{suffix}",
							name=f"Rule {suffix}",
							description="",
							status=RuleStatus.ACTIVE,
							current_version_id=rlv_id,
						)
					)
					rv_repo.save(
						RuleVersion(
							rule_version_id=rlv_id,
							rule_id=rl_id,
							version_number=1,
							condition={">": [{"var": "amount"}, 10]},
							action=RuleAction.REJECT,
						)
					)
					j_repo.save(
						DetectionJob(
							job_id=jb_id,
							project_id=proj_a_uuid,
							user_id=uid,
							job_name=f"job_{suffix}",
							input_path="raw.csv",
							output_path=out_key,
							status=DetectionJobStatus.COMPLETED,
						)
					)
				session.commit()

			# 1. Project read under OWN: u1 can get Project A (200), cannot get Project C owned by u2 (403)
			assert test_client.get(f"/api/v1/projects/{proj_a}", headers=u1_headers).status_code == 200
			assert test_client.get(f"/api/v1/projects/{proj_c}", headers=u1_headers).status_code == 403

			# 2. List endpoints in Project A only return u1's records (+ built-in models for GET /models)
			ds_list = test_client.get("/api/v1/datasets", params={"project_id": proj_a}, headers=u1_headers).json()["data"]["items"]
			assert [d["dataset_id"] for d in ds_list] == [str(ds1)]

			m_list = test_client.get("/api/v1/training/models", params={"project_id": proj_a}, headers=u1_headers).json()["data"]["items"]
			m_ids = {m["model_id"] for m in m_list}
			assert str(m1) in m_ids
			assert str(rf_id) in m_ids
			assert str(m2) not in m_ids
			rf_dto = next(m for m in m_list if m["model_id"] == str(rf_id))
			assert rf_dto["user_id"] is None

			v_list = test_client.get(f"/api/v1/training/models/{rf_id}/versions", params={"project_id": proj_a}, headers=u1_headers).json()["data"]["items"]
			assert [v["version_id"] for v in v_list] == [str(ver1)]
			assert v_list[0]["user_id"] == str(u1_id)

			run_list = test_client.get("/api/v1/training/runs", params={"project_id": proj_a}, headers=u1_headers).json()["data"]["items"]
			assert [r["run_id"] for r in run_list] == [str(run1)]
			assert run_list[0]["user_id"] == str(u1_id)

			rule_list = test_client.get("/api/v1/rules", params={"project_id": proj_a}, headers=u1_headers).json()["data"]["items"]
			assert [r["rule_id"] for r in rule_list] == [str(rule1)]
			assert rule_list[0]["user_id"] == str(u1_id)

			eval_batch = test_client.post(
				"/api/v1/rules/evaluate-batch",
				json={"project_id": proj_a, "transaction_id": "tx_1", "raw_features": {"amount": 50}},
				headers=u1_headers,
			).json()["data"]
			assert [r["rule_id"] for r in eval_batch] == [str(rule1)]

			job_list = test_client.get("/api/v1/detection/jobs", params={"project_id": proj_a}, headers=u1_headers).json()["data"]["items"]
			assert [j["job_id"] for j in job_list] == [str(job1)]
			assert job_list[0]["user_id"] == str(u1_id)

			# 3. Get-by-id: u1's records & built-in model -> 200; u2's records -> 403; nonexistent ID in A -> 404; Project B -> 403
			u1_get_paths = [
				f"/api/v1/datasets/{ds1}",
				f"/api/v1/datasets/{ds1}/artifacts/{art1}",
				f"/api/v1/training/models/{rf_id}",
				f"/api/v1/training/models/{m1}",
				f"/api/v1/training/models/{m1}/versions",
				f"/api/v1/training/versions/{ver1}",
				f"/api/v1/training/versions/{ver1}/lineage",
				f"/api/v1/training/runs/{run1}",
				f"/api/v1/training/runs/{run1}/lineage",
				f"/api/v1/rules/{rule1}",
				f"/api/v1/rules/{rule1}/versions",
				f"/api/v1/detection/jobs/{job1}",
				f"/api/v1/detection/jobs/{job1}/results",
				f"/api/v1/detection/jobs/{job1}/export",
			]
			for path in u1_get_paths:
				res = test_client.get(path, params={"project_id": proj_a}, headers=u1_headers)
				assert res.status_code == 200, f"{path}: {res.status_code} {res.text}"

			u2_get_paths = [
				f"/api/v1/datasets/{ds2}",
				f"/api/v1/datasets/{ds2}/artifacts/{art2}",
				f"/api/v1/training/models/{m2}",
				f"/api/v1/training/models/{m2}/versions",
				f"/api/v1/training/versions/{ver2}",
				f"/api/v1/training/versions/{ver2}/lineage",
				f"/api/v1/training/runs/{run2}",
				f"/api/v1/training/runs/{run2}/lineage",
				f"/api/v1/rules/{rule2}",
				f"/api/v1/rules/{rule2}/versions",
				f"/api/v1/detection/jobs/{job2}",
				f"/api/v1/detection/jobs/{job2}/results",
				f"/api/v1/detection/jobs/{job2}/export",
			]
			for path in u2_get_paths:
				res = test_client.get(path, params={"project_id": proj_a}, headers=u1_headers)
				assert res.status_code == 403, f"Expected 403 on u2 resource {path}, got {res.status_code}"

			missing = uuid4()
			missing_paths = [
				f"/api/v1/datasets/{missing}",
				f"/api/v1/datasets/{missing}/artifacts/{uuid4()}",
				f"/api/v1/training/models/{missing}",
				f"/api/v1/training/models/{missing}/versions",
				f"/api/v1/training/versions/{missing}",
				f"/api/v1/training/versions/{missing}/lineage",
				f"/api/v1/training/runs/{missing}",
				f"/api/v1/training/runs/{missing}/lineage",
				f"/api/v1/rules/{missing}",
				f"/api/v1/rules/{missing}/versions",
				f"/api/v1/detection/jobs/{missing}",
				f"/api/v1/detection/jobs/{missing}/results",
				f"/api/v1/detection/jobs/{missing}/export",
			]
			for path in missing_paths:
				assert test_client.get(path, params={"project_id": proj_a}, headers=u1_headers).status_code == 404, path
				assert test_client.get(path, params={"project_id": proj_b}, headers=u1_headers).status_code == 403, path

			# 4. Storage presigned-download respects owner_id for dataset & detection exports
			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"exports/datasets/{ds1}/b.zip"},
				headers=u1_headers,
			).status_code == 200
			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"exports/datasets/{ds2}/b.zip"},
				headers=u1_headers,
			).status_code == 403
			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"exports/detection/{job1}/r.csv"},
				headers=u1_headers,
			).status_code == 200
			assert test_client.get(
				"/api/v1/storage/presigned-download",
				params={"project_id": proj_a, "object_key": f"exports/detection/{job2}/r.csv"},
				headers=u1_headers,
			).status_code == 403


def test_builtin_ds_own_mutate_isolation_and_project_admin_override(server_settings, monkeypatch):
	"""ISS-043: Default data_scientist role allows reading peer resources in project but blocks mutating/deleting/deploying them; project_admin overrides."""
	import io
	from pathlib import Path
	import pandas as pd
	from fastapi.testclient import TestClient
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_token = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"}).json()["data"]["access_token"]
		admin_headers = {"Authorization": f"Bearer {admin_token}"}

		proj_a = test_client.post("/api/v1/projects", json={"project_name": "DS Isolation Proj"}, headers=admin_headers).json()["data"]["project_id"]

		roles = test_client.get("/api/v1/rbac/roles", headers=admin_headers).json()["data"]
		ds_role = next(r for r in roles if r["name"] == "data_scientist")
		pa_role = next(r for r in roles if r["name"] == "project_admin")

		ds1_member = test_client.post(
			f"/api/v1/projects/{proj_a}/members",
			json={"username": "ds_one", "password": "DsOnePass123!", "role_id": ds_role["role_id"]},
			headers=admin_headers,
		).json()["data"]
		ds2_member = test_client.post(
			f"/api/v1/projects/{proj_a}/members",
			json={"username": "ds_two", "password": "DsTwoPass123!", "role_id": ds_role["role_id"]},
			headers=admin_headers,
		).json()["data"]
		pa_member = test_client.post(
			f"/api/v1/projects/{proj_a}/members",
			json={"username": "proj_adm", "password": "ProjAdmPass123!", "role_id": pa_role["role_id"]},
			headers=admin_headers,
		).json()["data"]

		ds1_token = test_client.post("/api/v1/auth/login", json={"username": "ds_one", "password": "DsOnePass123!"}).json()["data"]["access_token"]
		ds2_token = test_client.post("/api/v1/auth/login", json={"username": "ds_two", "password": "DsTwoPass123!"}).json()["data"]["access_token"]
		pa_token = test_client.post("/api/v1/auth/login", json={"username": "proj_adm", "password": "ProjAdmPass123!"}).json()["data"]["access_token"]

		ds1_headers = {"Authorization": f"Bearer {ds1_token}"}
		ds2_headers = {"Authorization": f"Bearer {ds2_token}"}
		pa_headers = {"Authorization": f"Bearer {pa_token}"}

		# ds1 imports a dataset, maps schema, runs feature engineering, creates a rule, and trains a model version
		csv_path = Path(server_settings.storage_dir) / "ds1_input.csv"
		csv_path.parent.mkdir(parents=True, exist_ok=True)
		pd.DataFrame({
			"event_id": [f"ev_{i}" for i in range(40)],
			"user_id": [f"u_{i % 4}" for i in range(40)],
			"timestamp": [f"2026-01-01T00:{i:02d}:00Z" for i in range(40)],
			"amount": [100.0 + i * 10 for i in range(40)],
			"label": [1 if i % 4 == 0 else 0 for i in range(40)],
		}).to_csv(csv_path, index=False)

		imp_res = test_client.post(
			"/api/v1/datasets/import",
			json={"file_path": str(csv_path), "dataset_name": "ds1_dataset", "project_id": proj_a},
			headers=ds1_headers,
		)
		assert imp_res.status_code == 201, imp_res.text
		ds1_dataset_id = imp_res.json()["data"]["dataset"]["dataset_id"]
		assert imp_res.json()["data"]["dataset"]["user_id"] == ds1_member["user_id"]

		mapping_payload = {
			"event_id_column": "event_id",
			"user_id_column": "user_id",
			"time_column": "timestamp",
			"amount_column": "amount",
			"target_column": "label",
		}
		# ds2 can read ds1's dataset (200), but CANNOT map schema (403) or delete it (403)
		assert test_client.get(f"/api/v1/datasets/{ds1_dataset_id}", params={"project_id": proj_a}, headers=ds2_headers).status_code == 200
		assert test_client.post(f"/api/v1/datasets/{ds1_dataset_id}/schema-mapping", json=mapping_payload, headers=ds2_headers).status_code == 403
		assert test_client.delete(f"/api/v1/datasets/{ds1_dataset_id}", headers=ds2_headers).status_code == 403

		# ds1 maps schema and runs feature engineering on own dataset (201)
		assert test_client.post(f"/api/v1/datasets/{ds1_dataset_id}/schema-mapping", json=mapping_payload, headers=ds1_headers).status_code == 201
		fe_payload = {"enable_hour_of_day": True, "enable_amount_ratios": True, "enable_velocity_features": False}
		assert test_client.post(f"/api/v1/datasets/{ds1_dataset_id}/feature-engineering", json=fe_payload, headers=ds2_headers).status_code == 403
		fe_res = test_client.post(f"/api/v1/datasets/{ds1_dataset_id}/feature-engineering", json=fe_payload, headers=ds1_headers)
		assert fe_res.status_code == 201, fe_res.text
		fe_artifact_id = fe_res.json()["data"]["artifact_id"]

		# ds1 creates a rule (201)
		rule_res = test_client.post(
			"/api/v1/rules",
			json={
				"project_id": proj_a,
				"rule_code": "R_DS1",
				"name": "DS1 Rule",
				"condition": {">": [{"var": "amount"}, 200]},
				"action": "REVIEW",
				"status": "DRAFT",
			},
			headers=ds1_headers,
		)
		assert rule_res.status_code == 201, rule_res.text
		rule_id = rule_res.json()["data"]["rule_id"]
		assert rule_res.json()["data"]["user_id"] == ds1_member["user_id"]

		# ds2 can read and dry-run ds1's rule (200), but CANNOT update, deploy, or delete it (403)
		assert test_client.get(f"/api/v1/rules/{rule_id}", params={"project_id": proj_a}, headers=ds2_headers).status_code == 200
		assert test_client.post(
			f"/api/v1/rules/{rule_id}/evaluate",
			json={"transaction_id": "tx_1", "raw_features": {"amount": 300}},
			headers=ds2_headers,
		).status_code == 200
		assert test_client.put(f"/api/v1/rules/{rule_id}", json={"name": "Hijack"}, headers=ds2_headers).status_code == 403
		assert test_client.patch(f"/api/v1/rules/{rule_id}/status", json={"status": "ACTIVE"}, headers=ds2_headers).status_code == 403
		assert test_client.delete(f"/api/v1/rules/{rule_id}", headers=ds2_headers).status_code == 403

		# ds1 updates own rule (200)
		assert test_client.put(f"/api/v1/rules/{rule_id}", json={"name": "DS1 Updated Rule"}, headers=ds1_headers).status_code == 200

		# ds1 trains a model version (201)
		models = test_client.get("/api/v1/training/models", params={"project_id": proj_a}, headers=ds1_headers).json()["data"]["items"]
		rf_id = next(m["model_id"] for m in models if m["model_name"] == "random_forest")
		run_res = test_client.post(
			"/api/v1/training/runs",
			json={"project_id": proj_a, "model_id": rf_id, "dataset_artifact_id": fe_artifact_id, "hyperparameters": {"n_estimators": 5}},
			headers=ds1_headers,
		)
		assert run_res.status_code == 201, run_res.text
		run_data = run_res.json()["data"]
		assert run_data["user_id"] == ds1_member["user_id"]
		ver_id = run_data["version_id"]

		# ds2 can read ds1's run and version (200), but CANNOT activate/deploy ds1's model version (403)
		assert test_client.get(f"/api/v1/training/runs/{run_data['run_id']}", params={"project_id": proj_a}, headers=ds2_headers).status_code == 200
		assert test_client.get(f"/api/v1/training/versions/{ver_id}", params={"project_id": proj_a}, headers=ds2_headers).status_code == 200
		assert test_client.post(f"/api/v1/training/versions/{ver_id}/activate", json={"decision_threshold": 0.55}, headers=ds2_headers).status_code == 403

		# ds1 activates own model version (200)
		assert test_client.post(f"/api/v1/training/versions/{ver_id}/activate", json={"decision_threshold": 0.55}, headers=ds1_headers).status_code == 200

		# project_admin overrides: can deploy, undeploy, and delete ds1's rule, and delete ds1's dataset (200)
		assert test_client.patch(f"/api/v1/rules/{rule_id}/status", json={"status": "ACTIVE"}, headers=pa_headers).status_code == 200
		assert test_client.patch(f"/api/v1/rules/{rule_id}/status", json={"status": "INACTIVE"}, headers=pa_headers).status_code == 200
		assert test_client.delete(f"/api/v1/rules/{rule_id}", headers=pa_headers).status_code == 200
		assert test_client.delete(f"/api/v1/datasets/{ds1_dataset_id}", headers=pa_headers).status_code == 200


def test_list_endpoints_support_cursor_pagination_and_return_owner(server_settings, monkeypatch):
	"""M2 (ISS-031 + owner): 8 GET list endpoints return CursorPage {items, nextCursor} and 7 resource DTOs include owner."""
	import io
	from uuid import UUID
	from fastapi.testclient import TestClient
	from usfds_core.domain.entities.detection import DetectionJob
	from usfds_core.domain.entities.enums import ModelVersionStatus, TrainingRunStatus
	from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
	from usfds_infra.database.repos.detection import SqliteDetectionJobRepository
	from usfds_infra.database.repos.model import (
		SqliteModelRepository,
		SqliteModelVersionRepository,
		SqliteTrainingRunRepository,
	)
	from usfds_server import dependencies
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_token = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"}).json()["data"]["access_token"]
		admin_headers = {"Authorization": f"Bearer {admin_token}"}
		roles = test_client.get("/api/v1/rbac/roles", headers=admin_headers).json()["data"]
		ds_role = next(r for r in roles if r["name"] == "data_scientist")

		proj_res = test_client.post(
			"/api/v1/projects",
			json={"project_name": "Pagination Owner Project"},
			headers=admin_headers,
		)
		assert proj_res.status_code == 201, proj_res.text
		proj_data = proj_res.json()["data"]
		proj_id = proj_data["project_id"]
		assert proj_data["owner"]["username"] == "admin"

		u1_res = test_client.post(
			f"/api/v1/projects/{proj_id}/members",
			json={
				"username": "owner_u1",
				"password": "OwnerPass123!",
				"full_name": "Owner One",
				"role_id": ds_role["role_id"],
			},
			headers=admin_headers,
		)
		assert u1_res.status_code == 201, u1_res.text
		u1_id = u1_res.json()["data"]["user_id"]
		u1_token = test_client.post("/api/v1/auth/login", json={"username": "owner_u1", "password": "OwnerPass123!"}).json()["data"]["access_token"]
		u1_headers = {"Authorization": f"Bearer {u1_token}"}

		# Create 3 datasets owned by u1 for pagination testing
		from pathlib import Path
		ds_ids = []
		for idx in range(3):
			csv_path = Path(server_settings.storage_dir) / f"page_ds_{idx}.csv"
			csv_path.parent.mkdir(parents=True, exist_ok=True)
			csv_path.write_text(f"event_id,timestamp,amount,user_id,label\ne{idx},2026-01-01T00:00:0{idx}Z,10,c1,0\n")
			res = test_client.post(
				"/api/v1/datasets/import",
				json={"project_id": proj_id, "dataset_name": f"ds_page_{idx}", "file_path": str(csv_path)},
				headers=u1_headers,
			)
			assert res.status_code == 201, res.text
			ds_ids.append(res.json()["data"]["dataset"]["dataset_id"])
			assert res.json()["data"]["dataset"]["owner"] == {
				"user_id": u1_id,
				"username": "owner_u1",
				"full_name": "Owner One",
			}

		# Create a rule owned by u1 (with 1 version)
		rule_res = test_client.post(
			"/api/v1/rules",
			json={
				"project_id": proj_id,
				"rule_code": "R_PAGE_1",
				"name": "Page Rule",
				"condition": {">": [{"var": "amount"}, 100]},
				"action": "REVIEW",
				"status": "DRAFT",
			},
			headers=u1_headers,
		)
		assert rule_res.status_code == 201, rule_res.text
		rule_id = rule_res.json()["data"]["rule_id"]
		assert rule_res.json()["data"]["owner"]["username"] == "owner_u1"

		# Seed custom model, training run, model version, detection job owned by u1
		u1_uuid = UUID(u1_id)
		proj_uuid = UUID(proj_id)
		custom_model_id = uuid4()
		run_id = uuid4()
		ver_id = uuid4()
		job_id = uuid4()
		with dependencies._session_factory() as session:
			SqliteModelRepository(session).save(
				Model(
					model_id=custom_model_id,
					project_id=proj_uuid,
					user_id=u1_uuid,
					model_name="custom_page_model",
					execution_type="CUSTOM",
				)
			)
			SqliteTrainingRunRepository(session).save(
				TrainingRun(
					run_id=run_id,
					project_id=proj_uuid,
					user_id=u1_uuid,
					model_id=custom_model_id,
					run_name="page_run",
					status=TrainingRunStatus.COMPLETED,
				)
			)
			SqliteModelVersionRepository(session).save(
				ModelVersion(
					version_id=ver_id,
					model_id=custom_model_id,
					project_id=proj_uuid,
					user_id=u1_uuid,
					run_id=run_id,
					semver="1.0.0",
					artifact_uri="models/1.0.0.pkl",
					status=ModelVersionStatus.APPROVED,
				)
			)
			SqliteDetectionJobRepository(session).save(
				DetectionJob(
					job_id=job_id,
					project_id=proj_uuid,
					user_id=u1_uuid,
					job_name="page_job",
					input_path="datasets/raw.csv",
				)
			)
			session.commit()

		# Cursor pagination on /datasets?limit=2 -> page 1 (2 items, nextCursor != None), page 2 (1 item, nextCursor == None)
		page1 = test_client.get(
			"/api/v1/datasets",
			params={"project_id": proj_id, "limit": 2},
			headers=u1_headers,
		)
		assert page1.status_code == 200, page1.text
		p1_data = page1.json()["data"]
		assert len(p1_data["items"]) == 2
		assert p1_data["nextCursor"] is not None
		assert all(item["owner"]["username"] == "owner_u1" for item in p1_data["items"])

		page2 = test_client.get(
			"/api/v1/datasets",
			params={"project_id": proj_id, "limit": 2, "cursor": p1_data["nextCursor"]},
			headers=u1_headers,
		)
		assert page2.status_code == 200, page2.text
		p2_data = page2.json()["data"]
		assert len(p2_data["items"]) == 1
		assert p2_data["nextCursor"] is None
		seen_ids = {i["dataset_id"] for i in p1_data["items"]} | {i["dataset_id"] for i in p2_data["items"]}
		assert seen_ids == set(ds_ids)

		# Malformed cursor returns 400
		bad_cursor = test_client.get(
			"/api/v1/datasets",
			params={"project_id": proj_id, "cursor": "not-a-valid-cursor!"},
			headers=u1_headers,
		)
		assert bad_cursor.status_code == 400

		# Verify CursorPage shape + owner on remaining list endpoints & detail endpoints
		projects_list = test_client.get("/api/v1/projects", headers=u1_headers).json()["data"]
		assert "items" in projects_list and "nextCursor" in projects_list
		proj_item = next(p for p in projects_list["items"] if p["project_id"] == proj_id)
		assert proj_item["owner"]["username"] == "admin"

		models_list = test_client.get("/api/v1/training/models", params={"project_id": proj_id}, headers=u1_headers).json()["data"]
		assert "items" in models_list and "nextCursor" in models_list
		builtin_m = next(m for m in models_list["items"] if m["execution_type"] == "BUILTIN")
		custom_m = next(m for m in models_list["items"] if m["model_id"] == str(custom_model_id))
		assert builtin_m["user_id"] is None and builtin_m["owner"] is None
		assert custom_m["owner"] == {"user_id": u1_id, "username": "owner_u1", "full_name": "Owner One"}

		versions_list = test_client.get(
			f"/api/v1/training/models/{custom_model_id}/versions",
			params={"project_id": proj_id},
			headers=u1_headers,
		).json()["data"]
		assert len(versions_list["items"]) == 1
		assert versions_list["items"][0]["owner"]["username"] == "owner_u1"

		runs_list = test_client.get("/api/v1/training/runs", params={"project_id": proj_id}, headers=u1_headers).json()["data"]
		assert len(runs_list["items"]) == 1
		assert runs_list["items"][0]["owner"]["username"] == "owner_u1"

		rules_list = test_client.get("/api/v1/rules", params={"project_id": proj_id}, headers=u1_headers).json()["data"]
		assert len(rules_list["items"]) == 1
		assert rules_list["items"][0]["owner"]["username"] == "owner_u1"

		rule_vers_list = test_client.get(
			f"/api/v1/rules/{rule_id}/versions",
			params={"project_id": proj_id},
			headers=u1_headers,
		).json()["data"]
		assert "items" in rule_vers_list and "nextCursor" in rule_vers_list and len(rule_vers_list["items"]) == 1

		jobs_list = test_client.get("/api/v1/detection/jobs", params={"project_id": proj_id}, headers=u1_headers).json()["data"]
		assert len(jobs_list["items"]) == 1
		assert jobs_list["items"][0]["owner"]["username"] == "owner_u1"

		# Detail endpoints also include owner
		assert test_client.get(f"/api/v1/projects/{proj_id}", headers=u1_headers).json()["data"]["owner"]["username"] == "admin"
		assert test_client.get(f"/api/v1/datasets/{ds_ids[0]}", params={"project_id": proj_id}, headers=u1_headers).json()["data"]["dataset"]["owner"]["username"] == "owner_u1"
		assert test_client.get(f"/api/v1/training/models/{custom_model_id}", params={"project_id": proj_id}, headers=u1_headers).json()["data"]["owner"]["username"] == "owner_u1"
		assert test_client.get(f"/api/v1/training/versions/{ver_id}", params={"project_id": proj_id}, headers=u1_headers).json()["data"]["owner"]["username"] == "owner_u1"
		assert test_client.get(f"/api/v1/training/runs/{run_id}", params={"project_id": proj_id}, headers=u1_headers).json()["data"]["owner"]["username"] == "owner_u1"
		assert test_client.get(f"/api/v1/rules/{rule_id}", params={"project_id": proj_id}, headers=u1_headers).json()["data"]["owner"]["username"] == "owner_u1"
		assert test_client.get(f"/api/v1/detection/jobs/{job_id}", params={"project_id": proj_id}, headers=u1_headers).json()["data"]["owner"]["username"] == "owner_u1"
