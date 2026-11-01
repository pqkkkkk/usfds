from uuid import uuid4

import pandas as pd
from fastapi.testclient import TestClient

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage
from usfds_core.domain.entities.system import Project
from usfds_infra.database import SqliteDatasetArtifactRepository, SqliteDatasetRepository, SqliteProjectRepository
from usfds_server.api import app
from usfds_server.config import settings
from usfds_server.dependencies import get_db, get_storage


def test_actor_is_backend_owned():
	from fastapi import Depends, FastAPI
	from usfds_server.routers.investigation_router import get_actor

	actor_app = FastAPI()

	@actor_app.get("/actor")
	def actor_endpoint(actor: str = Depends(get_actor)):
		return {"actor": actor}

	with TestClient(actor_app) as client:
		assert client.get("/actor").json() == {"actor": "local-analyst"}
		assert client.get("/actor", headers={"X-Actor": "spoofed"}).json() == {"actor": "local-analyst"}
		assert actor_app.openapi()["paths"]["/actor"]["get"].get("parameters", []) == []


def test_investigation_contract_and_independent_resolution(tmp_path):
	old_db, old_storage = settings.db_path, settings.storage_dir
	settings.db_path, settings.storage_dir = str(tmp_path / "cases.db"), str(tmp_path / "storage")
	try:
		with TestClient(app) as client:
			project_id, actor_id = uuid4(), uuid4()
			session_generator = get_db()
			session = next(session_generator)
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
			intake = client.post("/api/v1/cases/intake", json=payload)
			assert intake.status_code == 201, intake.text
			ids = intake.json()["data"]["created_case_ids"]
			assert len(ids) == 2
			assert client.post("/api/v1/cases/intake", json=payload).json()["data"]["accepted_count"] == 0
			url = f"/api/v1/cases/{ids[0]}"
			params = {"project_id": str(project_id)}
			first = client.post(url + "/claim", params=params, json={"expected_version": 1})
			assert first.status_code == 200, first.text
			assert first.json()["data"]["case"]["assigned_to"] == "local-analyst"
			assert client.post(url + "/claim", params=params, json={"expected_version": 1}).status_code == 409
			second = client.post(f"/api/v1/cases/{ids[1]}/claim", params=params, json={"expected_version": 1})
			assert second.json()["data"]["related_assignees"] == []
			decision = {"expected_version": 2, "verdict": "FRAUD", "reason": "OTHER_FRAUD", "summary": "Verified unauthorized transaction by customer",
				"block_entities": [{"entity_type": "USER_ID", "entity_value": "NOT_THIS_USER"}]}
			assert client.post(url + "/resolve", params=params, json=decision).status_code == 400
			assert client.get(url, params=params).json()["data"]["version"] == 2
			decision["block_entities"][0]["entity_value"] = "U1"
			resolved = client.post(url + "/resolve", params=params, json=decision)
			assert resolved.status_code == 200, resolved.text
			assert resolved.json()["data"]["case"]["verified_label"] == 1
			assert resolved.json()["data"]["case"]["resolved_by"] == "local-analyst"
			assert client.get(f"/api/v1/cases/{ids[1]}", params=params).json()["data"]["status"] == "IN_PROGRESS"
			workbench = client.get(url + "/workbench", params=params)
			assert workbench.status_code == 200, workbench.text
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
			assert client.post("/api/v1/cases/intake", json=bad).status_code == 400
			invalid = dict(payload, transactions=[dict(payload["transactions"][0], final_action="ALERT")])
			assert client.post("/api/v1/cases/intake", json=invalid).status_code == 422
			assert client.get("/api/v1/cases", params=params).json()["data"]["total"] == 2
	finally:
		settings.db_path, settings.storage_dir = old_db, old_storage