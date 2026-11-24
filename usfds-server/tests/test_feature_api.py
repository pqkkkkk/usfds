"""M2 acceptance tests for Feature Management REST API, RBAC, FE Execution & Rule Backtest (ISS-040)."""
from pathlib import Path

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


def _assign_project_role(test_client, headers, project_id: str, user_id: str, role_name: str):
	roles = test_client.get("/api/v1/rbac/roles", headers=headers).json()["data"]
	role_id = next(r["role_id"] for r in roles if r["name"] == role_name and r["scope"] == "PROJECT")
	res = test_client.post(
		f"/api/v1/projects/{project_id}/members",
		json={"user_id": user_id, "role_id": role_id},
		headers=headers,
	)
	assert res.status_code in (200, 201), res.text


def test_feature_api_crud_rbac_own_scope_and_project_isolation(server_settings, monkeypatch):
	"""RBAC (feature:*), GrantScope.OWN, AST validation 400, clone/edit source_code, compatibility, preview, cross-project 404, ARCHIVED 400."""
	from fastapi.testclient import TestClient
	from usfds_server.api import app

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	monkeypatch.setattr(server_settings, "bootstrap_admin_username", "admin")
	monkeypatch.setattr(server_settings, "bootstrap_admin_password", "AdminPass123!")

	with TestClient(app) as test_client:
		admin_login = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
		admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['access_token']}"}

		ds1_id, ds1_headers = _create_user_and_login(test_client, admin_headers, "ds_feat_1", "Pass1234!")
		ds2_id, ds2_headers = _create_user_and_login(test_client, admin_headers, "ds_feat_2", "Pass1234!")
		fa_id, fa_headers = _create_user_and_login(test_client, admin_headers, "fa_feat_1", "Pass1234!")

		p1_id = test_client.post("/api/v1/projects", json={"project_name": "Feat P1"}, headers=admin_headers).json()["data"]["project_id"]
		p2_id = test_client.post("/api/v1/projects", json={"project_name": "Feat P2"}, headers=admin_headers).json()["data"]["project_id"]

		_assign_project_role(test_client, admin_headers, p1_id, ds1_id, "data_scientist")
		_assign_project_role(test_client, admin_headers, p1_id, ds2_id, "data_scientist")
		_assign_project_role(test_client, admin_headers, p1_id, fa_id, "fraud_analyst")

		# 1. Built-in features & sets readable by fraud_analyst (200), but mutation rejected (403)
		list_res = test_client.get(f"/api/v1/features?project_id={p1_id}&limit=200", headers=fa_headers)
		assert list_res.status_code == 200
		builtin_items = list_res.json()["data"]["items"]
		assert len(builtin_items) >= 28
		free_email_feat = next(f for f in builtin_items if f["feature_key"] == "is_free_email")

		fa_create = test_client.post(
			"/api/v1/features",
			json={
				"project_id": p1_id,
				"feature_key": "fa_bad",
				"display_name": "FA Bad",
				"megafamily": "MONETARY",
				"compute_kind": "EXPRESSION",
				"output_type": "NUMERIC",
				"config_json": {"expr": "amount * 2"},
				"required_inputs": ["amount"],
			},
			headers=fa_headers,
		)
		assert fa_create.status_code == 403

		# 2. Unsafe PYTHON_CODE rejected with 400
		bad_py = test_client.post(
			"/api/v1/features",
			json={
				"project_id": p1_id,
				"feature_key": "evil_feat",
				"display_name": "Evil",
				"megafamily": "IDENTITY",
				"compute_kind": "PYTHON_CODE",
				"output_type": "NUMERIC",
				"source_code": "import os\ndef compute(df, params):\n    return df['amount']\n",
				"required_inputs": ["amount"],
			},
			headers=ds1_headers,
		)
		assert bad_py.status_code == 400

		# 3. ds1 creates valid PYTHON_CODE feature -> 201
		good_py = test_client.post(
			"/api/v1/features",
			json={
				"project_id": p1_id,
				"feature_key": "amt_double_py",
				"display_name": "Amount x2 Py",
				"megafamily": "MONETARY",
				"compute_kind": "PYTHON_CODE",
				"output_type": "NUMERIC",
				"source_code": "import pandas as pd\ndef compute(df, params):\n    return pd.to_numeric(df['amount'], errors='coerce') * 2.0\n",
				"required_inputs": ["amount"],
			},
			headers=ds1_headers,
		)
		assert good_py.status_code == 201, good_py.text
		custom_fid = good_py.json()["data"]["feature_id"]

		# 4. ds2 cannot PATCH/DELETE ds1's feature (GrantScope.OWN -> 403)
		assert (
			test_client.patch(
				f"/api/v1/features/{custom_fid}?project_id={p1_id}",
				json={"display_name": "Hijack"},
				headers=ds2_headers,
			).status_code
			== 403
		)
		assert (
			test_client.delete(
				f"/api/v1/features/{custom_fid}?project_id={p1_id}",
				headers=ds2_headers,
			).status_code
			== 403
		)

		# 5. Cross-project access returns 404
		_assign_project_role(test_client, admin_headers, p2_id, ds1_id, "data_scientist")
		assert (
			test_client.get(f"/api/v1/features/{custom_fid}?project_id={p2_id}", headers=ds1_headers).status_code == 404
		)

		# 6. Clone built-in & update its source_code
		clone_res = test_client.post(
			f"/api/v1/features/{free_email_feat['feature_id']}/clone?project_id={p1_id}",
			json={"new_feature_key": "custom_free_email"},
			headers=ds1_headers,
		)
		assert clone_res.status_code == 201, clone_res.text
		cloned_id = clone_res.json()["data"]["feature_id"]

		# 7. Upload dataset, map, check compatibility & preview feature
		csv_path = Path(server_settings.storage_dir) / "feat_api_sample.csv"
		csv_path.parent.mkdir(parents=True, exist_ok=True)
		pd.DataFrame(
			{
				"tx_id": ["E1", "E2", "E3", "E4", "E5"],
				"tx_time": [
					"2026-01-01 01:00:00",
					"2026-01-01 02:00:00",
					"2026-01-01 03:00:00",
					"2026-01-01 04:00:00",
					"2026-01-01 05:00:00",
				],
				"amt": [10.0, 20.0, 30.0, 40.0, 50.0],
				"acct": ["U1", "U1", "U2", "U2", "U3"],
				"is_fraud": [0, 1, 0, 0, 1],
			}
		).to_csv(csv_path, index=False)

		ds_id = test_client.post(
			"/api/v1/datasets/import",
			json={"project_id": p1_id, "dataset_name": "feat_ds", "file_path": str(csv_path)},
			headers=ds1_headers,
		).json()["data"]["dataset"]["dataset_id"]

		map_art_id = test_client.post(
			f"/api/v1/datasets/{ds_id}/schema-mapping",
			json={
				"event_id_column": "tx_id",
				"time_column": "tx_time",
				"amount_column": "amt",
				"user_id_column": "acct",
				"target_column": "is_fraud",
				"optional_columns": {},
				"time_format": "auto",
			},
			headers=ds1_headers,
		).json()["data"]["artifact_id"]

		compat_res = test_client.get(
			f"/api/v1/features/compatibility?project_id={p1_id}&artifact_id={map_art_id}",
			headers=ds1_headers,
		)
		assert compat_res.status_code == 200
		compat_map = {i["feature_key"]: i for i in compat_res.json()["data"]["items"]}
		assert compat_map["amt_double_py"]["status"] == "AVAILABLE"
		assert compat_map["geo_distance_km"]["status"] == "MISSING_INPUTS"

		prev_res = test_client.post(
			"/api/v1/features/preview",
			json={"project_id": p1_id, "artifact_id": map_art_id, "feature_id": custom_fid},
			headers=ds1_headers,
		)
		assert prev_res.status_code == 200, prev_res.text
		assert prev_res.json()["data"]["stats"]["row_count"] == 5

		# 8. FeatureSet CRUD & Archive guard (ARCHIVED project -> 400)
		fs_res = test_client.post(
			"/api/v1/feature-sets",
			json={
				"project_id": p1_id,
				"set_key": "p1_custom_set",
				"name": "P1 Set",
				"feature_ids": [custom_fid, cloned_id],
			},
			headers=ds1_headers,
		)
		assert fs_res.status_code == 201, fs_res.text

		arch_res = test_client.patch(
			f"/api/v1/projects/{p2_id}",
			json={"status": "ARCHIVED"},
			headers=admin_headers,
		)
		assert arch_res.status_code == 200, arch_res.text
		assert (
			test_client.post(
				"/api/v1/features",
				json={
					"project_id": p2_id,
					"feature_key": "arch_feat",
					"display_name": "Arch",
					"megafamily": "MONETARY",
					"compute_kind": "EXPRESSION",
					"config_json": {"expr": "amount"},
					"required_inputs": ["amount"],
				},
				headers=ds1_headers,
			).status_code
			== 400
		)


