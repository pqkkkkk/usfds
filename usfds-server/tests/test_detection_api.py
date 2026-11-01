import io
import os
import shutil
import tempfile
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
import pytest

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.services.project_management.schema_validator import ProjectSchemaValidator
from usfds_server import dependencies
from usfds_server.api import app
from usfds_server.config import settings


@pytest.fixture(autouse=True)
def temporary_environment():
	temp_dir = tempfile.mkdtemp(prefix="usfds_detection_api_test_")
	db_file = os.path.join(temp_dir, "test.db")
	storage_path = os.path.join(temp_dir, "storage")

	settings.db_path = db_file
	settings.storage_dir = storage_path
	dependencies._engine = None
	dependencies._session_factory = None
	dependencies._storage = None

	yield temp_dir

	dependencies.teardown_infrastructure()
	dependencies._session_factory = None
	dependencies._storage = None
	if os.path.exists(temp_dir):
		shutil.rmtree(temp_dir, ignore_errors=True)


def _seed_project_and_datasets(project_id_str: str):
	"""Seed a RAW artifact and a FEATURE_ENGINEERED artifact for a project."""
	assert dependencies._session_factory is not None
	session = dependencies._session_factory()
	try:
		proj_repo = dependencies.SqliteProjectRepository(session)
		ds_repo = dependencies.SqliteDatasetRepository(session)
		art_repo = dependencies.SqliteDatasetArtifactRepository(session)
		storage = dependencies.get_storage()

		proj = proj_repo.get_by_id(UUID(project_id_str))
		assert proj is not None

		rng = np.random.default_rng(101)
		n_rows = 40
		df = pd.DataFrame({
			"event_id": [f"evt_{i}" for i in range(n_rows)],
			"user_id": [f"usr_{i % 5}" for i in range(n_rows)],
			"amount": [650.0 if i % 4 == 0 else float(rng.uniform(10.0, 200.0)) for i in range(n_rows)],
			"velocity_1h": rng.integers(1, 8, size=n_rows).astype(float),
			"country": rng.choice(["US", "VN", "SG"], size=n_rows),
			"label": np.array([1 if i % 4 == 0 else 0 for i in range(n_rows)]),
		})

		proj.raw_schema = ProjectSchemaValidator.extract_raw_schema(df).to_dict()
		proj_repo.save(proj)

		csv_buf = io.BytesIO()
		df.drop(columns=["label"]).to_csv(csv_buf, index=False)
		raw_csv_bytes = csv_buf.getvalue()

		pq_buf = io.BytesIO()
		df.to_parquet(pq_buf, index=False)
		pq_bytes = pq_buf.getvalue()

		dataset_id = uuid4()
		raw_artifact_id = uuid4()
		fe_artifact_id = uuid4()

		raw_rel = f"datasets/{dataset_id}/artifacts/{raw_artifact_id}/raw.csv"
		train_rel = f"datasets/{dataset_id}/artifacts/{fe_artifact_id}/train_enriched.parquet"
		test_rel = f"datasets/{dataset_id}/artifacts/{fe_artifact_id}/test_enriched.parquet"

		storage.save_bytes(raw_rel, raw_csv_bytes)
		storage.save_bytes(train_rel, pq_bytes)
		storage.save_bytes(test_rel, pq_bytes)

		dataset = Dataset(
			dataset_id=dataset_id,
			project_id=UUID(project_id_str),
			user_id=uuid4(),
			dataset_name="detection_test_ds",
		)
		ds_repo.save(dataset)

		raw_artifact = DatasetArtifact(
			artifact_id=raw_artifact_id,
			dataset_id=dataset_id,
			pipeline_stage=PipelineStage.RAW,
			storage_path=raw_rel,
			output_paths={"raw": raw_rel},
			row_count=n_rows,
			column_count=5,
			validation_status=ValidationStatus.PASSED,
		)
		art_repo.save(raw_artifact)

		fe_artifact = DatasetArtifact(
			artifact_id=fe_artifact_id,
			dataset_id=dataset_id,
			parent_artifact_id=raw_artifact_id,
			pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
			storage_path=f"datasets/{dataset_id}/artifacts/{fe_artifact_id}",
			output_paths={"train": train_rel, "test": test_rel},
			row_count=n_rows,
			column_count=6,
			validation_status=ValidationStatus.PASSED,
			validation_report={"target_column": "label"},
		)
		art_repo.save(fe_artifact)
		session.commit()

		# Also write an external CSV file in temp_dir for Option 2 testing
		external_csv_path = os.path.join(settings.storage_dir, "external_upload_batch.csv")
		with open(external_csv_path, "wb") as f:
			f.write(raw_csv_bytes)

		return str(raw_artifact_id), str(fe_artifact_id), external_csv_path
	finally:
		session.close()


