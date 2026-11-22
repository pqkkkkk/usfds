"""ISS-012: Project Fact Warehouse — one normalized, append-only fact file per completed DetectionJob."""
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pandas as pd
import pytest

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus
from usfds_core.domain.schemas.inference_payload import BatchInferenceResult
from usfds_core.repositories.in_memory_repos import InMemoryDetectionJobRepository
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.warehouse.project_warehouse import ProjectWarehouse, create_bounded_duckdb_connection
from usfds_core.storage.base_storage import IFileStorage


class _MemoryStorage(IFileStorage):
	def __init__(self):
		self.files: dict[str, bytes] = {}

	def save_bytes(self, file_path, data):
		self.files[file_path] = data
		return file_path

	def read_bytes(self, file_path):
		return self.files[file_path]

	def exists(self, file_path):
		return file_path in self.files


def _predictions(rows: list[dict]) -> bytes:
	import io

	buf = io.BytesIO()
	pd.DataFrame(rows).to_parquet(buf, index=False)
	return buf.getvalue()


def _row(event_id, score, ts="2026-11-01T02:15:00Z", amount=100.0, rules=None, label=None):
	row = {
		"event_id": event_id, "user_id": f"U-{event_id}", "timestamp": ts, "amount": amount,
		"model_score": score, "rule_action": "REJECT" if rules else "ALLOW",
		"final_action": "REVIEW" if score >= 0.5 else "ALLOW",
		"triggered_rules": json.dumps(rules or []),
	}
	if label is not None:
		row["label"] = label
	return row


def _job(project_id, storage, rows, created_at, name):
	job_id = uuid4()
	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.save_bytes(path, _predictions(rows))
	return DetectionJob(
		job_id=job_id, project_id=project_id, job_name=name, output_path=path,
		status=DetectionJobStatus.COMPLETED, score_threshold=0.5, created_at=created_at,
	)


@pytest.fixture
def no_pandas_parquet_read(monkeypatch):
	def _blocked(*args, **kwargs):
		raise AssertionError("pd.read_parquet must not be used (ISS-012)")

	monkeypatch.setattr(pd, "read_parquet", _blocked)


def _load_facts(storage, jobs, **kwargs):
	conn = create_bounded_duckdb_connection()
	ProjectWarehouse(storage).load_fact_table(conn, jobs, **kwargs)
	return conn


def test_warehouse_writes_one_file_per_job_and_dedupes_latest_scan(no_pandas_parquet_read):
	storage = _MemoryStorage()
	repo = InMemoryDetectionJobRepository()
	service = InferenceService(file_storage=storage, detection_job_repo=repo)
	project_id = uuid4()
	t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
	old = _job(project_id, storage, [_row("TX-1", 0.20), _row("TX-2", 0.10, rules=["R1"])], t0, "old")
	new = _job(project_id, storage, [_row("TX-1", 0.90)], t0 + timedelta(days=1), "new")
	for job in (old, new):
		repo.save(job)
		service.handle_job_completion(BatchInferenceResult(job_id=job.job_id, is_success=True, output_path=job.output_path))

	keys = sorted(k for k in storage.files if k.startswith(f"warehouse/{project_id}/fact_transactions/"))
	assert keys == sorted(f"warehouse/{project_id}/fact_transactions/job_{j.job_id}.parquet" for j in (old, new))

	conn = _load_facts(storage, [old, new])
	rows = {r[0]: r for r in conn.execute("SELECT event_id, model_score, job_name, rule_codes FROM facts").fetchall()}
	assert set(rows) == {"TX-1", "TX-2"}
	assert rows["TX-1"][1] == pytest.approx(0.90) and rows["TX-1"][2] == "new"  # latest scan wins
	assert rows["TX-2"][3] == ["R1"]
	assert conn.execute("SELECT current_setting('threads')").fetchone()[0] == 2
	assert conn.execute("SELECT current_setting('memory_limit')").fetchone()[0].endswith("MiB")


def test_warehouse_bootstraps_legacy_completed_jobs(no_pandas_parquet_read):
	storage = _MemoryStorage()
	project_id = uuid4()
	t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
	legacy = _job(project_id, storage, [_row("TX-1", 0.3, label=1), _row("TX-2", 0.8, label=0)], t0, "legacy")
	warehouse = ProjectWarehouse(storage)
	assert not any(k.startswith("warehouse/") for k in storage.files)

	assert warehouse.sync_missing_jobs([legacy]) == 1
	assert warehouse.sync_missing_jobs([legacy]) == 0  # second call creates nothing

	conn = _load_facts(storage, [legacy])
	assert conn.execute("SELECT COUNT(*), SUM(dataset_label), BOOL_AND(has_label_col) FROM facts").fetchone() == (2, 1, True)


def test_warehouse_load_filters_by_tx_timestamp_not_job_date(no_pandas_parquet_read):
	storage = _MemoryStorage()
	project_id = uuid4()
	job = _job(
		project_id, storage,
		[_row("TX-A", 0.5, ts="2026-10-01T10:00:00Z"), _row("TX-B", 0.5, ts="2026-11-15T10:00:00Z"), _row("TX-C", 0.5, ts="2026-12-20T10:00:00Z")],
		datetime(2026, 12, 25, tzinfo=timezone.utc), "dec-scan",
	)
	ProjectWarehouse(storage).sync_missing_jobs([job])

	conn = _load_facts(
		storage, [job],
		date_from=datetime(2026, 11, 1, tzinfo=timezone.utc), date_to=datetime(2026, 11, 30, tzinfo=timezone.utc),
	)
	assert [r[0] for r in conn.execute("SELECT event_id FROM facts").fetchall()] == ["TX-B"]
