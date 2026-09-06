import json
from pathlib import Path
import shutil
import tempfile
import unittest

from usfds_core.services.training.models.script_trainer import ScriptPluginTrainer
from usfds_core.services.training.workspace import TrainingRunWorkspace


class TestScriptPluginTrainer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.workspace = TrainingRunWorkspace(run_id="test_script", base_dir=self.temp_dir)
        self.workspace.initialize()

    def tearDown(self):
        self.workspace.cleanup()

    def test_successful_script_execution(self):
        # Create a mock training script
        script_path = self.temp_dir / "train_mock.py"
        script_code = """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

out_dir = Path(args.output)
model_dir = out_dir / "model"
model_dir.mkdir(parents=True, exist_ok=True)
(model_dir / "model.bin").write_text("mock model weights")

metrics = {"accuracy": 0.98, "f1_score": 0.95}
with open(out_dir / "metrics.json", "w") as f:
    json.dump(metrics, f)
"""
        script_path.write_text(script_code.strip(), encoding="utf-8")

        trainer = ScriptPluginTrainer(entrypoint_uri=str(script_path))
        metrics = trainer.train(
            workspace=self.workspace,
            target_column="is_fraud",
            hyperparameters={},
        )

        self.assertEqual(metrics["accuracy"], 0.98)
        self.assertEqual(metrics["f1_score"], 0.95)
        self.assertTrue((self.workspace.model_dir / "model.bin").exists())

    def test_script_error_handling(self):
        script_path = self.temp_dir / "train_fail.py"
        script_code = """
import sys
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