def test_detection_api_end_to_end(temporary_environment):
	with TestClient(app) as client:
		# 1. Create a project with raw_schema
		res_proj = client.post(
			"/api/v1/projects",
			json={
				"project_name": "E-Commerce Fraud Detection",
				"description": "Hybrid detection API test",
				"raw_schema": {
					"event_id": "string",
					"user_id": "string",
					"amount": "float",
					"velocity_1h": "float",
					"country": "string",
				},
			},
		)
		assert res_proj.status_code == 201, res_proj.text
		project_id = res_proj.json()["data"]["project_id"]

		raw_artifact_id, fe_artifact_id, external_csv_path = _seed_project_and_datasets(project_id)

		# 2. Create and activate an ACTIVE rule (REJECT if amount > 500)
		res_rule = client.post(
			"/api/v1/rules",
			json={
				"project_id": project_id,
				"rule_code": "RL-HIGH-AMOUNT",
				"name": "High Amount Immediate Block",
				"condition": {">": [{"var": "amount"}, 500.0]},
				"action": "REJECT",
				"status": "ACTIVE",
			},
		)
		assert res_rule.status_code == 201, res_rule.text

		# 3. Train and activate a Built-in Random Forest model version
		res_models = client.get("/api/v1/training/models")
		rf_model = next(m for m in res_models.json()["data"] if m["model_name"] == "random_forest")

		res_run = client.post(
			"/api/v1/training/runs",
			json={
				"model_id": rf_model["model_id"],
				"dataset_artifact_id": fe_artifact_id,
				"hyperparameters": {"n_estimators": 10},
				"run_name": "rf-for-detection",
			},
		)
		assert res_run.status_code == 201, res_run.text
		version_id = res_run.json()["data"]["version_id"]

		res_act = client.post(
			f"/api/v1/training/versions/{version_id}/activate",
			json={"decision_threshold": 0.55, "description": "Approved for batch detection"},
		)
		assert res_act.status_code == 200, res_act.text

		# 4. Reject non-RAW target_artifact_id (Option 1 validation)
		res_bad_stage = client.post(
			"/api/v1/detection/jobs",
			json={
				"project_id": project_id,
				"target_artifact_id": fe_artifact_id,
				"model_version_id": version_id,
				"use_rules": True,
			},
		)
		assert res_bad_stage.status_code == 400
		assert "must be at stage 'RAW'" in res_bad_stage.json()["error"]

		# 5. Start Hybrid Detection Job using Option 1 (RAW target_artifact_id + ModelVersion + Active Rules)
		res_job1 = client.post(
			"/api/v1/detection/jobs",
			json={
				"project_id": project_id,
				"target_artifact_id": raw_artifact_id,
				"model_version_id": version_id,
				"score_threshold": 0.55,
				"use_rules": True,
				"job_name": "Batch-Scan-Option1-RAW-Artifact",
			},
		)
		assert res_job1.status_code == 201, res_job1.text
		job1 = res_job1.json()["data"]
		assert job1["status"] == "COMPLETED"
		assert job1["total_records"] == 40
		assert job1["summary_metrics"]["reject_count"] == 10  # 40 / 4 rows have amount = 650 > 500

		# 6. Start Detection Job using Option 2 (input_file_path in Rule-Only mode)
		res_job2 = client.post(
			"/api/v1/detection/jobs",
			json={
				"project_id": project_id,
				"input_file_path": external_csv_path,
				"model_version_id": None,
				"use_rules": True,
				"job_name": "Batch-Scan-Option2-FilePath",
			},
		)
		assert res_job2.status_code == 201, res_job2.text
		job2 = res_job2.json()["data"]
		assert job2["status"] == "COMPLETED"
		assert job2["total_records"] == 40

		# 7. List Detection Jobs (SUC-19)
		res_list = client.get(f"/api/v1/detection/jobs?project_id={project_id}")
		assert res_list.status_code == 200
		jobs = res_list.json()["data"]
		assert len(jobs) == 2

		# 8. View Detection Results (SUC-16)
		res_results = client.get(
			f"/api/v1/detection/jobs/{job1['job_id']}/results?action_filter=FLAGGED&limit=25&offset=0"
		)
		assert res_results.status_code == 200, res_results.text
		results_data = res_results.json()["data"]
		assert results_data["total_filtered"] >= 10
		first_flagged = results_data["transactions"][0]
		assert first_flagged["final_action"] in ("REJECT", "REVIEW")

		# 9. Export Detection Results as CSV
		res_export = client.get(
			f"/api/v1/detection/jobs/{job1['job_id']}/export?only_flagged=true&file_format=csv"
		)
		assert res_export.status_code == 200
		assert "text/csv" in res_export.headers["content-type"]

		# 10. Send to Investigation (SUC-16) and query Investigation Cases
		res_dispatch = client.post(
			f"/api/v1/detection/jobs/{job1['job_id']}/send-to-investigation",
			json={
				"event_ids": [first_flagged["event_id"]],
				"analyst_notes": "Confirmed high-value anomaly during batch scan",
			},
		)
		assert res_dispatch.status_code == 201, res_dispatch.text
		dispatched = res_dispatch.json()["data"]
		assert len(dispatched) == 1
		assert dispatched[0]["metadata"]["raw_event_id"] == first_flagged["event_id"]

		res_cases = client.get(f"/api/v1/detection/cases?project_id={project_id}")
		assert res_cases.status_code == 200
		cases = res_cases.json()["data"]
		assert len(cases) == 1
		assert cases[0]["analyst_notes"] == "Confirmed high-value anomaly during batch scan"