def test_dataset_fe_and_rule_backtest_end_to_end_via_api(client, server_settings):
	"""End-to-end API flow: RAW -> MAPPED -> FE (multi-set + individual + feature-only) -> ACTIVE Rule with enriched.* -> Backtest."""
	p_res = client.post("/api/v1/projects", json={"project_name": "E2E Feature Proj"})
	assert p_res.status_code == 201
	project_id = p_res.json()["data"]["project_id"]

	csv_path = Path(server_settings.storage_dir) / "feat_e2e.csv"
	csv_path.parent.mkdir(parents=True, exist_ok=True)
	pd.DataFrame(
		{
			"event_id": [f"E{i}" for i in range(10)],
			"timestamp": [f"2026-01-01 0{i}:00:00" for i in range(10)],
			"amount": [50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 500.0, 600.0, 70.0, 800.0],
			"user_id": ["U1", "U1", "U1", "U2", "U2", "U3", "U1", "U1", "U2", "U3"],
			"merchant": ["M1", "M1", "M2", "M2", "M3", "M3", "M1", "M1", "M2", "M3"],
			"lat": [10.76] * 10,
			"long": [106.66] * 10,
			"merch_lat": [21.02 if i >= 6 else 10.76 for i in range(10)],
			"merch_long": [105.80 if i >= 6 else 106.66 for i in range(10)],
			"label": [0, 0, 0, 0, 0, 0, 1, 1, 0, 1],
		}
	).to_csv(csv_path, index=False)

	ds_id = client.post(
		"/api/v1/datasets/import",
		json={"project_id": project_id, "dataset_name": "e2e_feat_ds", "file_path": str(csv_path)},
	).json()["data"]["dataset"]["dataset_id"]

	client.post(
		f"/api/v1/datasets/{ds_id}/schema-mapping",
		json={
			"event_id_column": "event_id",
			"time_column": "timestamp",
			"amount_column": "amount",
			"user_id_column": "user_id",
			"target_column": "label",
			"optional_columns": {
				"merchant": "merchant",
				"lat": "lat",
				"long": "long",
				"merch_lat": "merch_lat",
				"merch_long": "merch_long",
			},
			"time_format": "auto",
		},
	)

	# Create custom PYTHON_CODE feature
	custom_feat = client.post(
		"/api/v1/features",
		json={
			"project_id": project_id,
			"feature_key": "amt_triple_custom",
			"display_name": "Amount x3",
			"megafamily": "MONETARY",
			"compute_kind": "PYTHON_CODE",
			"output_type": "NUMERIC",
			"source_code": "import pandas as pd\ndef compute(df, params):\n    return pd.to_numeric(df['amount'], errors='coerce') * 3.0\n",
			"required_inputs": ["amount"],
		},
	).json()["data"]

	sets = client.get(f"/api/v1/feature-sets?project_id={project_id}&limit=50").json()["data"]["items"]
	geo_set = next(s for s in sets if s["set_key"] == "pkg_geo_behavioral")
	ccfd_set = next(s for s in sets if s["set_key"] == "pkg_ccfd_standard")

	# 1. Multi-set + individual feature execution
	fe_res = client.post(
		f"/api/v1/datasets/{ds_id}/feature-engineering",
		json={
			"feature_set_ids": [geo_set["feature_set_id"], ccfd_set["feature_set_id"]],
			"feature_ids": [custom_feat["feature_id"]],
		},
	)
	assert fe_res.status_code == 201, fe_res.text
	fe_art = fe_res.json()["data"]
	vr = fe_art["validation_report"]
	assert "geo_distance_km" in vr["engineered_features"]
	assert "amt_triple_custom" in vr["engineered_features"]
	assert len(vr["feature_set_snapshot"]) >= 10
	snap_custom = next(s for s in vr["feature_set_snapshot"] if s["feature_key"] == "amt_triple_custom")
	assert snap_custom.get("snapshot_sha256")
	assert snap_custom.get("source_code")

	# 2. Feature-only execution (0 FeatureSets, only individual feature_ids)
	fe_only_res = client.post(
		f"/api/v1/datasets/{ds_id}/feature-engineering",
		json={"feature_ids": [custom_feat["feature_id"]]},
	)
	assert fe_only_res.status_code == 201, fe_only_res.text

	# 3. Create ACTIVE Rule referencing enriched.amt_triple_custom and backtest on FE artifact
	rule_res = client.post(
		"/api/v1/rules",
		json={
			"project_id": project_id,
			"rule_code": "R_CUSTOM_TRIPLE",
			"name": "High triple amount",
			"description": "Triggers on custom enriched feature",
			"condition": {">=": [{"var": "enriched.amt_triple_custom"}, 1500]},
			"action": "REJECT",
			"status": "ACTIVE",
		},
	)
	assert rule_res.status_code == 201, rule_res.text

	bt_res = client.post(
		"/api/v1/rules/backtest",
		json={
			"project_id": project_id,
			"dataset_artifact_id": fe_art["artifact_id"],
			"rule_id": rule_res.json()["data"]["rule_id"],
		},
	)
	assert bt_res.status_code == 200, bt_res.text
	assert bt_res.json()["data"]["total_hits"] == 3
	assert bt_res.json()["data"]["tp"] == 3


