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
			SqliteDatasetRepository(session).save(
				Dataset(dataset_id=ds_id, project_id=project_uuid, user_id=uuid4(), dataset_name="ds_test")
			)
			SqliteRuleRepository(session).save(
				Rule(
					rule_id=rule_id,
					project_id=project_uuid,
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
			SqliteDatasetRepository(session).save(
				Dataset(dataset_id=ds_b, project_id=proj_b_uuid, user_id=uuid4(), dataset_name="ds_b")
			)
			SqliteDatasetArtifactRepository(session).save(
				DatasetArtifact(artifact_id=art_b, dataset_id=ds_b, pipeline_stage=PipelineStage.RAW, storage_path="datasets/b/raw.csv")
			)
			SqliteModelRepository(session).save(
				Model(model_id=model_b, project_id=proj_b_uuid, user_id=uuid4(), model_name="custom_b", execution_type=ExecutionType.SCRIPT)
			)
			SqliteTrainingRunRepository(session).save(
				TrainingRun(run_id=run_b, project_id=proj_b_uuid, model_id=model_b, version_id=ver_b, run_name="run_b", status=TrainingRunStatus.COMPLETED)
			)
			SqliteModelVersionRepository(session).save(
				ModelVersion(version_id=ver_b, model_id=model_b, project_id=proj_b_uuid, run_id=run_b, semver="v1", artifact_uri="models/b/v1.zip", status=ModelVersionStatus.CANDIDATE)
			)
			SqliteTrainingRunRepository(session).save(
				TrainingRun(run_id=run_null, project_id=None, model_id=rf_id, version_id=ver_null, run_name="run_null", status=TrainingRunStatus.COMPLETED)
			)
			SqliteModelVersionRepository(session).save(
				ModelVersion(version_id=ver_null, model_id=rf_id, project_id=None, run_id=run_null, semver="v1", artifact_uri="models/null/v1.joblib", status=ModelVersionStatus.CANDIDATE)
			)
			SqliteDetectionJobRepository(session).save(
				DetectionJob(job_id=job_b, project_id=proj_b_uuid, job_name="job_b", input_path="datasets/b/raw.csv")
			)
			r_ver_id = uuid4()
			SqliteRuleRepository(session).save(
				Rule(rule_id=rule_b, project_id=proj_b_uuid, rule_code="R-B1", name="Rule B", description="", status=RuleStatus.DRAFT, current_version_id=r_ver_id)
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
				ds_repo = SqliteDatasetRepository(session)
				art_repo = SqliteDatasetArtifactRepository(session)
				rule_repo = SqliteRuleRepository(session)
				rv_repo = SqliteRuleVersionRepository(session)
				job_repo = SqliteDetectionJobRepository(session)

				ds_repo.save(Dataset(dataset_id=ds_a, project_id=UUID(proj_a), user_id=uuid4(), dataset_name="ds_a"))
				art_repo.save(DatasetArtifact(artifact_id=art_a, dataset_id=ds_a, pipeline_stage=PipelineStage.RAW, storage_path=f"datasets/{ds_a}/raw.csv", validation_status=ValidationStatus.PASSED))
				ds_repo.save(Dataset(dataset_id=ds_b, project_id=UUID(proj_b), user_id=uuid4(), dataset_name="ds_b"))
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
				job_repo.save(DetectionJob(job_id=job_b, project_id=UUID(proj_b), job_name="job_b", input_path="datasets/b/raw.csv"))

				rule_repo.save(Rule(rule_id=rule_a, project_id=UUID(proj_a), rule_code="RA", name="Rule A", description="", status=RuleStatus.DRAFT, current_version_id=rv_a))
				rv_repo.save(RuleVersion(rule_version_id=rv_a, rule_id=rule_a, version_number=1, condition={"==": [1, 1]}, action=RuleAction.REVIEW))
				rule_repo.save(Rule(rule_id=rule_b, project_id=UUID(proj_b), rule_code="RB", name="Rule B", description="", status=RuleStatus.DRAFT, current_version_id=rv_b))
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
