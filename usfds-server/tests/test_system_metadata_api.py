"""M2 acceptance tests for System Metadata Management REST API & dynamic Schema Mapping (ISS-007)."""
import io
from pathlib import Path
from uuid import UUID

import pandas as pd


def _create_user_and_login(test_client, admin_headers, username: str, password: str, system_roles=None):
	create_res = test_client.post(
		"/api/v1/users",
		json={
			"username": username,
			"password": password,
			"full_name": f"User {username}",
			"email": f"{username}@usfds.local",
			"system_roles": system_roles or ["system_member"],
		},
		headers=admin_headers,
	)
	assert create_res.status_code == 201, create_res.text
	user_id = create_res.json()["data"]["user_id"]

	login_res = test_client.post(
		"/api/v1/auth/login",
		json={"username": username, "password": password},
	)
	assert login_res.status_code == 200, login_res.text
	token = login_res.json()["data"]["access_token"]
	return user_id, {"Authorization": f"Bearer {token}"}


def test_system_metadata_crud_api_and_rbac_enforcement(server_settings, monkeypatch):
	"""ISS-007: Authenticated users can GET system metadata, only system_admin can POST/PATCH/DELETE, CORE columns cannot be deleted."""
	from fastapi.testclient import TestClient
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_login = test_client.post(
			"/api/v1/auth/login",
			json={"username": "admin", "password": "AdminPass123!"},
		)
		assert admin_login.status_code == 200
		admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['access_token']}"}

		_, ds_headers = _create_user_and_login(test_client, admin_headers, "ds_user", "DsPass123!")

		# 1. Seeded 5 CORE + 2 DOMAIN columns are readable by normal authenticated user
		list_res = test_client.get("/api/v1/system-metadata/columns", headers=ds_headers)
		assert list_res.status_code == 200, list_res.text
		cols = list_res.json()["data"]
		col_keys = {c["column_key"] for c in cols}
		assert {"event_id", "timestamp", "amount", "user_id", "label", "merchant", "category"}.issubset(col_keys)

		# 2. Normal user (data_scientist / system_member) cannot POST new metadata -> 403
		forbidden_res = test_client.post(
			"/api/v1/system-metadata/columns",
			json={
				"column_key": "terminal_id",
				"display_name": "Mã thiết bị đầu cuối",
				"logical_type": "STRING",
				"is_required": True,
				"ml_role": "IDENTIFIER",
				"aliases": ["dev_hash"],
			},
			headers=ds_headers,
		)
		assert forbidden_res.status_code == 403

		# 3. system_admin creates a DOMAIN column -> 201
		create_res = test_client.post(
			"/api/v1/system-metadata/columns",
			json={
				"column_key": "terminal_id",
				"display_name": "Mã thiết bị đầu cuối",
				"logical_type": "STRING",
				"is_required": True,
				"ml_role": "IDENTIFIER",
				"aliases": ["dev_hash"],
				"description": "Định danh thiết bị đầu cuối",
			},
			headers=admin_headers,
		)
		assert create_res.status_code == 201, create_res.text
		created = create_res.json()["data"]
		assert created["column_key"] == "terminal_id"
		assert created["category"] == "DOMAIN"
		assert "terminal_id" in created["aliases"]
		assert "dev_hash" in created["aliases"]

		# 4. system_admin updates the DOMAIN column -> 200
		patch_res = test_client.patch(
			f"/api/v1/system-metadata/columns/{created['metadata_id']}",
			json={
				"display_name": "Thiết bị giao dịch",
				"aliases": ["dev_hash", "device_fingerprint"],
			},
			headers=admin_headers,
		)
		assert patch_res.status_code == 200, patch_res.text
		patched = patch_res.json()["data"]
		assert patched["display_name"] == "Thiết bị giao dịch"
		assert "device_fingerprint" in patched["aliases"]

		# 5. system_admin deletes the DOMAIN column -> 200
		del_res = test_client.delete(
			f"/api/v1/system-metadata/columns/{created['metadata_id']}",
			headers=admin_headers,
		)
		assert del_res.status_code == 200, del_res.text

		# 6. system_admin trying to delete a CORE column -> 400 Bad Request
		core_event = next(c for c in cols if c["column_key"] == "event_id")
		del_core_res = test_client.delete(
			f"/api/v1/system-metadata/columns/{core_event['metadata_id']}",
			headers=admin_headers,
		)
		assert del_core_res.status_code == 400


