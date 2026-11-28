import io
import unittest
from uuid import uuid4
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import (
    DataMappingConfig,
    SupportedTimeFormat,
    SystemColumn,
)
from usfds_core.repositories.in_memory_repos import InMemoryDatasetArtifactRepository
from usfds_core.services.data_management.mapping import DataMappingService
from usfds_core.storage.in_memory_storage import InMemoryFileStorage


class TestDataMappingService(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryFileStorage()
        self.artifact_repo = InMemoryDatasetArtifactRepository()
        self.service = DataMappingService(
            file_storage=self.storage,
            artifact_repo=self.artifact_repo,
        )
        self.dataset_id = uuid4()

        # Standard sample dataframe
        self.raw_df = pd.DataFrame({
            "tx_id": [f"tx_{i}" for i in range(10)],
            "tx_time": [
                "2024-01-01 10:00:00",
                "2024-01-01 10:05:00",
                "2024-01-01 10:10:00",
                "2024-01-01 10:15:00",
                "2024-01-01 10:20:00",
                "2024-01-01 10:25:00",
                "2024-01-01 10:30:00",
                "2024-01-01 10:35:00",
                "2024-01-01 10:40:00",
                "2024-01-01 10:45:00",
            ],
            "tx_amount": [15.5, 20.0, 100.5, 45.0, 99.9, 120.0, 30.0, 50.0, 200.0, 75.0],
            "customer_id": ["c1", "c2", "c1", "c3", "c2", "c4", "c1", "c5", "c2", "c3"],
            "fraud_flag": [0, 0, 1, 0, 0, 0, 0, 0, 1, 0],
            "device": ["mobile", "web", "mobile", "pos", "web", "mobile", "web", "pos", "mobile", "web"],
            "extra_note": ["note"] * 10,
        })
        self.raw_storage_path = f"datasets/{self.dataset_id}/raw/data.csv"
        self._save_df_to_storage(self.raw_df, self.raw_storage_path)

        self.raw_artifact = DatasetArtifact(
            artifact_id=uuid4(),
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            change_type="RAW_INGESTION",
            storage_path=self.raw_storage_path,
            output_paths={"raw": self.raw_storage_path},
            row_count=10,
            column_count=7,
        )
        self.artifact_repo.save(self.raw_artifact)

    def _save_df_to_storage(self, df: pd.DataFrame, path: str):
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        self.storage.save_bytes(path, buf.getvalue().encode("utf-8"))

    def test_map_dataset_success_auto_timestamp(self):
        """Tests successful mapping with AUTO timestamp, optional column inclusion, and dropped unmapped columns."""
        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="tx_time",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
            optional_columns={"device": "device_type"},
            time_format=SupportedTimeFormat.AUTO,
        )

        artifact = self.service.map_dataset(
            dataset_id=self.dataset_id,
            parent_artifact=self.raw_artifact,
            mapping_config=config,
            user_name="analyst_alice",
        )

        # 1. Artifact metadata
        self.assertIsNotNone(artifact.artifact_id)
        self.assertEqual(artifact.dataset_id, self.dataset_id)
        self.assertEqual(artifact.parent_artifact_id, self.raw_artifact.artifact_id)
        self.assertEqual(artifact.pipeline_stage, PipelineStage.MAPPED)
        self.assertEqual(artifact.change_type, "DATA_MAPPING")
        self.assertEqual(artifact.created_by, "analyst_alice")
        self.assertIn("mapped", artifact.output_paths)
        self.assertTrue(self.storage.exists(artifact.output_paths["mapped"]))

        # 2. Verify Output Parquet DataFrame
        mapped_bytes = self.storage.read_bytes(artifact.output_paths["mapped"])
        mapped_df = pd.read_parquet(io.BytesIO(mapped_bytes))
        self.assertEqual(len(mapped_df), 10)

        # 5 core standardized fields present
        self.assertIn(SystemColumn.EVENT_ID.value, mapped_df.columns)
        self.assertIn(SystemColumn.TIMESTAMP.value, mapped_df.columns)
        self.assertIn(SystemColumn.AMOUNT.value, mapped_df.columns)
        self.assertIn(SystemColumn.USER_ID.value, mapped_df.columns)
        self.assertIn(SystemColumn.LABEL.value, mapped_df.columns)

        # Optional column included and renamed
        self.assertIn("device_type", mapped_df.columns)
        self.assertEqual(mapped_df["device_type"].tolist(), self.raw_df["device"].tolist())

        # Unmapped columns dropped
        self.assertNotIn("extra_note", mapped_df.columns)
        self.assertNotIn("tx_id", mapped_df.columns)

        # 3. Validation Report attached from DataQualityValidationService
        self.assertIsNotNone(artifact.validation_report)
        self.assertIn("quality_score", artifact.validation_report)
        self.assertEqual(artifact.validation_status, ValidationStatus.PASSED)

        # 4. Check persistence in repository
        persisted = self.artifact_repo.get_by_id(artifact.artifact_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.artifact_id, artifact.artifact_id)

    def test_map_dataset_with_epoch_seconds_timestamp(self):
        """Tests parsing timestamps formatted as integer epoch seconds."""
        # 1704110400 = 2024-01-01 12:00:00 UTC
        epoch_df = self.raw_df.copy()
        epoch_df["epoch_sec"] = [1704110400 + (i * 60) for i in range(10)]
        path = f"datasets/{self.dataset_id}/raw/epoch_sec.csv"
        self._save_df_to_storage(epoch_df, path)

        raw_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=path,
            output_paths={"raw": path},
        )

        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="epoch_sec",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
            time_format=SupportedTimeFormat.EPOCH_SECONDS,
        )

        artifact = self.service.map_dataset(self.dataset_id, raw_art, config)
        mapped_bytes = self.storage.read_bytes(artifact.output_paths["mapped"])
        mapped_df = pd.read_parquet(io.BytesIO(mapped_bytes))

        # Check timestamp format
        self.assertEqual(mapped_df[SystemColumn.TIMESTAMP.value].iloc[0], "2024-01-01 12:00:00")
        self.assertEqual(mapped_df[SystemColumn.TIMESTAMP.value].iloc[1], "2024-01-01 12:01:00")

    def test_map_dataset_with_epoch_millis_timestamp(self):
        """Tests parsing timestamps formatted as numeric epoch milliseconds."""
        # 1704110400000 = 2024-01-01 12:00:00 UTC
        epoch_df = self.raw_df.copy()
        epoch_df["epoch_ms"] = [(1704110400 + (i * 60)) * 1000 for i in range(10)]
        path = f"datasets/{self.dataset_id}/raw/epoch_ms.csv"
        self._save_df_to_storage(epoch_df, path)

        raw_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=path,
            output_paths={"raw": path},
        )

        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="epoch_ms",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
            time_format=SupportedTimeFormat.EPOCH_MILLIS,
        )

        artifact = self.service.map_dataset(self.dataset_id, raw_art, config)
        mapped_bytes = self.storage.read_bytes(artifact.output_paths["mapped"])
        mapped_df = pd.read_parquet(io.BytesIO(mapped_bytes))

        self.assertEqual(mapped_df[SystemColumn.TIMESTAMP.value].iloc[0], "2024-01-01 12:00:00")

    def test_map_dataset_with_custom_strftime_format(self):
        """Tests parsing timestamps with custom strftime format like %d/%m/%Y %H:%M."""
        custom_df = self.raw_df.copy()
        custom_df["custom_time"] = [f"{i+1:02d}/05/2024 14:30" for i in range(10)]
        path = f"datasets/{self.dataset_id}/raw/custom_time.csv"
        self._save_df_to_storage(custom_df, path)

        raw_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=path,
            output_paths={"raw": path},
        )

        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="custom_time",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
            time_format="%d/%m/%Y %H:%M",
        )

        artifact = self.service.map_dataset(self.dataset_id, raw_art, config)
        mapped_bytes = self.storage.read_bytes(artifact.output_paths["mapped"])
        mapped_df = pd.read_parquet(io.BytesIO(mapped_df := mapped_bytes))

        self.assertEqual(mapped_df[SystemColumn.TIMESTAMP.value].iloc[0], "2024-05-01 14:30:00")

    def test_rejects_parent_artifact_not_at_raw_stage(self):
        """Fails when parent artifact is not at RAW pipeline stage."""
        non_raw_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.MAPPED,  # Already MAPPED
            storage_path=self.raw_storage_path,
            output_paths={"mapped": self.raw_storage_path},
        )

        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="tx_time",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
        )

        with self.assertRaises(ValueError) as ctx:
            self.service.map_dataset(self.dataset_id, non_raw_art, config)
        self.assertIn("requires parent artifact at stage RAW", str(ctx.exception))

    def test_rejects_missing_mandatory_fields(self):
        """BR-DM-03: Fails when any of the 5 mandatory fields is missing or blank."""
        invalid_config = DataMappingConfig(
            event_id_column="",  # Blank event_id
            time_column="tx_time",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
        )

        with self.assertRaises(ValueError) as ctx:
            self.service.map_dataset(self.dataset_id, self.raw_artifact, invalid_config)
        self.assertIn("Chưa ánh xạ đầy đủ 5 trường dữ liệu bắt buộc", str(ctx.exception))
        self.assertIn("event_id", str(ctx.exception))

    def test_rejects_duplicate_column_mapping(self):
        """BR-DM-04: Fails when multiple standard fields map to the same source column."""
        duplicate_config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="tx_time",
            amount_column="tx_amount",
            user_id_column="tx_id",  # Duplicated tx_id mapped to both event_id and user_id!
            target_column="fraud_flag",
        )

        with self.assertRaises(ValueError) as ctx:
            self.service.map_dataset(self.dataset_id, self.raw_artifact, duplicate_config)
        self.assertIn("chỉ được ánh xạ tối đa với 1 cột nguồn duy nhất", str(ctx.exception))

    def test_rejects_non_existent_mandatory_source_column(self):
        """Fails when specified mandatory source column does not exist in raw data."""
        config = DataMappingConfig(
            event_id_column="non_existent_col",
            time_column="tx_time",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
        )

        with self.assertRaises(ValueError) as ctx:
            self.service.map_dataset(self.dataset_id, self.raw_artifact, config)
        self.assertIn("không tồn tại trong tập dữ liệu thô", str(ctx.exception))
        self.assertIn("non_existent_col", str(ctx.exception))

    def test_rejects_non_existent_optional_source_column(self):
        """Fails when specified optional column does not exist in raw data."""
        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="tx_time",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
            optional_columns={"missing_optional_col": "opt"},
        )

        with self.assertRaises(ValueError) as ctx:
            self.service.map_dataset(self.dataset_id, self.raw_artifact, config)
        self.assertIn("Cột nguồn tùy chọn 'missing_optional_col' không tồn tại", str(ctx.exception))

    def test_rejects_unparseable_timestamps_exceeding_threshold(self):
        """Fails when invalid/unparseable timestamps exceed max_invalid_ratio_allowed."""
        bad_time_df = self.raw_df.copy()
        # 5 out of 10 rows are invalid text -> 50% invalid > default 5%
        bad_time_df["bad_time"] = ["2024-01-01 10:00:00"] * 5 + ["invalid_date_abc"] * 5
        path = f"datasets/{self.dataset_id}/raw/bad_time.csv"
        self._save_df_to_storage(bad_time_df, path)

        raw_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=path,
            output_paths={"raw": path},
        )

        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="bad_time",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
            max_invalid_ratio_allowed=0.05,
        )

        with self.assertRaises(ValueError) as ctx:
            self.service.map_dataset(self.dataset_id, raw_art, config)
        self.assertIn("Cột nguồn thời gian không tương thích", str(ctx.exception))

    def test_rejects_invalid_amount_exceeding_threshold(self):
        """Fails when non-numeric amount values exceed max_invalid_ratio_allowed."""
        bad_amount_df = self.raw_df.copy()
        # 5 out of 10 are non-numeric strings
        bad_amount_df["bad_amount"] = [100.0] * 5 + ["one_hundred", "twenty", "N/A", "abc", "xyz"]
        path = f"datasets/{self.dataset_id}/raw/bad_amount.csv"
        self._save_df_to_storage(bad_amount_df, path)

        raw_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=path,
            output_paths={"raw": path},
        )

        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="tx_time",
            amount_column="bad_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
            max_invalid_ratio_allowed=0.05,
        )

        with self.assertRaises(ValueError) as ctx:
            self.service.map_dataset(self.dataset_id, raw_art, config)
        self.assertIn("Cột nguồn số tiền không tương thích với kiểu số", str(ctx.exception))

    def test_missing_storage_file_raises_filenotfound(self):
        """Fails with FileNotFoundError when raw file is missing from storage."""
        missing_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path="datasets/nonexistent/data.csv",
            output_paths={"raw": "datasets/nonexistent/data.csv"},
        )

        config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="tx_time",
            amount_column="tx_amount",
            user_id_column="customer_id",
            target_column="fraud_flag",
        )

        with self.assertRaises(FileNotFoundError):
            self.service.map_dataset(self.dataset_id, missing_art, config)

    def test_map_dataset_with_explicit_label_value_mapping(self):
        """ISS-047: Maps string, non-binary numeric, and many-to-one labels explicitly to canonical 0/1."""
        # Case 1: string labels ('fraud' / 'legit')
        str_df = self.raw_df.copy()
        str_df["fraud_flag"] = ["legit", "legit", "fraud", "legit", "fraud"] * 2
        str_path = f"datasets/{self.dataset_id}/raw/str_labels.csv"
        self._save_df_to_storage(str_df, str_path)
        str_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=str_path,
            output_paths={"raw": str_path},
        )
        str_mapping = {"fraud": 1, "legit": 0}
        mapped_str = self.service.map_dataset(
            self.dataset_id,
            str_art,
            DataMappingConfig(
                event_id_column="tx_id",
                time_column="tx_time",
                amount_column="tx_amount",
                user_id_column="customer_id",
                target_column="fraud_flag",
                label_value_mapping=str_mapping,
            ),
        )
        mapped_str_df = pd.read_parquet(io.BytesIO(self.storage.read_bytes(mapped_str.output_paths["mapped"])))
        self.assertEqual(mapped_str_df[SystemColumn.LABEL.value].tolist(), [0, 0, 1, 0, 1] * 2)
        self.assertEqual(mapped_str.validation_report.get("label_value_mapping"), str_mapping)

        # Case 2: numeric 1/2 labels
        num_df = self.raw_df.copy()
        num_df["fraud_flag"] = [1, 1, 2, 1, 2] * 2
        num_path = f"datasets/{self.dataset_id}/raw/num_labels.csv"
        self._save_df_to_storage(num_df, num_path)
        num_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=num_path,
            output_paths={"raw": num_path},
        )
        num_mapping = {"1": 0, "2": 1}
        mapped_num = self.service.map_dataset(
            self.dataset_id,
            num_art,
            DataMappingConfig(
                event_id_column="tx_id",
                time_column="tx_time",
                amount_column="tx_amount",
                user_id_column="customer_id",
                target_column="fraud_flag",
                label_value_mapping=num_mapping,
            ),
        )
        mapped_num_df = pd.read_parquet(io.BytesIO(self.storage.read_bytes(mapped_num.output_paths["mapped"])))
        self.assertEqual(mapped_num_df[SystemColumn.LABEL.value].tolist(), [0, 0, 1, 0, 1] * 2)
        self.assertEqual(mapped_num.validation_report.get("label_value_mapping"), num_mapping)

        # Case 3: many-to-one mapping ('chargeback', 'fraud' -> 1; 'ok' -> 0)
        m2o_df = self.raw_df.copy()
        m2o_df["fraud_flag"] = ["ok", "fraud", "chargeback", "ok", "ok"] * 2
        m2o_path = f"datasets/{self.dataset_id}/raw/m2o_labels.csv"
        self._save_df_to_storage(m2o_df, m2o_path)
        m2o_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=m2o_path,
            output_paths={"raw": m2o_path},
        )
        m2o_mapping = {"fraud": 1, "chargeback": 1, "ok": 0}
        mapped_m2o = self.service.map_dataset(
            self.dataset_id,
            m2o_art,
            DataMappingConfig(
                event_id_column="tx_id",
                time_column="tx_time",
                amount_column="tx_amount",
                user_id_column="customer_id",
                target_column="fraud_flag",
                label_value_mapping=m2o_mapping,
            ),
        )
        mapped_m2o_df = pd.read_parquet(io.BytesIO(self.storage.read_bytes(mapped_m2o.output_paths["mapped"])))
        self.assertEqual(mapped_m2o_df[SystemColumn.LABEL.value].tolist(), [0, 1, 1, 0, 0] * 2)
        self.assertEqual(mapped_m2o.validation_report.get("label_value_mapping"), m2o_mapping)

    def test_map_dataset_strict_canonical_binary_and_rejects_unmapped_values(self):
        """ISS-047: Strict canonical binary when label_value_mapping is None, fail-fast on any unmapped value, and invalid mapping validation."""
        # (a) Raw has 'fraud'/'legit' without label_value_mapping -> fail-fast ValueError with sample values
        str_df = self.raw_df.copy()
        str_df["fraud_flag"] = ["legit"] * 9 + ["fraud"]  # 10% minority class (< 30%), still must fail fast!
        str_path = f"datasets/{self.dataset_id}/raw/strict_reject.csv"
        self._save_df_to_storage(str_df, str_path)
        str_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=str_path,
            output_paths={"raw": str_path},
        )
        with self.assertRaises(ValueError) as ctx_a:
            self.service.map_dataset(
                self.dataset_id,
                str_art,
                DataMappingConfig(
                    event_id_column="tx_id",
                    time_column="tx_time",
                    amount_column="tx_amount",
                    user_id_column="customer_id",
                    target_column="fraud_flag",
                ),
            )
        msg_a = str(ctx_a.exception)
        self.assertTrue("fraud" in msg_a or "legit" in msg_a, msg_a)

        # (b) Raw has 'A','B','C' with partial mapping {"A": 1, "B": 0} -> fail-fast mentioning 'C'
        abc_df = self.raw_df.copy()
        abc_df["fraud_flag"] = ["A", "B", "B", "B", "B", "B", "B", "B", "B", "C"]
        abc_path = f"datasets/{self.dataset_id}/raw/abc_labels.csv"
        self._save_df_to_storage(abc_df, abc_path)
        abc_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=abc_path,
            output_paths={"raw": abc_path},
        )
        with self.assertRaises(ValueError) as ctx_b:
            self.service.map_dataset(
                self.dataset_id,
                abc_art,
                DataMappingConfig(
                    event_id_column="tx_id",
                    time_column="tx_time",
                    amount_column="tx_amount",
                    user_id_column="customer_id",
                    target_column="fraud_flag",
                    label_value_mapping={"A": 1, "B": 0},
                ),
            )
        self.assertIn("C", str(ctx_b.exception))

        # (c1) Invalid mapping: value=2
        with self.assertRaises(ValueError):
            self.service.map_dataset(
                self.dataset_id,
                self.raw_artifact,
                DataMappingConfig(
                    event_id_column="tx_id",
                    time_column="tx_time",
                    amount_column="tx_amount",
                    user_id_column="customer_id",
                    target_column="fraud_flag",
                    label_value_mapping={"0": 0, "1": 2},
                ),
            )

        # (c2) Invalid mapping: duplicate keys after strip()
        with self.assertRaises(ValueError):
            self.service.map_dataset(
                self.dataset_id,
                self.raw_artifact,
                DataMappingConfig(
                    event_id_column="tx_id",
                    time_column="tx_time",
                    amount_column="tx_amount",
                    user_id_column="customer_id",
                    target_column="fraud_flag",
                    label_value_mapping={"1": 1, " 1 ": 0},
                ),
            )

        # (c3) Canonical 0/1 and BOOLEAN true/false without label_value_mapping pass normally
        bool_df = self.raw_df.copy()
        bool_df["fraud_flag"] = [False, False, True, False, False, False, False, False, True, False]
        bool_path = f"datasets/{self.dataset_id}/raw/bool_labels.csv"
        self._save_df_to_storage(bool_df, bool_path)
        bool_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=bool_path,
            output_paths={"raw": bool_path},
        )
        mapped_bool = self.service.map_dataset(
            self.dataset_id,
            bool_art,
            DataMappingConfig(
                event_id_column="tx_id",
                time_column="tx_time",
                amount_column="tx_amount",
                user_id_column="customer_id",
                target_column="fraud_flag",
            ),
        )
        mapped_bool_df = pd.read_parquet(io.BytesIO(self.storage.read_bytes(mapped_bool.output_paths["mapped"])))
        self.assertEqual(mapped_bool_df[SystemColumn.LABEL.value].tolist(), [0, 0, 1, 0, 0, 0, 0, 0, 1, 0])

    def test_map_dataset_preserves_null_labels_and_warns_on_single_class(self):
        """ISS-047: Null/blank labels remain NULL (never coerced to 0) and single-class mapped labels emit a warning."""
        # (a) Null/blank cells in label column stay NULL and report missing warning
        null_df = self.raw_df.copy()
        null_df["fraud_flag"] = ["legit", "fraud", None, "legit", "", "legit", "fraud", "legit", "legit", "legit"]
        null_path = f"datasets/{self.dataset_id}/raw/null_labels.csv"
        self._save_df_to_storage(null_df, null_path)
        null_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=null_path,
            output_paths={"raw": null_path},
        )
        mapped_null = self.service.map_dataset(
            self.dataset_id,
            null_art,
            DataMappingConfig(
                event_id_column="tx_id",
                time_column="tx_time",
                amount_column="tx_amount",
                user_id_column="customer_id",
                target_column="fraud_flag",
                label_value_mapping={"fraud": 1, "legit": 0},
            ),
        )
        mapped_null_df = pd.read_parquet(io.BytesIO(self.storage.read_bytes(mapped_null.output_paths["mapped"])))
        self.assertTrue(pd.isna(mapped_null_df[SystemColumn.LABEL.value].iloc[2]))
        self.assertTrue(pd.isna(mapped_null_df[SystemColumn.LABEL.value].iloc[4]))
        self.assertEqual(mapped_null.validation_report["column_metrics"]["label"]["null_count"], 2)
        self.assertTrue(
            any("label" in w and "thiếu" in w for w in mapped_null.validation_report["warnings"]),
            mapped_null.validation_report["warnings"],
        )

        # (b) Single-class labels ('legit' only) emit single-class warning
        single_df = self.raw_df.copy()
        single_df["fraud_flag"] = ["legit"] * 10
        single_path = f"datasets/{self.dataset_id}/raw/single_class.csv"
        self._save_df_to_storage(single_df, single_path)
        single_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=single_path,
            output_paths={"raw": single_path},
        )
        mapped_single = self.service.map_dataset(
            self.dataset_id,
            single_art,
            DataMappingConfig(
                event_id_column="tx_id",
                time_column="tx_time",
                amount_column="tx_amount",
                user_id_column="customer_id",
                target_column="fraud_flag",
                label_value_mapping={"legit": 0},
            ),
        )
        self.assertTrue(
            any("1 lớp" in w or "single" in w.lower() for w in mapped_single.validation_report["warnings"]),
            mapped_single.validation_report["warnings"],
        )


if __name__ == "__main__":
    unittest.main()
