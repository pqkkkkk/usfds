"""M1 acceptance tests for System Metadata Management (ISS-007) & Alias Consolidation (ISS-027)."""
import io
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import pandas as pd
import pytest

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import (
	ColumnCategory,
	ColumnMlRole,
	LogicalDataType,
	PipelineStage,
	ValidationStatus,
)
from usfds_core.domain.entities.system_metadata import SystemColumnMetadata
from usfds_core.domain.schemas.preprocessing_config import (
	DataMappingConfig,
	FeatureEngineeringConfig,
	PreprocessingConfig,
	SplitConfig,
	SystemColumn,
)
from usfds_core.domain.schemas.system_metadata import (
	DEFAULT_SYSTEM_COLUMN_ALIASES,
	build_default_system_columns,
	resolve_canonical_column,
)
from usfds_core.repositories.base_system_metadata_repo import ISystemColumnMetadataRepository
from usfds_core.services.data_management.mapping import DataMappingService
from usfds_core.services.data_management.system_metadata_service import SystemMetadataService
from usfds_core.services.inference.executor import prepare_and_validate_input
from usfds_core.services.preprocessing.feature_engineering.credit_card_engineer import (
	CreditCardFeatureEngineer,
)
from usfds_core.services.preprocessing.feature_engineering.velocity_engineer import (
	VelocityFeatureEngineer,
)
from usfds_core.services.preprocessing.feature_engineering_service import (
	FeatureEngineeringExecutionService,
)
from usfds_core.services.preprocessing.pipeline_builder import PreprocessingPipelineBuilder
from usfds_core.services.preprocessing.preprocessing_service import PreprocessingExecutionService
from usfds_core.services.preprocessing.splitters.temporal_splitter import TemporalDataSplitter
from usfds_core.services.rule_engine.executor import RuleExecutor
from usfds_core.storage.in_memory_storage import InMemoryFileStorage


class _InMemorySystemMetadataRepository(ISystemColumnMetadataRepository):
	"""Lightweight in-memory repo for pure core tests (no usfds_infra imports)."""

	def __init__(self, initial: Optional[List[SystemColumnMetadata]] = None) -> None:
		self._items: Dict[UUID, SystemColumnMetadata] = {}
		for item in (initial if initial is not None else build_default_system_columns()):
			self._items[item.metadata_id] = item

	def list_all(self, include_inactive: bool = False) -> List[SystemColumnMetadata]:
		items = list(self._items.values())
		if not include_inactive:
			items = [m for m in items if m.is_active]
		return sorted(items, key=lambda m: (m.display_order, m.column_key))

	def get_by_id(self, metadata_id: UUID) -> Optional[SystemColumnMetadata]:
		return self._items.get(metadata_id)

	def get_by_key(self, column_key: str) -> Optional[SystemColumnMetadata]:
		key_lower = column_key.strip().lower()
		for item in self._items.values():
			if item.column_key.lower() == key_lower:
				return item
		return None

	def save(self, metadata: SystemColumnMetadata) -> SystemColumnMetadata:
		self._items[metadata.metadata_id] = metadata
		return metadata

	def delete(self, metadata_id: UUID) -> None:
		self._items.pop(metadata_id, None)


def _save_raw_artifact(storage: InMemoryFileStorage, dataset_id: UUID, df: pd.DataFrame) -> DatasetArtifact:
	raw_path = f"datasets/{dataset_id}/raw/raw.parquet"
	buf = io.BytesIO()
	df.to_parquet(buf, index=False)
	storage.save_bytes(raw_path, buf.getvalue())
	return DatasetArtifact(
		artifact_id=uuid4(),
		dataset_id=dataset_id,
		pipeline_stage=PipelineStage.RAW,
		storage_path=raw_path,
		output_paths={"raw": raw_path},
		validation_status=ValidationStatus.PASSED,
		row_count=len(df),
		column_count=len(df.columns),
	)


