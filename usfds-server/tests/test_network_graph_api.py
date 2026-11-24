"""M2 acceptance tests for Network Graph read API, live Case/Blacklist overlay, and project isolation (ISS-041 / SUC-19)."""
from datetime import datetime, timezone
import json
from uuid import uuid4

import pandas as pd
from fastapi.testclient import TestClient

from usfds_core.domain.entities.case import BlacklistEntityType, Case, EntityBlacklist
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus, ProjectStatus, RuleAction
from usfds_core.domain.entities.system import Project
from usfds_infra.database import SqliteDetectionJobRepository, SqliteProjectRepository, SqlUserRepository
from usfds_infra.database.case_repositories import SqliteBlacklistRepository, SqliteCaseRepository
from usfds_server.api import app
from usfds_server.dependencies import get_storage


def _seed_network_project(session, storage, actor_id, project_id, name: str = "Net Test", status: ProjectStatus = ProjectStatus.ACTIVE):
	SqliteProjectRepository(session).save(
		Project(project_id=project_id, user_id=actor_id, project_name=name, status=status)
	)
	job_id = uuid4()
	df = pd.DataFrame([
		{
			"event_id": "EV-1",
			"user_id": "U-BLK",
			"timestamp": "2026-11-10T10:00:00Z",
			"amount": 500.0,
			"model_score": 0.91,
			"rule_action": "REJECT",
			"final_action": "REJECT",
			"triggered_rules": json.dumps(["R1"]),
			"device_id": "DEV-SHARED",
			"ip_address": "10.1.1.1",
			"merchant_id": "M-1",
			"merchant_category": "CRYPTO",
		},
		{
			"event_id": "EV-2",
			"user_id": "U-OPEN",
			"timestamp": "2026-11-10T11:00:00Z",
			"amount": 320.0,
			"model_score": 0.78,
			"rule_action": "REVIEW",
			"final_action": "REVIEW",
			"triggered_rules": json.dumps(["R2"]),
			"device_id": "DEV-SHARED",
			"ip_address": "10.1.1.2",
			"merchant_id": "M-1",
			"merchant_category": "CRYPTO",
		},
		{
			"event_id": "EV-3",
			"user_id": "U-CLEAN",
			"timestamp": "2026-11-10T12:00:00Z",
			"amount": 90.0,
			"model_score": 0.12,
			"rule_action": "ALLOW",
			"final_action": "ALLOW",
			"triggered_rules": json.dumps([]),
			"device_id": "DEV-SHARED",
			"ip_address": "10.1.1.3",
			"merchant_id": "M-2",
			"merchant_category": "GROCERY",
		},
	])
	output_path = storage.save_bytes(
		f"datasets/{project_id}/inferences/{job_id}/predictions.parquet",
		df.to_parquet(index=False),
	)
	SqliteDetectionJobRepository(session).save(
		DetectionJob(
			job_id=job_id,
			project_id=project_id,
			user_id=actor_id,
			job_name="Network Scan",
			output_path=output_path,
			score_threshold=0.5,
			status=DetectionJobStatus.COMPLETED,
			created_at=datetime(2026, 11, 10, 13, 0, tzinfo=timezone.utc),
		)
	)
	return job_id


def test_network_api_hubs_subgraph_expand_and_edge_transactions_with_live_overlay(client, server_session_factory):
	"""ISS-041 / SUC-19: /api/v1/network/* overlays live Case/Blacklist status even on cache hits and binds case_id on edge transactions."""
	project_id = uuid4()
	with server_session_factory() as session:
		actor_id = SqlUserRepository(session).get_by_username("admin").user_id
		job_id = _seed_network_project(session, get_storage(), actor_id, project_id)
		# Seed 1 blacklisted user and 1 OPEN case
		SqliteBlacklistRepository(session).save(
			EntityBlacklist(
				project_id=project_id,
				entity_type=BlacklistEntityType.USER_ID,
				entity_value="U-BLK",
				reason="Known fraudster account",
				created_by="admin",
			)
		)
		open_case = SqliteCaseRepository(session).save(
			Case(
				project_id=project_id,
				event_id="EV-2",
				user_id="U-OPEN",
				tx_timestamp=datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc),
				amount=320.0,
				final_action=RuleAction.REVIEW,
				dataset_artifact_id=None,
				detection_job_id=job_id,
				model_score=0.78,
			)
		)
		open_case_id = str(open_case.case_id)
		session.commit()

	params = {"project_id": str(project_id)}

	hubs_res = client.get("/api/v1/network/hubs", params={**params, "days": 90})
	assert hubs_res.status_code == 200, hubs_res.text
	hubs_data = hubs_res.json()["data"]
	assert hubs_data["available"] is True
	assert any(h["id"] == "DEVICE_ID:DEV-SHARED" and h["pattern_type"] == "DEVICE_IP_CARD_HUB" for h in hubs_data["hubs"])

	# 1-hop subgraph from U-OPEN -> DEV-SHARED, IP 10.1.1.2, M-1
	sub_res = client.get(
		"/api/v1/network/subgraph",
		params={**params, "seed_type": "USER_ID", "seed_value": "U-OPEN", "hops": 1, "days": 90},
	)
	assert sub_res.status_code == 200, sub_res.text
	sub = sub_res.json()["data"]
	nodes_by_id = {n["id"]: n for n in sub["nodes"]}
	assert nodes_by_id["USER_ID:U-OPEN"]["risk_status"] == "WARNING"
	assert open_case_id in nodes_by_id["USER_ID:U-OPEN"]["case_ids"]

	# Expand DEV-SHARED -> adds U-BLK (CRITICAL) & U-CLEAN (NORMAL)
	exp_res = client.post(
		"/api/v1/network/expand",
		json={
			"project_id": str(project_id),
			"entity_type": "DEVICE_ID",
			"entity_value": "DEV-SHARED",
			"existing_node_ids": [n["id"] for n in sub["nodes"]],
			"days": 90,
		},
	)
	assert exp_res.status_code == 200, exp_res.text
	added_by_id = {n["id"]: n for n in exp_res.json()["data"]["added_nodes"]}
	assert added_by_id["USER_ID:U-BLK"]["risk_status"] == "CRITICAL"
	assert added_by_id["USER_ID:U-BLK"]["is_blacklisted"] is True
	assert added_by_id["USER_ID:U-CLEAN"]["risk_status"] == "NORMAL"

	# Add U-CLEAN to blacklist AFTER graph is cached -> next subgraph call must reflect live CRITICAL status
	with server_session_factory() as session:
		SqliteBlacklistRepository(session).save(
			EntityBlacklist(
				project_id=project_id,
				entity_type=BlacklistEntityType.USER_ID,
				entity_value="U-CLEAN",
				reason="Blocked after initial graph build",
				created_by="admin",
			)
		)
		session.commit()

	sub2_res = client.get(
		"/api/v1/network/subgraph",
		params={**params, "seed_type": "DEVICE_ID", "seed_value": "DEV-SHARED", "hops": 1, "days": 90},
	)
	assert sub2_res.status_code == 200
	nodes2 = {n["id"]: n for n in sub2_res.json()["data"]["nodes"]}
	assert nodes2["USER_ID:U-CLEAN"]["risk_status"] == "CRITICAL"
	assert nodes2["USER_ID:U-CLEAN"]["is_blacklisted"] is True

	# Edge transactions binds existing case_id
	edge_res = client.get(
		"/api/v1/network/edge-transactions",
		params={**params, "user_id": "U-OPEN", "entity_type": "DEVICE_ID", "entity_value": "DEV-SHARED", "days": 90},
	)
	assert edge_res.status_code == 200, edge_res.text
	txs = edge_res.json()["data"]["transactions"]
	assert len(txs) == 1
	assert txs[0]["event_id"] == "EV-2"
	assert txs[0]["case_id"] == open_case_id
	assert txs[0]["job_id"] == str(job_id)