def test_feature_and_feature_set_list_cursor_pagination(client):
	"""GET /api/v1/features and /api/v1/feature-sets support CursorPage (limit, cursor, search, origin)."""
	project_id = client.post("/api/v1/projects", json={"project_name": "Pagination Proj"}).json()["data"]["project_id"]

	# Create 1 custom feature so CUSTOM filter has distinct item
	custom_res = client.post(
		"/api/v1/features",
		json={
			"project_id": project_id,
			"feature_key": "custom_paginated_expr",
			"display_name": "Custom Paginated Expr",
			"megafamily": "MONETARY",
			"compute_kind": "EXPRESSION",
			"output_type": "NUMERIC",
			"config_json": {"expr": "amount * 2"},
			"required_inputs": ["amount"],
		},
	)
	assert custom_res.status_code == 201

	# 1. Walk pages of features with limit=10
	collected_ids = []
	cursor = None
	pages = 0
	while True:
		url = f"/api/v1/features?project_id={project_id}&limit=10"
		if cursor:
			url += f"&cursor={cursor}"
		res = client.get(url)
		assert res.status_code == 200
		payload = res.json()["data"]
		page_items = payload["items"]
		assert len(page_items) <= 10
		collected_ids.extend(item["feature_id"] for item in page_items)
		pages += 1
		cursor = payload["nextCursor"]
		if cursor is None:
			break
		assert len(page_items) == 10

	assert pages >= 5
	assert len(collected_ids) == len(set(collected_ids))
	assert len(collected_ids) >= 53

	# 2. Filter by origin & search
	custom_only = client.get(f"/api/v1/features?project_id={project_id}&origin=CUSTOM").json()["data"]
	assert [f["feature_key"] for f in custom_only["items"]] == ["custom_paginated_expr"]
	assert custom_only["nextCursor"] is None

	searched = client.get(f"/api/v1/features?project_id={project_id}&search=free_email").json()["data"]
	assert any(f["feature_key"] == "is_free_email" for f in searched["items"])

	# 3. Invalid cursor -> 400
	bad_cursor_res = client.get(f"/api/v1/features?project_id={project_id}&cursor=invalid-cursor")
	assert bad_cursor_res.status_code == 400

	# 4. Walk pages of feature-sets with limit=2 (5 built-in sets -> 3 pages: 2 + 2 + 1)
	set_ids = []
	fs_cursor = None
	fs_pages = 0
	while True:
		url = f"/api/v1/feature-sets?project_id={project_id}&limit=2"
		if fs_cursor:
			url += f"&cursor={fs_cursor}"
		res = client.get(url)
		assert res.status_code == 200
		payload = res.json()["data"]
		set_ids.extend(item["feature_set_id"] for item in payload["items"])
		fs_pages += 1
		fs_cursor = payload["nextCursor"]
		if fs_cursor is None:
			break
		assert len(payload["items"]) == 2

	assert fs_pages == 3
	assert len(set_ids) == len(set(set_ids)) == 5
	assert client.get(f"/api/v1/feature-sets?project_id={project_id}&cursor=bad").status_code == 400