def test_resolve_canonical_column_unifies_aliases_across_modules():
	"""ISS-027: All core modules resolve canonical system columns from DEFAULT_SYSTEM_COLUMN_ALIASES."""
	df = pd.DataFrame(
		{
			"TransactionID": ["TX1", "TX2", "TX3", "TX4", "TX5"],
			"TransactionDT": [1000, 2000, 3000, 4000, 5000],
			"TransactionAmt": [50.0, 120.0, 250.0, 15.0, 900.0],
			"CLIENTNUM": ["U1", "U1", "U2", "U2", "U1"],
			"isFraud": [0, 0, 1, 0, 1],
		}
	)

	# 1. Single source of truth resolver
	assert SystemColumn.EVENT_ID.value in DEFAULT_SYSTEM_COLUMN_ALIASES
	assert resolve_canonical_column(df, SystemColumn.EVENT_ID) == "TransactionID"
	assert resolve_canonical_column(df, SystemColumn.TIMESTAMP) == "TransactionDT"
	assert resolve_canonical_column(df, SystemColumn.AMOUNT) == "TransactionAmt"
	assert resolve_canonical_column(df, SystemColumn.USER_ID) == "CLIENTNUM"
	assert resolve_canonical_column(df, SystemColumn.LABEL) == "isFraud"

	# 2. prepare_and_validate_input fallback renaming
	prepared = prepare_and_validate_input(df, column_mapping={})
	for canonical in (
		SystemColumn.EVENT_ID.value,
		SystemColumn.TIMESTAMP.value,
		SystemColumn.AMOUNT.value,
		SystemColumn.USER_ID.value,
		SystemColumn.LABEL.value,
	):
		assert canonical in prepared.columns

	# 3. TemporalDataSplitter
	splitter = TemporalDataSplitter(SplitConfig(time_column="timestamp", target_column="label", test_size=0.4))
	X_train, X_test, y_train, y_test = splitter.split_features_target(df)
	assert len(X_train) == 3
	assert len(X_test) == 2
	assert list(y_train) == [0, 0, 1]
	assert list(y_test) == [0, 1]

	# 4. CreditCardFeatureEngineer
	cc_eng = CreditCardFeatureEngineer(time_col="timestamp", amount_col="amount")
	cc_out = cc_eng.fit_transform(df)
	assert "hour_of_day" in cc_out.columns
	assert "amount_to_mean_ratio" in cc_out.columns

	# 5. VelocityFeatureEngineer
	vel_eng = VelocityFeatureEngineer(user_id_col="user_id", time_col="timestamp", amount_col="amount", windows=[1])
	vel_out = vel_eng.fit_transform(df)
	assert "tx_freq_last_1h" in vel_out.columns
	assert "tx_sum_last_1h" in vel_out.columns

	# 6. RuleExecutor.backtest_dataframe
	rule_exec = RuleExecutor()
	bt = rule_exec.backtest_dataframe(
		df=df,
		condition={">": [{"var": "TransactionAmt"}, 200]},
	)
	assert bt.has_ground_truth is True
	assert bt.total_hits == 2
	assert bt.tp == 2
	assert bt.sample_hits[0].event_id == "TX3"
	assert bt.sample_hits[0].user_id == "U2"


