import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
from uuid import uuid4

import pandas as pd
import pytest

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import (
	ColumnMlRole,
	LogicalDataType,
	PipelineStage,
	ValidationStatus,
)
from usfds_core.domain.entities.system_metadata import SystemColumnMetadata
from usfds_core.domain.entities.system import Project
from usfds_core.domain.schemas.preprocessing_config import (
	DataMappingConfig,
	SupportedTimeFormat,
)
from usfds_core.repositories.in_memory_repos import (
	InMemoryDatasetArtifactRepository,
	InMemoryDatasetRepository,
	InMemoryProjectRepository,
)
from usfds_core.services.data_management.ingestion import DatasetIngestionService
from usfds_core.services.data_management.mapping import DataMappingService
from usfds_core.services.data_management.validation import DataQualityValidationService
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


class _StaticMetadataRepo:
	def __init__(self, items):
		self._items = items

	def list_all(self, include_inactive: bool = False):
		return list(self._items)


def test_mapping_and_quality_validation_use_duckdb_without_pandas(tmp_path, monkeypatch):
	"""ISS-044 (M2): Schema mapping and quality validation run via DuckDB with full parity against pandas validation."""
	storage = InMemoryFileStorage()
	artifact_repo = InMemoryDatasetArtifactRepository()
	metadata_repo = _StaticMetadataRepo(
		[
			SystemColumnMetadata(
				column_key="risk_hint",
				display_name="Risk Hint",
				logical_type=LogicalDataType.NUMERIC,
				is_required=False,
				ml_role=ColumnMlRole.FEATURE,
			),
			SystemColumnMetadata(
				column_key="kyc_verified",
				display_name="KYC Verified",
				logical_type=LogicalDataType.BOOLEAN,
				is_required=False,
				ml_role=ColumnMlRole.FEATURE,
			),
			SystemColumnMetadata(
				column_key="signup_at",
				display_name="Signup At",
				logical_type=LogicalDataType.DATETIME,
				is_required=False,
				ml_role=ColumnMlRole.FEATURE,
			),
			SystemColumnMetadata(
				column_key="channel_note",
				display_name="Channel Note",
				logical_type=LogicalDataType.STRING,
				is_required=False,
				ml_role=ColumnMlRole.IDENTIFIER,
			),
		]
	)
	service = DataMappingService(
		file_storage=storage,
		artifact_repo=artifact_repo,
		metadata_repo=metadata_repo,
	)
	dataset_id = uuid4()

	future_ts = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
	rows = [
		["E1", "2024-01-01 10:00:00", "100.0", "U1", "0", "0.1", "true", "2024-01-01 09:00:00", "web"],
		["E1", "2024-01-01 10:00:00", "100.0", "U1", "0", "0.1", "true", "2024-01-01 09:00:00", "web"],
		["E2", "2024-01-01 10:05:00", "-5.0", "U2", "1", "0.5", "0", "2024-01-01 09:05:00", "mobile"],
		["E3", future_ts, "0.0", "U3", "0", "", "yes", "", ""],
		["E4", "2024-01-01 10:15:00", "1000000.0", "U4", "1", "0.9", "false", "2024-01-01 09:15:00", "pos"],
	]
	for i in range(5, 25):
		rows.append([f"E{i}", f"2024-01-01 10:{i:02d}:00", str(10.0 + i), f"U{i % 4}", "0", "0.2", "no", "2024-01-01 08:00:00", "web"])

	raw_csv = tmp_path / "raw_auto.csv"
	with open(raw_csv, "w", newline="", encoding="utf-8") as f:
		writer = csv.writer(f)
		writer.writerow(["tx_id", "tx_time", "tx_amt", "cust_id", "is_fraud", "raw_risk", "raw_kyc", "raw_signup", "raw_note"])
		writer.writerows(rows)
	storage.save_bytes(f"datasets/{dataset_id}/raw/raw_auto.csv", raw_csv.read_bytes())
	raw_art_auto = DatasetArtifact(
		dataset_id=dataset_id,
		pipeline_stage=PipelineStage.RAW,
		storage_path=f"datasets/{dataset_id}/raw/raw_auto.csv",
		output_paths={"raw": f"datasets/{dataset_id}/raw/raw_auto.csv"},
	)

	# Extra formats: epoch_s, epoch_ms, custom strftime, and invalid threshold violations
	epoch_s_path = tmp_path / "epoch_s.csv"
	epoch_s_path.write_text(
		"tx_id,tx_time,tx_amt,cust_id,is_fraud\n"
		"E1,1704110400,50,U1,0\n"
		"E2,1704110460,60,U2,1\n",
		encoding="utf-8",
	)
	storage.save_bytes(f"datasets/{dataset_id}/raw/epoch_s.csv", epoch_s_path.read_bytes())
	raw_epoch_s = DatasetArtifact(
		dataset_id=dataset_id,
		pipeline_stage=PipelineStage.RAW,
		storage_path=f"datasets/{dataset_id}/raw/epoch_s.csv",
		output_paths={"raw": f"datasets/{dataset_id}/raw/epoch_s.csv"},
	)

	epoch_ms_path = tmp_path / "epoch_ms.csv"
	epoch_ms_path.write_text(
		"tx_id,tx_time,tx_amt,cust_id,is_fraud\n"
		"E1,1704110400000,50,U1,0\n"
		"E2,1704110460000,60,U2,1\n",
		encoding="utf-8",
	)
	storage.save_bytes(f"datasets/{dataset_id}/raw/epoch_ms.csv", epoch_ms_path.read_bytes())
	raw_epoch_ms = DatasetArtifact(
		dataset_id=dataset_id,
		pipeline_stage=PipelineStage.RAW,
		storage_path=f"datasets/{dataset_id}/raw/epoch_ms.csv",
		output_paths={"raw": f"datasets/{dataset_id}/raw/epoch_ms.csv"},
	)

	custom_path = tmp_path / "custom.csv"
	custom_path.write_text(
		"tx_id,tx_time,tx_amt,cust_id,is_fraud\n"
		"E1,01/05/2024 14:30,50,U1,0\n"
		"E2,02/05/2024 15:45,60,U2,1\n",
		encoding="utf-8",
	)
	storage.save_bytes(f"datasets/{dataset_id}/raw/custom.csv", custom_path.read_bytes())
	raw_custom = DatasetArtifact(
		dataset_id=dataset_id,
		pipeline_stage=PipelineStage.RAW,
		storage_path=f"datasets/{dataset_id}/raw/custom.csv",
		output_paths={"raw": f"datasets/{dataset_id}/raw/custom.csv"},
	)

	bad_bool_path = tmp_path / "bad_bool.csv"
	bad_bool_path.write_text(
		"tx_id,tx_time,tx_amt,cust_id,is_fraud,raw_kyc\n"
		"E1,2024-01-01 10:00:00,50,U1,0,maybe\n"
		"E2,2024-01-01 10:05:00,60,U2,1,unknown\n",
		encoding="utf-8",
	)
	storage.save_bytes(f"datasets/{dataset_id}/raw/bad_bool.csv", bad_bool_path.read_bytes())
	raw_bad_bool = DatasetArtifact(
		dataset_id=dataset_id,
		pipeline_stage=PipelineStage.RAW,
		storage_path=f"datasets/{dataset_id}/raw/bad_bool.csv",
		output_paths={"raw": f"datasets/{dataset_id}/raw/bad_bool.csv"},
	)

	def _forbid_pandas(*args, **kwargs):
		raise AssertionError("pandas full-file load forbidden in ISS-044")

	with monkeypatch.context() as mp:
		mp.setattr(pd, "read_csv", _forbid_pandas)
		mp.setattr(pd, "read_parquet", _forbid_pandas)
		mp.setattr(pd, "read_json", _forbid_pandas)

		mapped_auto = service.map_dataset(
			dataset_id,
			raw_art_auto,
			DataMappingConfig(
				event_id_column="tx_id",
				time_column="tx_time",
				amount_column="tx_amt",
				user_id_column="cust_id",
				target_column="is_fraud",
				optional_columns={
					"raw_risk": "risk_hint",
					"raw_kyc": "kyc_verified",
					"raw_signup": "signup_at",
					"raw_note": "channel_note",
				},
				time_format=SupportedTimeFormat.AUTO,
			),
		)
		mapped_es = service.map_dataset(
			dataset_id,
			raw_epoch_s,
			DataMappingConfig(
				event_id_column="tx_id",
				time_column="tx_time",
				amount_column="tx_amt",
				user_id_column="cust_id",
				target_column="is_fraud",
				time_format=SupportedTimeFormat.EPOCH_SECONDS,
			),
		)
		mapped_em = service.map_dataset(
			dataset_id,
			raw_epoch_ms,
			DataMappingConfig(
				event_id_column="tx_id",
				time_column="tx_time",
				amount_column="tx_amt",
				user_id_column="cust_id",
				target_column="is_fraud",
				time_format=SupportedTimeFormat.EPOCH_MILLIS,
			),
		)
		mapped_custom = service.map_dataset(
			dataset_id,
			raw_custom,
			DataMappingConfig(
				event_id_column="tx_id",
				time_column="tx_time",
				amount_column="tx_amt",
				user_id_column="cust_id",
				target_column="is_fraud",
				time_format="%d/%m/%Y %H:%M",
			),
		)
		with pytest.raises(ValueError, match="BOOLEAN"):
			service.map_dataset(
				dataset_id,
				raw_bad_bool,
				DataMappingConfig(
					event_id_column="tx_id",
					time_column="tx_time",
					amount_column="tx_amt",
					user_id_column="cust_id",
					target_column="is_fraud",
					optional_columns={"raw_kyc": "kyc_verified"},
					max_invalid_ratio_allowed=0.05,
				),
			)

	# Verify generated Parquets & exact parity with pandas DataQualityValidationService
	mapped_df = pd.read_parquet(io.BytesIO(storage.read_bytes(mapped_auto.output_paths["mapped"])))
	expected_report = DataQualityValidationService().validate(mapped_df).to_dict()
	actual_report = mapped_auto.validation_report

	for key in (
		"quality_score",
		"rating",
		"validation_status",
		"total_rows",
		"total_columns",
		"duplicate_rows_count",
		"duplicate_event_ids_count",
		"non_positive_amount_count",
		"future_timestamp_count",
		"amount_outliers_count",
	):
		assert actual_report[key] == expected_report[key], f"Mismatch on {key}"
	assert actual_report["amount_q999"] == pytest.approx(expected_report["amount_q999"])
	assert len(actual_report["sample_records"]) == len(expected_report["sample_records"])
	for col, exp_m in expected_report["column_metrics"].items():
		act_m = actual_report["column_metrics"][col]
		assert act_m["null_count"] == exp_m["null_count"]
		assert act_m["null_percentage"] == exp_m["null_percentage"]
		assert act_m["unique_count"] == exp_m["unique_count"]

	es_df = pd.read_parquet(io.BytesIO(storage.read_bytes(mapped_es.output_paths["mapped"])))
	em_df = pd.read_parquet(io.BytesIO(storage.read_bytes(mapped_em.output_paths["mapped"])))
	cu_df = pd.read_parquet(io.BytesIO(storage.read_bytes(mapped_custom.output_paths["mapped"])))
	assert es_df["timestamp"].iloc[0] == "2024-01-01 12:00:00"
	assert em_df["timestamp"].iloc[0] == "2024-01-01 12:00:00"
	assert cu_df["timestamp"].iloc[0] == "2024-05-01 14:30:00"

