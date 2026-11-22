from datetime import datetime, timezone
import json
from uuid import uuid4

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus, PipelineStage
from usfds_core.domain.entities.system import Project
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteDetectionJobRepository,
	SqliteProjectRepository,
	SqlUserRepository,
)
from usfds_server.api import app
from usfds_server.config import settings
from usfds_server.dependencies import get_db, get_storage
from usfds_server.routers.investigation_router import ingest_request
from usfds_server.schemas.investigation_api_schemas import CaseIntakeRequest


def test_actor_is_backend_owned():
	from fastapi import Depends, FastAPI
	from usfds_server.routers.investigation_router import get_actor

	actor_app = FastAPI()

	@actor_app.get("/actor")
	def actor_endpoint(actor: str = Depends(get_actor)):
		return {"actor": actor}

	with TestClient(actor_app) as client:
		assert client.get("/actor").json() == {"actor": "admin"}
		assert client.get("/actor", headers={"X-Actor": "spoofed"}).json() == {"actor": "admin"}
		assert [p for p in actor_app.openapi()["paths"]["/actor"]["get"].get("parameters", []) if p.get("name") == "X-Actor"] == []

	from usfds_server.schemas.investigation_api_schemas import CaseIntakeRequest
	request = CaseIntakeRequest.model_validate({"project_id": str(uuid4()), "detection_job_id": str(uuid4()),
		"transactions": [{"event_id": "TX-1", "user_id": "U1", "timestamp": "2026-11-01T00:00:00Z", "amount": 100, "final_action": "REVIEW"}]})
	assert request.dataset_artifact_id is None


def test_investigation_contract_and_independent_resolution(tmp_path):
	old_db, old_storage = settings.db_path, settings.storage_dir
	settings.db_path, settings.storage_dir = str(tmp_path / "cases.db"), str(tmp_path / "storage")
	try:
		with TestClient(app) as client:
			from usfds_infra.database import SqlUserRepository

			project_id = uuid4()
			session_generator = get_db()
			session = next(session_generator)
			actor_id = SqlUserRepository(session).get_by_username("admin").user_id
			project = Project(project_name="Investigation test", user_id=actor_id, project_id=project_id,
				raw_schema={"columns": {"amount": {"logical_type": "NUMERIC"}}})
			SqliteProjectRepository(session).save(project)
			dataset = SqliteDatasetRepository(session).save(Dataset(dataset_name="transactions", project_id=project_id, user_id=actor_id))
			frame = pd.DataFrame([
				{"event_id": "OLD", "user_id": "U1", "timestamp": "2026-10-01T00:00:00Z", "amount": 100},
				{"event_id": "TX-1", "user_id": "U1", "timestamp": "2026-10-10T00:00:00Z", "amount": 1000},
				{"event_id": "TX-2", "user_id": "U1", "timestamp": "2026-10-10T00:01:00Z", "amount": 2000},
			])
			path = get_storage().save_bytes("transactions.parquet", frame.to_parquet(index=False))
			artifact = SqliteDatasetArtifactRepository(session).save(DatasetArtifact(dataset_id=dataset.dataset_id, storage_path=path, pipeline_stage=PipelineStage.MAPPED))
			session.commit()
			session_generator.close()
			payload = {"project_id": str(project_id), "dataset_artifact_id": str(artifact.artifact_id), "transactions": [
				{"event_id": "TX-1", "user_id": "U1", "timestamp": "2026-10-10T00:00:00Z", "amount": 1000, "model_score": .95,
				 "final_action": "REVIEW", "attributes": {"amount": 1000}, "feature_contributions": [{"feature_name": "amount", "contribution": .4}]},
				{"event_id": "TX-2", "user_id": "U1", "timestamp": "2026-10-10T00:01:00Z", "amount": 2000, "final_action": "REJECT"},
			]}
			seed_generator = get_db()
			seed_session = next(seed_generator)
			request = CaseIntakeRequest.model_validate(payload)
			intake = ingest_request(request, seed_session, get_storage(), "local-analyst")
			ids = intake["created_case_ids"]
			assert len(ids) == 2
			assert ingest_request(request, seed_session, get_storage(), "local-analyst")["accepted_count"] == 0
			seed_session.commit()
			seed_generator.close()
			assert "/api/v1/cases/intake" not in app.openapi()["paths"]
			url = f"/api/v1/cases/{ids[0]}"
			params = {"project_id": str(project_id)}
			pending = client.post(
				url + "/pending-customer",
				params=params,
				json={"expected_version": 1, "summary": "Contacted cardholder to confirm transaction"},
			)
			assert pending.status_code == 200, pending.text
			assert pending.json()["data"]["case"]["status"] == "PENDING_CUSTOMER"
			assert "assigned_to" not in pending.json()["data"]["case"]
			assert "related_assignees" not in pending.json()["data"]
			assert client.post(
				url + "/pending-customer",
				params=params,
				json={"expected_version": 1, "summary": "Stale version retry should conflict"},
			).status_code == 409
			decision = {"expected_version": 2, "verdict": "FRAUD", "reason": "OTHER_FRAUD", "summary": "Verified unauthorized transaction by customer",
				"block_entities": [{"entity_type": "USER_ID", "entity_value": "NOT_THIS_USER"}]}
			assert client.post(url + "/resolve", params=params, json=decision).status_code == 400
			assert client.get(url, params=params).json()["data"]["version"] == 2
			decision["block_entities"][0]["entity_value"] = "U1"
			resolved = client.post(url + "/resolve", params=params, json=decision)
			assert resolved.status_code == 200, resolved.text
			assert resolved.json()["data"]["case"]["verified_label"] == 1
			assert resolved.json()["data"]["case"]["resolved_by"] == "admin"
			assert client.get(f"/api/v1/cases/{ids[1]}", params=params).json()["data"]["status"] == "OPEN"
			for window in (None, 30, 90):
				window_params = params if window is None else {**params, "days": window}
				workbench = client.get(url + "/workbench", params=window_params)
				assert workbench.status_code == 200, workbench.text
				assert workbench.json()["data"]["profile"]["days"] == (30 if window is None else window)
			for window in (0, 60, 91, "invalid"):
				assert client.get(url + "/workbench", params={**params, "days": window}).status_code == 422
			assert workbench.json()["data"]["profile"]["avg_amount"] == 100
			assert workbench.json()["data"]["subject_status"] == "BLOCKED"
			assert len(workbench.json()["data"]["related_cases"]) == 1
			assert len(workbench.json()["data"]["audit_logs"]) == 3
			assert client.get(url + "/rule-draft", params=params).json()["data"]["condition"] == {"and": [{">=": [{"var": "amount"}, 1000]}]}
			entries = client.get("/api/v1/blacklist", params=params).json()["data"]
			assert len(entries) == 1
			duplicate = {"project_id": str(project_id), "entity_type": "USER_ID", "entity_value": "U1", "reason": "Duplicate block attempt"}
			assert client.post("/api/v1/blacklist", json=duplicate).status_code == 409
			assert client.post(f"/api/v1/blacklist/{entries[0]['blacklist_id']}/remove", params=params, json={"reason": "Investigation established release conditions"}).status_code == 200
			assert client.post(url + "/reopen", params=params, json={"expected_version": 3, "summary": "Additional evidence requires review"}).json()["data"]["case"]["verified_label"] is None
			bad = dict(payload, transactions=[dict(payload["transactions"][0], event_id="UNKNOWN")])
			invalid_generator = get_db()
			invalid_session = next(invalid_generator)
			with pytest.raises(HTTPException) as error:
				ingest_request(CaseIntakeRequest.model_validate(bad), invalid_session, get_storage(), "local-analyst")
			assert error.value.status_code == 400
			invalid_generator.close()
			invalid = dict(payload, transactions=[dict(payload["transactions"][0], final_action="ALERT")])
			with pytest.raises(ValidationError):
				CaseIntakeRequest.model_validate(invalid)
			assert client.get("/api/v1/cases", params=params).json()["data"]["total"] == 2
	finally:
		settings.db_path, settings.storage_dir = old_db, old_storage


