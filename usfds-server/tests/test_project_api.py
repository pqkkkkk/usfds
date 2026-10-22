import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
from fastapi.testclient import TestClient
import pandas as pd
import pytest

from usfds_server.api import app
from usfds_server.config import settings


@pytest.fixture(autouse=True)
def temporary_environment():
    temp_dir = tempfile.mkdtemp(prefix="usfds_server_project_test_")
    db_file = os.path.join(temp_dir, "test.db")
    storage_path = os.path.join(temp_dir, "storage")

    settings.db_path = db_file
    settings.storage_dir = storage_path

    yield

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_project_lifecycle_and_schema_governance_api():
    with TestClient(app) as client:
        user_id = str(uuid4())

        # -------------------------------------------------------------
        # 1. Create Project (starts with unlocked schema)
        # -------------------------------------------------------------
        create_res = client.post(
            "/api/v1/projects",
            json={
                "project_name": "E-Commerce Fraud 2026",
                "user_id": user_id,
                "description": "Main project for e-commerce transaction monitoring",
            },
        )
        assert create_res.status_code == 201, create_res.text
        proj_data = create_res.json()["data"]
        project_id = proj_data["project_id"]
        assert proj_data["project_name"] == "E-Commerce Fraud 2026"
        assert proj_data["status"] == "ACTIVE"
        assert proj_data["is_schema_locked"] is False
        assert proj_data["raw_schema"] is None

        # Duplicate project name for same user -> 400
        dup_res = client.post(
            "/api/v1/projects",
            json={"project_name": "e-commerce fraud 2026", "user_id": user_id},
        )
        assert dup_res.status_code == 400
        assert dup_res.json()["success"] is False

        # -------------------------------------------------------------
        # 2. Creating an ACTIVE rule before first dataset is rejected (BR-PM-04)
        # -------------------------------------------------------------
        early_rule_res = client.post(
            "/api/v1/rules",
            json={
                "project_id": project_id,
                "rule_code": "R_EARLY",
                "name": "Early Rule",
                "condition": {">": [{"var": "TxAmount"}, 1000]},
                "action": "REJECT",
                "status": "ACTIVE",
            },
        )
        assert early_rule_res.status_code == 400
        assert early_rule_res.json()["success"] is False

        # -------------------------------------------------------------
        # 3. Upload First Dataset -> Locks Project RAW Schema (BR-PM-01)
        # -------------------------------------------------------------
        storage_root = Path(settings.storage_dir)
        storage_root.mkdir(parents=True, exist_ok=True)

        df1 = pd.DataFrame({
            "TransactionID": [f"TX_{i}" for i in range(10)],
            "TxTime": [f"2026-01-01 10:0{i}:00" for i in range(10)],
            "TxAmount": [100 * (i + 1) for i in range(10)],  # int64 -> NUMERIC
            "Channel": ["ONLINE"] * 5 + ["MOBILE"] * 5,      # object -> STRING
            "IsFraud": [0] * 8 + [1] * 2,                    # int64 -> NUMERIC
        })
        csv1_path = storage_root / "batch1.csv"
        df1.to_csv(csv1_path, index=False)

        imp1_res = client.post(
            "/api/v1/datasets/import",
            json={
                "file_path": str(csv1_path),
                "dataset_name": "historical_q1",
                "project_id": project_id,
                "user_id": user_id,
            },
        )
        assert imp1_res.status_code == 201, imp1_res.text
        ds1_id = imp1_res.json()["data"]["dataset"]["dataset_id"]

        # Verify GET /api/v1/projects/{project_id} now includes locked raw_schema
        get_proj_res = client.get(f"/api/v1/projects/{project_id}")
        assert get_proj_res.status_code == 200
        locked_proj = get_proj_res.json()["data"]
        assert locked_proj["is_schema_locked"] is True
        assert locked_proj["base_dataset_id"] == ds1_id
        assert locked_proj["datasets_count"] == 1
        assert "TxAmount" in locked_proj["raw_schema"]["columns"]
        assert locked_proj["raw_schema"]["columns"]["TxAmount"]["logical_type"] == "NUMERIC"
        assert locked_proj["raw_schema"]["columns"]["Channel"]["logical_type"] == "STRING"

        # -------------------------------------------------------------
        # 4. Upload Second Dataset (Unlabeled Inference + float64 NaN) -> Passes (BR-PM-02)
        # -------------------------------------------------------------
        df2 = pd.DataFrame({
            "TransactionID": ["TX_100", "TX_101"],
            "TxTime": ["2026-02-01 12:00:00", "2026-02-01 12:05:00"],
            "TxAmount": [250.75, None],  # float64 with NaN -> compatible with NUMERIC
            "Channel": ["ONLINE", "POS"],
            # Missing 'IsFraud' label column -> allowed for inference
        })
        csv2_path = storage_root / "batch2_inference.csv"
        df2.to_csv(csv2_path, index=False)

        imp2_res = client.post(
            "/api/v1/datasets/import",
            json={
                "file_path": str(csv2_path),
                "dataset_name": "inference_q2",
                "project_id": project_id,
                "user_id": user_id,
            },
        )
        assert imp2_res.status_code == 201, imp2_res.text
        ds2_id = imp2_res.json()["data"]["dataset"]["dataset_id"]

        # -------------------------------------------------------------
        # 5. Upload Incompatible Dataset -> Rejected (BR-PM-02)
        # -------------------------------------------------------------
        df_bad = pd.DataFrame({
            "TransactionID": ["TX_200"],
            "WrongColumn": [999],
        })
        csv_bad_path = storage_root / "bad.csv"
        df_bad.to_csv(csv_bad_path, index=False)

        imp_bad_res = client.post(
            "/api/v1/datasets/import",
            json={
                "file_path": str(csv_bad_path),
                "dataset_name": "incompatible_ds",
                "project_id": project_id,
                "user_id": user_id,
            },
        )
        assert imp_bad_res.status_code == 400
        assert imp_bad_res.json()["success"] is False

        # -------------------------------------------------------------
        # 6. Create & Evaluate Rule directly on RAW schema fields (BR-PM-05)
        # -------------------------------------------------------------
        # Invalid column name in rule -> Rejected (400)
        bad_rule_res = client.post(
            "/api/v1/rules",
            json={
                "project_id": project_id,
                "rule_code": "R_INVALID_COL",
                "name": "Invalid Column Rule",
                "condition": {">": [{"var": "NonExistentField"}, 500]},
                "action": "REJECT",
            },
        )
        assert bad_rule_res.status_code == 400

        # Valid RAW schema fields -> Created (201)
        valid_rule_res = client.post(
            "/api/v1/rules",
            json={
                "project_id": project_id,
                "rule_code": "R_HIGH_TX_AMOUNT",
                "name": "High Transaction Amount",
                "condition": {
                    "and": [
                        {">": [{"var": "TxAmount"}, 5000]},
                        {"==": [{"var": "Channel"}, "ONLINE"]},
                    ]
                },
                "action": "REJECT",
                "status": "ACTIVE",
            },
        )
        assert valid_rule_res.status_code == 201, valid_rule_res.text
        rule_id = valid_rule_res.json()["data"]["rule_id"]

        # Evaluate rule using raw_features
        eval_res = client.post(
            f"/api/v1/rules/{rule_id}/evaluate",
            json={
                "transaction_id": "TX_999",
                "raw_features": {"TxAmount": 12000, "Channel": "ONLINE"},
            },
        )
        assert eval_res.status_code == 200
        assert eval_res.json()["data"]["is_triggered"] is True

        # -------------------------------------------------------------
        # 7. Schema Reset Guard & Auto-Unlock when resources removed (BR-PM-03)
        # -------------------------------------------------------------
        # Cannot reset schema while datasets and rules exist
        reset_fail_res = client.post(f"/api/v1/projects/{project_id}/schema/reset")
        assert reset_fail_res.status_code == 400

        # Delete first dataset -> schema remains locked because ds2 and rule still exist
        client.delete(f"/api/v1/datasets/{ds1_id}")
        proj_after_ds1 = client.get(f"/api/v1/projects/{project_id}").json()["data"]
        assert proj_after_ds1["is_schema_locked"] is True

        # Delete rule and second dataset -> auto-unlocks schema!
        client.delete(f"/api/v1/rules/{rule_id}")
        client.delete(f"/api/v1/datasets/{ds2_id}")
        proj_unlocked = client.get(f"/api/v1/projects/{project_id}").json()["data"]
        assert proj_unlocked["is_schema_locked"] is False
        assert proj_unlocked["raw_schema"] is None

        # -------------------------------------------------------------
        # 8. Update & Delete Project
        # -------------------------------------------------------------
        patch_res = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"project_name": "E-Commerce Fraud Updated", "status": "ARCHIVED"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["data"]["project_name"] == "E-Commerce Fraud Updated"
        assert patch_res.json()["data"]["status"] == "ARCHIVED"

        del_proj_res = client.delete(f"/api/v1/projects/{project_id}")
        assert del_proj_res.status_code == 200
        assert del_proj_res.json()["data"] is True

        get_deleted = client.get(f"/api/v1/projects/{project_id}")
        assert get_deleted.status_code == 404