def test_core_system_columns_are_immutable_while_aliases_are_editable():
	"""ISS-007: Core system columns cannot be deleted or structurally altered, while aliases & descriptions can be edited."""
	repo = _InMemorySystemMetadataRepository()
	service = SystemMetadataService(repo)

	event_id_meta = repo.get_by_key(SystemColumn.EVENT_ID.value)
	assert event_id_meta is not None
	assert event_id_meta.category == ColumnCategory.CORE

	# Deleting a CORE column must fail
	with pytest.raises(ValueError):
		service.delete_column(event_id_meta.metadata_id)

	# Disabling is_required or changing logical_type on CORE column must fail
	with pytest.raises(ValueError):
		service.update_column(event_id_meta.metadata_id, is_required=False)

	with pytest.raises(ValueError):
		service.update_column(event_id_meta.metadata_id, logical_type=LogicalDataType.NUMERIC)

	with pytest.raises(ValueError):
		service.update_column(event_id_meta.metadata_id, is_active=False)

	# Updating aliases and description succeeds and always retains "event_id"
	updated = service.update_column(
		event_id_meta.metadata_id,
		aliases=["tx_id", "ma_gd"],
		description="Mã giao dịch chuẩn hoá",
	)
	assert "event_id" in updated.aliases
	assert "tx_id" in updated.aliases
	assert "ma_gd" in updated.aliases
	assert updated.description == "Mã giao dịch chuẩn hoá"


def test_mapping_adapts_to_dynamic_domain_columns_and_identifier_role():
	"""ISS-007: DataMappingService enforces required DOMAIN columns, casts logical types, and excludes IDENTIFIER columns from ML OHE."""
	repo = _InMemorySystemMetadataRepository()
	meta_service = SystemMetadataService(repo)
	meta_service.create_column(
		column_key="device_id",
		display_name="Mã thiết bị",
		logical_type=LogicalDataType.STRING,
		is_required=True,
		ml_role=ColumnMlRole.IDENTIFIER,
		aliases=["dev_hash"],
	)
	meta_service.create_column(
		column_key="risk_hint",
		display_name="Điểm rủi ro sơ bộ",
		logical_type=LogicalDataType.NUMERIC,
		is_required=False,
		ml_role=ColumnMlRole.FEATURE,
		aliases=["risk_score_raw"],
	)

	storage = InMemoryFileStorage()
	dataset_id = uuid4()
	raw_df = pd.DataFrame(
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
			"acct": ["U1", "U2", "U3", "U4", "U5"],
			"is_fraud": [0, 0, 1, 0, 1],
			"dev_hash": ["DEV-A", "DEV-B", "DEV-C", "DEV-D", "DEV-E"],
			"risk_score_raw": ["0.1", "0.2", "0.9", "0.3", "0.8"],
			"category": ["retail", "travel", "retail", "food", "travel"],
		}
	)
	raw_art = _save_raw_artifact(storage, dataset_id, raw_df)
	mapping_service = DataMappingService(file_storage=storage, metadata_repo=repo)

	# Missing required DOMAIN column 'device_id' must fail
	incomplete_cfg = DataMappingConfig(
		event_id_column="tx_id",
		time_column="tx_time",
		amount_column="amt",
		user_id_column="acct",
		target_column="is_fraud",
		optional_columns={"risk_score_raw": "risk_hint"},
	)
	with pytest.raises(ValueError, match="device_id"):
		mapping_service.map_dataset(dataset_id, raw_art, incomplete_cfg)

	# Complete mapping succeeds, casts risk_hint -> float64, records device_id in non_ml_columns
	complete_cfg = DataMappingConfig(
		event_id_column="tx_id",
		time_column="tx_time",
		amount_column="amt",
		user_id_column="acct",
		target_column="is_fraud",
		optional_columns={
			"dev_hash": "device_id",
			"risk_score_raw": "risk_hint",
			"category": "category",
		},
	)
	mapped_art = mapping_service.map_dataset(dataset_id, raw_art, complete_cfg)

	mapped_df = pd.read_parquet(io.BytesIO(storage.read_bytes(mapped_art.output_paths["mapped"])))
	assert pd.api.types.is_float_dtype(mapped_df["risk_hint"])
	assert "device_id" in (mapped_art.validation_report or {}).get("non_ml_columns", [])

	# PreprocessingPipelineBuilder must exclude device_id from categorical OneHotEncoder
	pipeline = PreprocessingPipelineBuilder.build(
		PreprocessingConfig(),
		sample_df=mapped_df.drop(columns=["label"]),
		extra_non_ml_columns=mapped_art.validation_report["non_ml_columns"],
	)
	col_transformer = dict(pipeline.steps)["data_transformation"]
	cat_cols_used: List[str] = []
	for name, _, cols in col_transformer.transformers:
		if name == "cat_encoder":
			cat_cols_used.extend(cols)
	assert "device_id" not in cat_cols_used
	assert "category" in cat_cols_used