def test_detection_api_with_velocity_feature_engineering_and_raw_columns(temporary_environment):
	"""End-to-end test: Import RAW CSV (with 'transaction_id', 'transaction_time', 'is_fraud') ->
	Schema Mapping -> Velocity Feature Engineering (tx_freq_last_*h, tx_sum_last_*h) ->
	Train Random Forest -> Activate ModelVersion -> Batch Detection on unlabeled RAW CSV.
	"""
	with TestClient(app) as client:
		# 1. Create Project
		res_proj = client.post(
			"/api/v1/projects",
			json={
				"project_name": "Velocity FE Detection Project",
				"description": "Test velocity features on RAW input",
			},
		)
		assert res_proj.status_code == 201, res_proj.text
		project_id = res_proj.json()["data"]["project_id"]

		# 2. Write RAW training CSV and unlabeled batch CSV with non-canonical column names
		rng = np.random.default_rng(2026)
		n_rows = 60
		raw_train_df = pd.DataFrame({
			"transaction_id": [i + 1 for i in range(n_rows)],
			"user_id": [(i % 6) + 1 for i in range(n_rows)],
			"amount": [float(rng.uniform(20.0, 500.0)) for _ in range(n_rows)],
			"country": rng.choice(["US", "FR", "TR"], size=n_rows),
			"channel": rng.choice(["web", "app"], size=n_rows),
			"transaction_time": [f"2024-01-01T{(i // 6) % 24:02d}:{(i * 7) % 60:02d}:00Z" for i in range(n_rows)],
			"is_fraud": [1 if i % 5 == 0 else 0 for i in range(n_rows)],
		})

		train_csv_path = os.path.join(settings.storage_dir, "raw_ecommerce_train.csv")
		os.makedirs(settings.storage_dir, exist_ok=True)
		raw_train_df.to_csv(train_csv_path, index=False)

		unlabeled_batch_df = raw_train_df.drop(columns=["is_fraud"]).iloc[:20].copy()
		unlabeled_csv_path = os.path.join(settings.storage_dir, "test_random_unlabeled.csv")
		unlabeled_batch_df.to_csv(unlabeled_csv_path, index=False)

		# 3. Import Dataset (locks project raw_schema)
		res_imp = client.post(
			"/api/v1/datasets/import",
			json={
				"file_path": train_csv_path,
				"dataset_name": "ecommerce_raw_ds",
				"project_id": project_id,
			},
		)
		assert res_imp.status_code == 201, res_imp.text
		dataset_id = res_imp.json()["data"]["dataset"]["dataset_id"]

		# 4. Schema Mapping (transaction_id -> event_id, transaction_time -> timestamp, is_fraud -> label)
		res_map = client.post(
			f"/api/v1/datasets/{dataset_id}/schema-mapping",
			json={
				"event_id_column": "transaction_id",
				"time_column": "transaction_time",
				"amount_column": "amount",
				"user_id_column": "user_id",
				"target_column": "is_fraud",
				"optional_columns": {
					"country": "country",
					"channel": "channel",
				},
			},
		)
		assert res_map.status_code == 201, res_map.text
		mapped_art = res_map.json()["data"]
		assert "column_mapping" in mapped_art["validation_report"]

		# 5. Execute Feature Engineering with Velocity Features enabled
		res_fe = client.post(
			f"/api/v1/datasets/{dataset_id}/feature-engineering",
			json={
				"enable_velocity_features": True,
				"velocity_windows": [1, 24, 168],
				"enable_amount_ratios": False,
				"enable_hour_of_day": False,
			},
		)
		assert res_fe.status_code == 201, res_fe.text
		fe_artifact_id = res_fe.json()["data"]["artifact_id"]

		# 6. Train Built-in Random Forest Model & Activate Version
		res_models = client.get("/api/v1/training/models")
		rf_model = next(m for m in res_models.json()["data"] if m["model_name"] == "random_forest")

		res_run = client.post(
			"/api/v1/training/runs",
			json={
				"project_id": project_id,
				"model_id": rf_model["model_id"],
				"dataset_artifact_id": fe_artifact_id,
				"hyperparameters": {"n_estimators": 10},
				"run_name": "rf-velocity-run",
			},
		)
		assert res_run.status_code == 201, res_run.text
		version_id = res_run.json()["data"]["version_id"]

		res_act = client.post(
			f"/api/v1/training/versions/{version_id}/activate",
			json={"decision_threshold": 0.4, "description": "Approved RF with velocity features"},
		)
		assert res_act.status_code == 200, res_act.text

		# 7. Run Detection Job on unlabeled RAW CSV (with 'transaction_time' and 'transaction_id')
		res_job = client.post(
			"/api/v1/detection/jobs",
			json={
				"project_id": project_id,
				"input_file_path": unlabeled_csv_path,
				"model_version_id": version_id,
				"score_threshold": 0.4,
				"use_rules": False,
				"job_name": "Velocity-RAW-Batch-Scan",
			},
		)
		assert res_job.status_code == 201, res_job.text
		job_data = res_job.json()["data"]
		assert job_data["status"] == "COMPLETED", f"Job failed with: {job_data.get('error_message')}"
		assert job_data["total_records"] == 20