def test_network_and_bulk_api_project_isolation_and_archived_guard(server_settings, monkeypatch):
	"""ISS-041: Cross-project reads on /api/v1/network/* are forbidden (403/404); ARCHIVED project allows graph reads (200)."""
	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_token = test_client.post(
			"/api/v1/auth/login",
			json={"username": "admin", "password": "AdminPass123!"},
		).json()["data"]["access_token"]
		admin_headers = {"Authorization": f"Bearer {admin_token}"}

		p_a = test_client.post("/api/v1/projects", json={"project_name": "Net Proj A"}, headers=admin_headers).json()["data"]["project_id"]
		p_b = test_client.post("/api/v1/projects", json={"project_name": "Net Proj B"}, headers=admin_headers).json()["data"]["project_id"]

		from usfds_server import dependencies
		with dependencies._session_factory() as session:
			admin_id = SqlUserRepository(session).get_by_username("admin").user_id
			_seed_network_project(session, get_storage(), admin_id, p_a if not isinstance(p_a, str) else uuid4() if False else __import__("uuid").UUID(p_a))
			# Create archived project
			p_arch_id = uuid4()
			_seed_network_project(session, get_storage(), admin_id, p_arch_id, name="Archived Net", status=ProjectStatus.ARCHIVED)
			session.commit()

		# Create user with fraud_analyst role ONLY on project A
		u_res = test_client.post(
			"/api/v1/users",
			json={"username": "net_analyst", "email": "net_analyst@usfds.local", "password": "UserPass123!"},
			headers=admin_headers,
		)
		assert u_res.status_code == 201
		user_id = u_res.json()["data"]["user_id"]
		roles = test_client.get("/api/v1/rbac/roles", headers=admin_headers).json()["data"]
		analyst_role = next(r for r in roles if r["name"] == "fraud_analyst")
		test_client.post(
			f"/api/v1/projects/{p_a}/members/{user_id}/roles",
			json={"role_id": analyst_role["role_id"]},
			headers=admin_headers,
		)

		user_token = test_client.post(
			"/api/v1/auth/login",
			json={"username": "net_analyst", "password": "UserPass123!"},
		).json()["data"]["access_token"]
		user_headers = {"Authorization": f"Bearer {user_token}"}

		# Allowed on Project A
		assert test_client.get("/api/v1/network/hubs", params={"project_id": p_a}, headers=user_headers).status_code == 200
		# Forbidden on Project B
		assert test_client.get("/api/v1/network/hubs", params={"project_id": p_b}, headers=user_headers).status_code in (403, 404)
		assert test_client.get(
			"/api/v1/network/subgraph",
			params={"project_id": p_b, "seed_type": "USER_ID", "seed_value": "U-BLK"},
			headers=user_headers,
		).status_code in (403, 404)
		assert test_client.post(
			"/api/v1/network/expand",
			json={"project_id": p_b, "entity_type": "DEVICE_ID", "entity_value": "DEV-SHARED", "existing_node_ids": []},
			headers=user_headers,
		).status_code in (403, 404)

		# Archived project still allows read-only graph queries as admin
		arch_res = test_client.get("/api/v1/network/hubs", params={"project_id": str(p_arch_id)}, headers=admin_headers)
		assert arch_res.status_code == 200, arch_res.text
		assert arch_res.json()["data"]["available"] is True
