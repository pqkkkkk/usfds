"""Queue-mode API tests: router -> InlineJobQueue (JSON payload) -> worker handler -> shared DB/storage.

Reference examples for testing `if settings.dispatch_backend == "queue"` branches without BullMQ/PostgreSQL.
"""
from pathlib import Path
from uuid import uuid4

import pandas as pd

from usfds_infra.job_queue import JOB_DATASET_INGESTION, QUEUE_DATA_PIPELINE


def _write_raw_csv(storage_dir: str) -> Path:
	raw_df = pd.DataFrame({
		"TransactionID": [f"TX_{i:04d}" for i in range(20)],
		"TxAmount": [10.0 + i for i in range(20)],
		"IsFraud": [0] * 18 + [1] * 2,
	})
	csv_path = Path(storage_dir) / "queue_source.csv"
	csv_path.parent.mkdir(parents=True, exist_ok=True)
	raw_df.to_csv(csv_path, index=False)
	return csv_path


def _import_payload(csv_path: Path) -> dict:
	return {
		"file_path": str(csv_path),
		"dataset_name": "queue_dataset",
		"display_name": "Queue Dataset",
		"project_id": str(uuid4()),
		"user_id": str(uuid4()),
		"data_classification": "CONFIDENTIAL",
	}


def test_import_dataset_in_queue_mode_runs_worker_ingestion_handler(client_queue_mode, server_settings):
	csv_path = _write_raw_csv(server_settings.storage_dir)

	res = client_queue_mode.post("/api/v1/datasets/import", json=_import_payload(csv_path))

	assert res.status_code == 201, res.text
	data = res.json()["data"]
	assert data["dataset"]["dataset_name"] == "queue_dataset"
	assert data["artifacts"][0]["pipeline_stage"] == "RAW"
	assert data["artifacts"][0]["row_count"] == 20
	jobs = client_queue_mode.job_queue.jobs
	assert [(j["queue"], j["name"], j["state"]) for j in jobs] == [
		(QUEUE_DATA_PIPELINE, JOB_DATASET_INGESTION, "completed"),
	]
	# The dataset written by the worker handler is visible through the API (same DB).
	res_get = client_queue_mode.get(f"/api/v1/datasets/{data['dataset']['dataset_id']}")
	assert res_get.status_code == 200, res_get.text


def test_import_dataset_in_queue_mode_maps_worker_value_error_to_400(client_queue_mode, server_settings):
	csv_path = _write_raw_csv(server_settings.storage_dir)
	payload = _import_payload(csv_path)
	assert client_queue_mode.post("/api/v1/datasets/import", json=payload).status_code == 201

	res_dup = client_queue_mode.post("/api/v1/datasets/import", json=payload)

	assert res_dup.status_code == 400, res_dup.text
	assert client_queue_mode.job_queue.jobs[-1]["state"] == "failed"
	assert client_queue_mode.job_queue.jobs[-1]["failed_reason"].startswith("ValueError:")