def test_investigation_api_removes_claim_and_escalates_without_assignee(client, server_session_factory):
	"""ISS-045 / SUC-17 / SUC-18: /claim route and assigned_to/assignee fields are removed; /escalate requires only summary."""
	assert "/api/v1/cases/{case_id}/claim" not in app.openapi()["paths"]
	list_params = app.openapi()["paths"]["/api/v1/cases"]["get"]["parameters"]
	param_names = {p["name"] for p in list_params}
	assert "assigned_to" not in param_names
	assert "unassigned" not in param_names

	project_id, job_id = uuid4(), uuid4()
	with server_session_factory() as session:
		actor_id = SqlUserRepository(session).get_by_username("admin").user_id
		SqliteProjectRepository(session).save(Project(project_id=project_id, user_id=actor_id, project_name="Escalate Test"))
		pred_df = pd.DataFrame([
			{"event_id": "EV-ESC", "user_id": "U-ESC", "timestamp": "2026-11-10T03:00:00Z", "amount": 900.0, "final_action": "REVIEW", "model_score": 0.72},
		])
		output_path = get_storage().save_bytes(f"datasets/{project_id}/inferences/{job_id}/predictions.parquet", pred_df.to_parquet(index=False))
		SqliteDetectionJobRepository(session).save(DetectionJob(
			job_id=job_id, project_id=project_id, user_id=actor_id, job_name="Escalate Scan",
			output_path=output_path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
		))
		session.commit()

		intake = ingest_request(
			CaseIntakeRequest.model_validate({
				"project_id": str(project_id),
				"detection_job_id": str(job_id),
				"transactions": [{
					"event_id": "EV-ESC", "user_id": "U-ESC", "timestamp": "2026-11-10T03:00:00Z",
					"amount": 900.0, "model_score": 0.72, "final_action": "REVIEW",
				}],
			}),
			session,
			get_storage(),
			"admin",
		)
		case_id = intake["created_case_ids"][0]
		session.commit()

	params = {"project_id": str(project_id)}
	assert client.post(f"/api/v1/cases/{case_id}/claim", params=params, json={"expected_version": 1}).status_code in (404, 405)

	# Extra `assignee` field must be rejected by CaseActionRequest (extra="forbid")
	assert client.post(
		f"/api/v1/cases/{case_id}/escalate",
		params=params,
		json={"expected_version": 1, "summary": "High risk anomaly requires urgent check", "assignee": "someone"},
	).status_code == 422

	escalated = client.post(
		f"/api/v1/cases/{case_id}/escalate",
		params=params,
		json={"expected_version": 1, "summary": "High risk anomaly requires urgent check"},
	)
	assert escalated.status_code == 200, escalated.text
	body = escalated.json()["data"]
	assert "related_assignees" not in body
	assert body["case"]["priority"] == "CRITICAL"
	assert "assigned_to" not in body["case"]


