from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from usfds_core.constants import DEFAULT_WORKSPACE_ROOT
from usfds_core.services.preprocessing.workspace import (
    FeatureEngineeringWorkspace,
    PreprocessingWorkspace,
)


class TestPreprocessingWorkspaces(unittest.TestCase):
    def setUp(self):
        self.temp_base = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_base, ignore_errors=True)

    def test_feature_engineering_workspace_lifecycle(self):
        artifact_id = uuid4()
        workspace = FeatureEngineeringWorkspace(
            dataset_artifact_id=artifact_id,
            base_dir=self.temp_base,
        )

        expected_run_dir = self.temp_base / str(artifact_id)
        self.assertEqual(workspace.run_dir, expected_run_dir)
        self.assertEqual(workspace.input_dir, expected_run_dir / "input")
        self.assertEqual(workspace.output_dir, expected_run_dir / "output")
        self.assertEqual(workspace.mapped_data_path, expected_run_dir / "input" / "mapped.parquet")
        self.assertEqual(workspace.train_enriched_path, expected_run_dir / "output" / "train_enriched.parquet")
        self.assertEqual(workspace.test_enriched_path, expected_run_dir / "output" / "test_enriched.parquet")
        self.assertEqual(workspace.fitted_engineers_path, expected_run_dir / "output" / "fitted_feature_engineers.joblib")

        # Before initialize
        self.assertFalse(workspace.input_dir.exists())
        self.assertFalse(workspace.output_dir.exists())

        # Initialize
        workspace.initialize()
        self.assertTrue(workspace.input_dir.exists())
        self.assertTrue(workspace.output_dir.exists())

        # Create a dummy file inside
        dummy_file = workspace.train_enriched_path
        dummy_file.write_text("test")
        self.assertTrue(dummy_file.exists())

        # Cleanup
        workspace.cleanup()
        self.assertFalse(workspace.run_dir.exists())

    def test_preprocessing_workspace_lifecycle(self):
        artifact_id = uuid4()
        workspace = PreprocessingWorkspace(
            dataset_artifact_id=artifact_id,
            base_dir=self.temp_base,
        )

        expected_run_dir = self.temp_base / str(artifact_id)
        self.assertEqual(workspace.run_dir, expected_run_dir)
        self.assertEqual(workspace.input_dir, expected_run_dir / "input")
        self.assertEqual(workspace.output_dir, expected_run_dir / "output")
        self.assertEqual(workspace.train_input_path, expected_run_dir / "input" / "train_enriched.parquet")
        self.assertEqual(workspace.test_input_path, expected_run_dir / "input" / "test_enriched.parquet")
        self.assertEqual(workspace.train_processed_path, expected_run_dir / "output" / "train_processed.parquet")
        self.assertEqual(workspace.test_processed_path, expected_run_dir / "output" / "test_processed.parquet")
        self.assertEqual(workspace.fitted_pipeline_path, expected_run_dir / "output" / "fitted_pipeline.joblib")

        # Initialize
        workspace.initialize()
        self.assertTrue(workspace.input_dir.exists())
        self.assertTrue(workspace.output_dir.exists())

        # Cleanup
        workspace.cleanup()
        self.assertFalse(workspace.run_dir.exists())

    def test_default_base_dir_resolution(self):
        artifact_id = uuid4()
        fe_workspace = FeatureEngineeringWorkspace(dataset_artifact_id=artifact_id)
        self.assertEqual(
            fe_workspace.base_dir,
            DEFAULT_WORKSPACE_ROOT / "preprocessing" / "feature_engineering",
        )

        prep_workspace = PreprocessingWorkspace(dataset_artifact_id=artifact_id)
        self.assertEqual(
            prep_workspace.base_dir,
            DEFAULT_WORKSPACE_ROOT / "preprocessing" / "transformations",
        )
