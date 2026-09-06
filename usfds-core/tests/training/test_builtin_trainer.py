import json
from pathlib import Path
import shutil
import tempfile
import unittest
import numpy as np
import pandas as pd

from usfds_core.services.training.models.builtin_trainer import RandomForestTrainer, XGBoostTrainer
from usfds_core.services.training.models.trainer_factory import ModelTrainerFactory
from usfds_core.services.training.workspace import TrainingRunWorkspace


class TestBuiltinModelTrainer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.workspace = TrainingRunWorkspace(run_id="test_builtin", base_dir=self.temp_dir)
        self.workspace.initialize()

        # Generate synthetic classification dataset
        np.random.seed(42)
        n_samples = 100
        df = pd.DataFrame({
            "feature1": np.random.randn(n_samples),
            "feature2": np.random.randn(n_samples),
            "feature3": np.random.randn(n_samples),
            "is_fraud": np.random.choice([0, 1], size=n_samples, p=[0.8, 0.2]),
        })

        df.iloc[:80].to_parquet(self.workspace.train_data_path)
        df.iloc[80:].to_parquet(self.workspace.test_data_path)

    def tearDown(self):
        self.workspace.cleanup()

    def test_random_forest_training(self):
        trainer = RandomForestTrainer()
        metrics = trainer.train(
            workspace=self.workspace,
            target_column="is_fraud",
            hyperparameters={"n_estimators": 10, "max_depth": 3},
        )

        self.assertIn("accuracy", metrics)
        self.assertIn("f1_score", metrics)
        self.assertIn("confusion_matrix", metrics)

        # Verify model artifact produced
        model_file = self.workspace.model_dir / "model.joblib"
        self.assertTrue(model_file.exists())
        self.assertGreater(model_file.stat().st_size, 0)

        # Verify metrics.json
        self.assertTrue(self.workspace.metrics_path.exists())
        with open(self.workspace.metrics_path, "r") as f:
            saved_metrics = json.load(f)
        self.assertEqual(saved_metrics["accuracy"], metrics["accuracy"])

    def test_xgboost_training(self):
        trainer = XGBoostTrainer()
        metrics = trainer.train(
            workspace=self.workspace,
            target_column="is_fraud",
            hyperparameters={"n_estimators": 10, "max_depth": 3, "learning_rate": 0.1},
        )

        self.assertIn("accuracy", metrics)
        self.assertIn("f1_score", metrics)
        self.assertIn("roc_auc", metrics)

        # Verify model artifacts
        self.assertTrue((self.workspace.model_dir / "model.joblib").exists())
        self.assertTrue(self.workspace.metrics_path.exists())

    def test_factory_creation(self):
        rf_trainer = ModelTrainerFactory.create_trainer("BUILTIN", "random_forest")
        self.assertIsInstance(rf_trainer, RandomForestTrainer)

        xgb_trainer = ModelTrainerFactory.create_trainer("BUILTIN", "xgboost")
        self.assertIsInstance(xgb_trainer, XGBoostTrainer)

        with self.assertRaises(ValueError):
            ModelTrainerFactory.create_trainer("BUILTIN", "unsupported_algo")

    def test_missing_target_column_raises_error(self):
        trainer = RandomForestTrainer()
        with self.assertRaises(ValueError):
            trainer.train(
                workspace=self.workspace,
                target_column="non_existent_label",
                hyperparameters={},
            )


if __name__ == "__main__":
    unittest.main()