def test_workbench_queries_warehouse_via_duckdb_without_pandas_full_load(client, server_session_factory, monkeypatch):
	"""ISS-045 / SUC-18: Workbench loads behavior profile and timeline from ProjectWarehouse via DuckDB without pandas file reads."""
	project_id, job_id = uuid4(), uuid4()
	with server_session_factory() as session:
		actor_id = SqlUserRepository(session).get_by_username("admin").user_id
		SqliteProjectRepository(session).save(Project(project_id=project_id, user_id=actor_id, project_name="WB Warehouse Test"))
		pred_df = pd.DataFrame([
			{"event_id": "EV-H1", "user_id": "U-WB", "timestamp": "2026-11-05T02:00:00Z", "amount": 100.0, "final_action": "ALLOW",
			 "model_score": 0.10, "device_id": "DEV-HOME", "ip_address": "1.1.1.1", "card_id": "C-1", "merchant_id": "M-1", "merchant_category": "FOOD"},
			{"event_id": "EV-H2", "user_id": "U-WB", "timestamp": "2026-11-08T02:30:00Z", "amount": 300.0, "final_action": "ALLOW",
			 "model_score": 0.15, "device_id": "DEV-HOME", "ip_address": "1.1.1.1", "card_id": "C-1", "merchant_id": "M-1", "merchant_category": "FOOD"},
			{"event_id": "EV-CURR", "user_id": "U-WB", "timestamp": "2026-11-10T15:00:00Z", "amount": 1200.0, "final_action": "REJECT",
			 "model_score": 0.91, "device_id": "DEV-EVIL", "ip_address": "1.1.1.1", "card_id": "C-1", "merchant_id": "M-1", "merchant_category": "CRYPTO"},
		])
		output_path = get_storage().save_bytes(f"datasets/{project_id}/inferences/{job_id}/predictions.parquet", pred_df.to_parquet(index=False))
		SqliteDetectionJobRepository(session).save(DetectionJob(
			job_id=job_id, project_id=project_id, user_id=actor_id, job_name="WB Scan",
			output_path=output_path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
			created_at=datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc),
		))
		session.commit()

		intake = ingest_request(
			CaseIntakeRequest.model_validate({
				"project_id": str(project_id),
				"detection_job_id": str(job_id),
				"transactions": [{
					"event_id": "EV-CURR", "user_id": "U-WB", "timestamp": "2026-11-10T15:00:00Z",
					"amount": 1200.0, "model_score": 0.91, "final_action": "REJECT",
				}],
			}),
			session,
			get_storage(),
			"admin",
		)
		case_id = intake["created_case_ids"][0]
		session.commit()

	def _blocked(*args, **kwargs):
		raise AssertionError("pandas file read must not be used in workbench (ISS-045)")

	monkeypatch.setattr(pd, "read_parquet", _blocked)
	monkeypatch.setattr(pd, "read_csv", _blocked)

	res = client.get(f"/api/v1/cases/{case_id}/workbench", params={"project_id": str(project_id), "days": 30})
	assert res.status_code == 200, res.text
	data = res.json()["data"]
	assert "assigned_to" not in data["case"]
	profile = data["profile"]
	assert profile["available"] is True
	assert profile["avg_amount"] == 200.0
	assert profile["max_amount"] == 300.0
	comp = {item["field"]: item for item in profile["comparison"]}
	assert comp["device_id"]["current"] == "DEV-EVIL"
	assert comp["device_id"]["is_anomalous"] is True
	assert comp["merchant_category"]["current"] == "CRYPTO"
	assert [item["event_id"] for item in profile["timeline"]] == ["EV-H1", "EV-H2", "EV-CURR"]
	assert get_storage().exists(f"warehouse/{project_id}/fact_transactions/job_{job_id}.parquet")