def test_schema_mapping_endpoint_enforces_required_domain_column(client, server_settings):
	"""ISS-007: POST /api/v1/datasets/{id}/schema-mapping enforces dynamically created required DOMAIN columns."""
	# 1. Create required DOMAIN column 'acquisition_channel' via API
	create_col_res = client.post(
		"/api/v1/system-metadata/columns",
		json={
			"column_key": "acquisition_channel",
			"display_name": "Kênh thu thập giao dịch",
			"logical_type": "STRING",
			"is_required": True,
			"ml_role": "FEATURE",
			"aliases": ["tx_channel"],
		},
	)
	assert create_col_res.status_code == 201, create_col_res.text

	# 2. Create project & upload raw dataset containing tx_channel
	proj_res = client.post(
		"/api/v1/projects",
		json={"project_name": "metadata_mapping_proj", "description": "test"},
	)
	assert proj_res.status_code == 201, proj_res.text
	project_id = proj_res.json()["data"]["project_id"]

	csv_path = Path(server_settings.storage_dir) / "sample_channel.csv"
	csv_path.parent.mkdir(parents=True, exist_ok=True)
	df = pd.DataFrame(
		{
			"tx_id": ["T1", "T2", "T3", "T4"],
			"tx_time": [
				"2026-01-01 01:00:00",
				"2026-01-01 02:00:00",
				"2026-01-01 03:00:00",
				"2026-01-01 04:00:00",
			],
			"amt": [10.0, 25.0, 50.0, 100.0],
			"acct": ["U1", "U2", "U3", "U4"],
			"is_fraud": [0, 0, 1, 0],
			"tx_channel": ["web", "mobile", "pos", "web"],
		}
	)
	df.to_csv(csv_path, index=False)

	import_res = client.post(
		"/api/v1/datasets/import",
		json={
			"project_id": project_id,
			"dataset_name": "channel_ds",
			"file_path": str(csv_path),
		},
	)
	assert import_res.status_code == 201, import_res.text
	dataset_id = import_res.json()["data"]["dataset"]["dataset_id"]

	# 3. Call schema-mapping WITHOUT 'acquisition_channel' -> 400 Bad Request
	bad_map_res = client.post(
		f"/api/v1/datasets/{dataset_id}/schema-mapping",
		json={
			"event_id_column": "tx_id",
			"time_column": "tx_time",
			"amount_column": "amt",
			"user_id_column": "acct",
			"target_column": "is_fraud",
			"optional_columns": {},
			"time_format": "auto",
		},
	)
	assert bad_map_res.status_code == 400
	assert "acquisition_channel" in bad_map_res.text

	# 4. Call schema-mapping WITH 'acquisition_channel' -> 201 Created and 'acquisition_channel' in schema_snapshot
	ok_map_res = client.post(
		f"/api/v1/datasets/{dataset_id}/schema-mapping",
		json={
			"event_id_column": "tx_id",
			"time_column": "tx_time",
			"amount_column": "amt",
			"user_id_column": "acct",
			"target_column": "is_fraud",
			"optional_columns": {"tx_channel": "acquisition_channel"},
			"time_format": "auto",
		},
	)
	assert ok_map_res.status_code == 201, ok_map_res.text
	art = ok_map_res.json()["data"]
	assert "acquisition_channel" in art["schema_snapshot"]
	assert art["pipeline_stage"] == "MAPPED"
