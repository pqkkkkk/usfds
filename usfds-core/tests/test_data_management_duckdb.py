import csv
import hashlib
import io
from uuid import uuid4

import pandas as pd
import pytest

from usfds_core.domain.entities.enums import LogicalDataType, ValidationStatus
from usfds_core.domain.entities.system import Project
from usfds_core.repositories.in_memory_repos import (
	InMemoryDatasetArtifactRepository,
	InMemoryDatasetRepository,
	InMemoryProjectRepository,
)
from usfds_core.services.data_management.ingestion import DatasetIngestionService
from usfds_core.storage.in_memory_storage import InMemoryFileStorage


def test_ingestion_schema_lock_strip_extra_and_profiling_use_duckdb_without_pandas(tmp_path, monkeypatch):
	"""ISS-044 (M1): Ingestion, RAW schema lock/validation, extra-column stripping and profiling run via DuckDB without pandas."""
	storage = InMemoryFileStorage()
	project_repo = InMemoryProjectRepository()
	dataset_repo = InMemoryDatasetRepository()
	artifact_repo = InMemoryDatasetArtifactRepository()
	project_id = uuid4()
	user_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=user_id, project_name="DuckDB Ingest Proj"))

	ds1_path = tmp_path / "ds1.csv"
	ds1_path.write_text(
		"tx_id,tx_amount,merchant_cat,is_fraud,nullable_note\n"
		"T1,100,FOOD,0,ok\n"
		"T2,200,TECH,1,\n"
		"T3,300,FOOD,0,note\n",
		encoding="utf-8",
	)
	ds1_sha = hashlib.sha256(ds1_path.read_bytes()).hexdigest()

	ds2_path = tmp_path / "ds2.csv"
	ds2_path.write_text(
		"tx_id,tx_amount,merchant_cat,nullable_note,extra_col\n"
		"T4,150.5,TECH,,x1\n"
		"T5,,TRAVEL,,x2\n",
		encoding="utf-8",
	)

	ds_pq_path = tmp_path / "ds_pq.parquet"
	pd.DataFrame(
		{
			"tx_id": ["T6", "T7"],
			"tx_amount": [400.0, 500.0],
			"merchant_cat": ["FOOD", "TECH"],
			"is_fraud": [0, 1],
			"nullable_note": ["a", None],
			"extra_col": ["e1", "e2"],
		}
	).to_parquet(ds_pq_path, index=False)

	ds_bad_path = tmp_path / "ds_bad.csv"
	ds_bad_path.write_text(
		"tx_id,tx_amount,merchant_cat,is_fraud,nullable_note\n"
		"T8,bad_num,FOOD,0,ok\n"
		"T9,not_a_num,TECH,1,ok\n",
		encoding="utf-8",
	)

	def _forbid_pandas(*args, **kwargs):
		raise AssertionError("pandas full-file load forbidden in ISS-044")

	monkeypatch.setattr(pd, "read_csv", _forbid_pandas)
	monkeypatch.setattr(pd, "read_parquet", _forbid_pandas)
	monkeypatch.setattr(pd, "read_json", _forbid_pandas)

	service = DatasetIngestionService(
		file_storage=storage,
		artifact_repo=artifact_repo,
		dataset_repo=dataset_repo,
		project_repo=project_repo,
	)

	ds1, art1 = service.import_dataset(
		file_path=ds1_path,
		dataset_name="ds1",
		project_id=project_id,
		user_id=user_id,
	)
	locked_project = project_repo.get_by_id(project_id)
	assert locked_project is not None
	assert locked_project.is_schema_locked is True
	cols_spec = locked_project.raw_schema["columns"]
	assert cols_spec["tx_amount"]["logical_type"] == LogicalDataType.NUMERIC.value
	assert cols_spec["merchant_cat"]["logical_type"] == LogicalDataType.STRING.value
	assert cols_spec["nullable_note"]["nullable"] is True
	assert cols_spec["tx_id"]["nullable"] is False
	assert art1.checksum_sha256 == ds1_sha
	assert art1.row_count == 3
	assert art1.column_count == 5
	assert art1.validation_status == ValidationStatus.PASSED
	prof1 = art1.validation_report["profiling"]
	assert prof1["row_count"] == 3
	assert prof1["field_count"] == 5
	note_prof = next(f for f in prof1["fields"] if f["name"] == "nullable_note")
	assert note_prof["null_count"] == 1
	assert note_prof["null_percentage"] == 33.33
	assert note_prof["unique_count"] == 2

	ds2, art2 = service.import_dataset(
		file_path=ds2_path,
		dataset_name="ds2",
		project_id=project_id,
		user_id=user_id,
	)
	assert art2.validation_status == ValidationStatus.WARNING
	assert art2.column_count == 4
	sv2 = art2.validation_report["schema_validation"]
	assert sv2["inferred_unlabeled_inference"] is True
	assert sv2["extra_columns"] == ["extra_col"]
	persisted_csv = storage.read_bytes(art2.storage_path).decode("utf-8")
	rows2 = list(csv.reader(io.StringIO(persisted_csv)))
	assert rows2[0] == ["tx_id", "tx_amount", "merchant_cat", "nullable_note"]
	assert len(rows2) == 3
	assert art2.checksum_sha256 == hashlib.sha256(storage.read_bytes(art2.storage_path)).hexdigest()

	ds_pq, art_pq = service.import_dataset(
		file_path=ds_pq_path,
		dataset_name="ds_pq",
		project_id=project_id,
		user_id=user_id,
	)
	assert art_pq.validation_status == ValidationStatus.WARNING
	assert art_pq.column_count == 5
	assert "extra_col" not in art_pq.schema_snapshot

	stored_before_bad = set(storage.list_files("datasets/"))
	with pytest.raises(ValueError, match="tx_amount"):
		service.import_dataset(
			file_path=ds_bad_path,
			dataset_name="ds_bad",
			project_id=project_id,
			user_id=user_id,
		)
	assert set(storage.list_files("datasets/")) == stored_before_bad
