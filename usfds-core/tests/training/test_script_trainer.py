import json
from pathlib import Path
import shutil
import tempfile
import unittest
import pandas as pd

from usfds_core.services.training.models.script_trainer import ScriptPluginTrainer
from usfds_core.services.training.workspace import TrainingRunWorkspace


class TestScriptPluginTrainer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.workspace = TrainingRunWorkspace(run_id="test_script", base_dir=self.temp_dir)
        self.workspace.initialize()
        pd.DataFrame({"f1": [1.0, 2.0], "is_fraud": [0, 1]}).to_parquet(
            self.workspace.train_data_path, index=False
        )

    def tearDown(self):
        self.workspace.cleanup()

    def test_successful_script_execution(self):
        # Create a mock training script following the run_training contract
        script_path = self.temp_dir / "train_mock.py"
        script_code = """
from pathlib import Path
import numpy as np

def run_training(train_file, test_file, artifact_dir, target_column, hyperparameters):
    out_dir = Path(artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model.bin").write_text("mock model weights")
    return {
        "y_true": np.array([0, 1, 0, 1]),
        "y_prob": np.array([0.1, 0.9, 0.2, 0.85]),
    }
"""
        script_path.write_text(script_code.strip(), encoding="utf-8")

        trainer = ScriptPluginTrainer(entrypoint_uri=str(script_path))
        metrics = trainer.train(
            workspace=self.workspace,
            target_column="is_fraud",
            hyperparameters={},
        )

        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertEqual(metrics["f1_score"], 1.0)
        self.assertTrue((self.workspace.model_dir / "model.bin").exists())

    def test_script_error_handling(self):
        script_path = self.temp_dir / "train_fail.py"
        script_code = """
import sys

def run_training(train_file, test_file, artifact_dir, target_column, hyperparameters):
    sys.stderr.write("Training failed intentionally!\\n")
    sys.exit(1)
"""
        script_path.write_text(script_code.strip(), encoding="utf-8")

        trainer = ScriptPluginTrainer(entrypoint_uri=str(script_path))
        with self.assertRaises(RuntimeError) as ctx:
            trainer.train(
                workspace=self.workspace,
                target_column="is_fraud",
                hyperparameters={},
            )
        self.assertIn("Training failed intentionally", str(ctx.exception))

    def test_missing_script_raises_filenotfound(self):
        trainer = ScriptPluginTrainer(entrypoint_uri=str(self.temp_dir / "non_existent.py"))
        with self.assertRaises(FileNotFoundError):
            trainer.train(
                workspace=self.workspace,
                target_column="is_fraud",
                hyperparameters={},
            )


if __name__ == "__main__":
    unittest.main()
