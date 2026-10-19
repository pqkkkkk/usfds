import os
import shutil
import tempfile
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest

from usfds_server.api import app
from usfds_server.config import settings


@pytest.fixture(autouse=True)
def temporary_environment():
    temp_dir = tempfile.mkdtemp(prefix="usfds_server_rule_test_")
    db_file = os.path.join(temp_dir, "test.db")
    storage_path = os.path.join(temp_dir, "storage")

    settings.db_path = db_file
    settings.storage_dir = storage_path

    yield

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_rule_crud_and_versioning_flow():
    with TestClient(app) as client:
        project_id = str(uuid4())

        # 1. Create a new rule
        create_payload = {
            "project_id": project_id,
            "rule_code": "R_HIGH_AMOUNT_ONLINE",
            "name": "High Amount Online",
            "description": "Reject online transactions > 50M",
            "condition": {
                "and": [
                    {">": [{"var": "mapped.amount"}, 50000000]},
                    {"in": [{"var": "mapped.channel"}, ["ONLINE", "MOBILE"]]},
                ]
            },
            "action": "REJECT",
            "status": "ACTIVE",
            "change_summary": "Initial rule setup",
        }
        res = client.post("/api/v1/rules", json=create_payload)
        assert res.status_code == 201
        res_data = res.json()
        assert res_data["success"] is True
        rule_data = res_data["data"]
        rule_id = rule_data["rule_id"]

        assert rule_data["rule_code"] == "R_HIGH_AMOUNT_ONLINE"
        assert rule_data["status"] == "ACTIVE"
        assert rule_data["current_version"] is not None
        assert rule_data["current_version"]["version_number"] == 1
        assert rule_data["current_version"]["action"] == "REJECT"

        # 2. Get rule by ID
        get_res = client.get(f"/api/v1/rules/{rule_id}")
        assert get_res.status_code == 200
        assert get_res.json()["data"]["rule_id"] == rule_id

        # 3. List rules by project
        list_res = client.get(f"/api/v1/rules?project_id={project_id}")
        assert list_res.status_code == 200
        assert len(list_res.json()["data"]) == 1

        # 4. Evaluate single rule (Triggered)
        eval_payload = {
            "transaction_id": "TX_TEST_001",
            "mapped_features": {"amount": 75000000, "channel": "ONLINE"},
            "enriched_features": {},
        }
        eval_res = client.post(f"/api/v1/rules/{rule_id}/evaluate", json=eval_payload)
        assert eval_res.status_code == 200
        eval_data = eval_res.json()["data"]
        assert eval_data["is_triggered"] is True
        assert eval_data["action"] == "REJECT"
        assert eval_data["version_number"] == 1

        # Evaluate single rule (Not triggered)
        eval_payload_fail = {
            "transaction_id": "TX_TEST_002",
            "mapped_features": {"amount": 10000000, "channel": "ONLINE"},
            "enriched_features": {},
        }
        eval_fail_res = client.post(f"/api/v1/rules/{rule_id}/evaluate", json=eval_payload_fail)
        assert eval_fail_res.status_code == 200
        assert eval_fail_res.json()["data"]["is_triggered"] is False

        # 5. Update rule condition -> Auto-increments to Version 2
        update_payload = {
            "condition": {
                "and": [
                    {">": [{"var": "mapped.amount"}, 20000000]},
                    {"in": [{"var": "mapped.channel"}, ["ONLINE", "MOBILE"]]},
                ]
            },
            "action": "REVIEW",
            "change_summary": "Lower amount threshold to 20M and change action to REVIEW",
        }
        update_res = client.put(f"/api/v1/rules/{rule_id}", json=update_payload)
        assert update_res.status_code == 200
        updated_data = update_res.json()["data"]
        assert updated_data["current_version"]["version_number"] == 2
        assert updated_data["current_version"]["action"] == "REVIEW"

        # 6. Verify version history audit trail
        history_res = client.get(f"/api/v1/rules/{rule_id}/versions")
        assert history_res.status_code == 200
        history_data = history_res.json()["data"]
        assert len(history_data) == 2
        assert [v["version_number"] for v in history_data] == [1, 2]

        # 7. Evaluate batch rules in project
        batch_payload = {
            "project_id": project_id,
            "transaction_id": "TX_TEST_003",
            "mapped_features": {"amount": 35000000, "channel": "ONLINE"},
            "enriched_features": {},
        }
        batch_res = client.post("/api/v1/rules/evaluate-batch", json=batch_payload)
        assert batch_res.status_code == 200
        batch_results = batch_res.json()["data"]
        assert len(batch_results) == 1
        # Triggers version 2 (35M > 20M)
        assert batch_results[0]["is_triggered"] is True
        assert batch_results[0]["version_number"] == 2
        assert batch_results[0]["action"] == "REVIEW"

        # 8. Set status to INACTIVE
        status_res = client.patch(f"/api/v1/rules/{rule_id}/status", json={"status": "INACTIVE"})
        assert status_res.status_code == 200
        assert status_res.json()["data"]["status"] == "INACTIVE"

        # Active batch should now return empty
        batch_after_inactive = client.post("/api/v1/rules/evaluate-batch", json=batch_payload)
        assert batch_after_inactive.status_code == 200
        assert len(batch_after_inactive.json()["data"]) == 0

        # 9. Delete rule
        del_res = client.delete(f"/api/v1/rules/{rule_id}")
        assert del_res.status_code == 200
        assert del_res.json()["data"] is True
