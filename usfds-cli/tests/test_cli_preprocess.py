import os
import shutil
import tempfile
import unittest
import pandas as pd
from typer.testing import CliRunner

from usfds_cli.main import app

runner = CliRunner()


class TestPreprocessCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="usfds_cli_test_")
        self.input_csv = os.path.join(self.temp_dir, "raw_transactions.csv")
        self.config_yaml = os.path.join(self.temp_dir, "test_config.yaml")
        self.storage_dir = os.path.join(self.temp_dir, "storage")
        self.report_json = os.path.join(self.temp_dir, "report.json")

        # Create dummy sample fraud dataset
        df = pd.DataFrame({
            "Time": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
            "Amount": [100.0, 25.0, 300.0, 12.0, 500.0, 60.0, 15.0, 800.0, 45.0, 1000.0],
            "V1": [0.1, -0.2, 0.5, 0.0, 1.2, -0.4, 0.3, 0.9, -0.1, 0.4],
            "V2": [-0.5, 0.3, -0.1, 0.8, -0.2, 0.1, -0.3, 0.4, 0.2, -0.6],
            "Class": [0, 0, 0, 0, 1, 0, 0, 1, 0, 0],
        })
        df.to_csv(self.input_csv, index=False)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cli_help(self):
        result = runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("preprocess", result.stdout)

        result_pre = runner.invoke(app, ["preprocess", "--help"])
        self.assertEqual(result_pre.exit_code, 0)
        self.assertIn("run", result_pre.stdout)
        self.assertIn("template", result_pre.stdout)
        self.assertIn("validate-config", result_pre.stdout)

    def test_generate_template_and_validate(self):
        # Generate YAML template
        result = runner.invoke(app, ["preprocess", "template", "--output", self.config_yaml, "--format", "yaml"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(self.config_yaml))

        # Validate config
        val_result = runner.invoke(app, ["preprocess", "validate-config", self.config_yaml])
        self.assertEqual(val_result.exit_code, 0)
        self.assertIn("VALID", val_result.stdout)

    def test_run_preprocessing_with_cli_flags(self):
        result = runner.invoke(app, [
            "preprocess", "run",
            "--input-file", self.input_csv,
            "--storage-dir", self.storage_dir,
            "--time-col", "Time",
            "--target-col", "Class",
            "--test-size", "0.3",
            "--output-report", self.report_json,
            "--user-name", "tester",
        ])
        self.assertEqual(result.exit_code, 0, msg=result.stdout)
        self.assertIn("Preprocessing Execution Result", result.stdout)
        self.assertTrue(os.path.exists(self.report_json))

    def test_run_preprocessing_with_config_file(self):
        # Generate template first
        runner.invoke(app, ["preprocess", "template", "--output", self.config_yaml])

        result = runner.invoke(app, [
            "preprocess", "run",
            "--input-file", self.input_csv,
            "--config", self.config_yaml,
            "--storage-dir", self.storage_dir,
            "--output-report", self.report_json,
        ])
        self.assertEqual(result.exit_code, 0, msg=result.stdout)
        self.assertIn("Preprocessing Execution Result", result.stdout)
    def test_run_preprocessing_without_feature_engineering(self):
        result = runner.invoke(app, [
            "preprocess", "run",
            "--input-file", self.input_csv,
            "--storage-dir", self.storage_dir,
            "--time-col", "Time",
            "--target-col", "Class",
            "--no-feature-engineering",
        ])
        self.assertEqual(result.exit_code, 0, msg=result.stdout)
        self.assertIn("Preprocessing Execution Result", result.stdout)


if __name__ == "__main__":
    unittest.main()