def test_existing_mapped_artifact_remains_valid_after_metadata_change():
	"""ISS-007: Forward-only snapshot policy keeps existing MAPPED artifacts working after admin changes metadata."""
	repo = _InMemorySystemMetadataRepository()
	meta_service = SystemMetadataService(repo)
	device_col = meta_service.create_column(
		column_key="device_id",
		display_name="Mã thiết bị",
		logical_type=LogicalDataType.STRING,
		is_required=True,
		ml_role=ColumnMlRole.IDENTIFIER,
		aliases=["dev_hash"],
	)

	storage = InMemoryFileStorage()
	dataset_id = uuid4()
	raw_df = pd.DataFrame(
		{
			"tx_id": [f"E{i}" for i in range(10)],
			"tx_time": [f"2026-01-01 0{i}:00:00" for i in range(10)],
			"amt": [10.0 * (i + 1) for i in range(10)],
			"acct": [f"U{i % 3}" for i in range(10)],
			"is_fraud": [0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
			"dev_hash": [f"DEV-{i}" for i in range(10)],
			"channel_raw": ["web", "mobile"] * 5,
		}
	)
	raw_art = _save_raw_artifact(storage, dataset_id, raw_df)
	mapping_service = DataMappingService(file_storage=storage, metadata_repo=repo)

	old_mapped_art = mapping_service.map_dataset(
		dataset_id,
		raw_art,
		DataMappingConfig(
			event_id_column="tx_id",
			time_column="tx_time",
			amount_column="amt",
			user_id_column="acct",
			target_column="is_fraud",
			optional_columns={"dev_hash": "device_id"},
		),
	)
	old_mapped_path = old_mapped_art.output_paths["mapped"]
	old_mapped_bytes = storage.read_bytes(old_mapped_path)

	# Admin now adds required 'channel' and deactivates 'device_id'
	meta_service.create_column(
		column_key="channel",
		display_name="Kênh giao dịch",
		logical_type=LogicalDataType.STRING,
		is_required=True,
		ml_role=ColumnMlRole.FEATURE,
		aliases=["channel_raw"],
	)
	meta_service.update_column(device_col.metadata_id, is_active=False)

	# Old MAPPED artifact must still run FE + Preprocessing using its snapshotted non_ml_columns
	fe_service = FeatureEngineeringExecutionService(file_storage=storage)
	fe_art = fe_service.execute(
		parent_artifact=old_mapped_art,
		config=FeatureEngineeringConfig(split=SplitConfig(test_size=0.2)),
	)
	assert fe_art.validation_status == ValidationStatus.PASSED
	assert "device_id" in (fe_art.validation_report or {}).get("non_ml_columns", [])

	prep_service = PreprocessingExecutionService(file_storage=storage)
	prep_art = prep_service.execute(parent_artifact=fe_art, config=PreprocessingConfig())
	assert prep_art.validation_status == ValidationStatus.PASSED
	assert "device_id" in (prep_art.validation_report or {}).get("dropped_identifier_columns", [])

	# Re-mapping creates a new immutable path with 'channel' and does NOT overwrite old mapped.parquet
	new_mapped_art = mapping_service.map_dataset(
		dataset_id,
		raw_art,
		DataMappingConfig(
			event_id_column="tx_id",
			time_column="tx_time",
			amount_column="amt",
			user_id_column="acct",
			target_column="is_fraud",
			optional_columns={"channel_raw": "channel"},
		),
	)
	assert new_mapped_art.output_paths["mapped"] != old_mapped_path
	assert storage.read_bytes(old_mapped_path) == old_mapped_bytes
