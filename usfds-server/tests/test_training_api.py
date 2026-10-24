import io
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
import pytest

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.services.training.plugins.register import package_directory_to_zip_bytes
from usfds_server import dependencies
from usfds_server.api import app
from usfds_server.config import settings


@pytest.fixture(autouse=True)
def temporary_environment():
    temp_dir = tempfile.mkdtemp(prefix="usfds_training_api_test_")
    db_file = os.path.join(temp_dir, "test.db")
    storage_path = os.path.join(temp_dir, "storage")

    settings.db_path = db_file
    settings.storage_dir = storage_path
    dependencies._engine = None
    dependencies._session_factory = None
    dependencies._storage = None

    yield temp_dir

    dependencies.teardown_infrastructure()
    dependencies._session_factory = None
    dependencies._storage = None
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


def _seed_feature_engineered_artifact(storage_dir: str) -> str:
    """Seed a synthetic FEATURE_ENGINEERED Dataset + DatasetArtifact into the test SQLite DB and storage."""
    assert dependencies._session_factory is not None
    session = dependencies._session_factory()
    try:
        ds_repo = dependencies.SqliteDatasetRepository(session)
        art_repo = dependencies.SqliteDatasetArtifactRepository(session)
        storage = dependencies.get_storage()

        rng = np.random.default_rng(42)
        n_rows = 80
        df = pd.DataFrame({
            "tx_id": [f"tx_{i}" for i in range(n_rows)],
            "amount": rng.uniform(10.0, 1000.0, size=n_rows),
            "velocity_1h": rng.integers(1, 10, size=n_rows).astype(float),
            "merchant_cat": rng.choice(["retail", "travel", "food"], size=n_rows),
            "label": np.array([0] * 60 + [1] * 20),
        })

        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        pq_bytes = buf.getvalue()

        dataset_id = uuid4()
        artifact_id = uuid4()
        train_rel = f"datasets/{dataset_id}/artifacts/{artifact_id}/train_enriched.parquet"
        test_rel = f"datasets/{dataset_id}/artifacts/{artifact_id}/test_enriched.parquet"
        storage.save_bytes(train_rel, pq_bytes)
        storage.save_bytes(test_rel, pq_bytes)

        dataset = Dataset(
            dataset_id=dataset_id,
            project_id=uuid4(),
            user_id=uuid4(),
            dataset_name="fe_test_ds",
        )
        ds_repo.save(dataset)

        artifact = DatasetArtifact(
            artifact_id=artifact_id,
            dataset_id=dataset_id,
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
            storage_path=f"datasets/{dataset_id}/artifacts/{artifact_id}",
            output_paths={"train": train_rel, "test": test_rel},
            row_count=n_rows,
            column_count=5,
            validation_status=ValidationStatus.PASSED,
            validation_report={"target_column": "label"},
        )
        art_repo.save(artifact)
        session.commit()
        return str(artifact_id)
    finally:
        session.close()


def test_training_router_builtin_and_plugin_models_lifecycle(temporary_environment):
    repo_root = Path(__file__).resolve().parent.parent.parent
    lr_plugin_dir = repo_root / "custom-models" / "logistic_regression"

    with TestClient(app) as client:
        fe_artifact_id = _seed_feature_engineered_artifact(settings.storage_dir)

        # 1. Verify Built-in models (random_forest, xgboost) are pre-seeded and available out-of-the-box
        res_list = client.get("/api/v1/training/models")
        assert res_list.status_code == 200
        initial_models = res_list.json()["data"]
        model_names = [m["model_name"] for m in initial_models]
        assert "random_forest" in model_names
        assert "xgboost" in model_names

        rf_model = next(m for m in initial_models if m["model_name"] == "random_forest")
        assert rf_model["execution_type"] == "BUILTIN"

        # 2. User uploads and registers custom model plugin via /models/plugins
        zip_bytes = package_directory_to_zip_bytes(lr_plugin_dir)
        storage = dependencies.get_storage()
        plugin_zip_rel = "uploads/lr_plugin.zip"
        storage.save_bytes(plugin_zip_rel, zip_bytes)

        res_plugin = client.post(
            "/api/v1/training/models/plugins",
            json={"model_artifact_path": plugin_zip_rel},
        )
        assert res_plugin.status_code == 201, res_plugin.text
        plugin_model = res_plugin.json()["data"]
        plugin_model_id = plugin_model["model_id"]
        assert plugin_model["execution_type"] == "SCRIPT"
        assert plugin_model["model_name"] == "custom_logistic_regression"

        # 3. Model catalog now has 3 models (2 built-in + 1 plugin)
        res_list_after = client.get("/api/v1/training/models")
        assert res_list_after.status_code == 200
        assert len(res_list_after.json()["data"]) == 3

        # 4. Run training for built-in Random Forest model
        res_rf_run = client.post(
            "/api/v1/training/runs",
            json={
                "model_id": rf_model["model_id"],
                "dataset_artifact_id": fe_artifact_id,
                "hyperparameters": {"n_estimators": 10},
                "run_name": "api-builtin-rf-run",
            },
        )
        assert res_rf_run.status_code == 201, res_rf_run.text
        rf_run_data = res_rf_run.json()["data"]
        assert rf_run_data["status"] == "COMPLETED"
        assert rf_run_data["accuracy"] is not None

        # 5. Run training for the plugged Logistic Regression model
        res_run = client.post(
            "/api/v1/training/runs",
            json={
                "model_id": plugin_model_id,
                "dataset_artifact_id": fe_artifact_id,
                "hyperparameters": {"C": 1.0, "max_iter": 100},
                "run_name": "api-lr-plugin-run",
            },
        )
        assert res_run.status_code == 201, res_run.text
        run_data = res_run.json()["data"]
        assert run_data["status"] == "COMPLETED"
        assert run_data["accuracy"] is not None
        assert run_data["version_id"] is not None

        # 6. Query model versions and run details
        res_versions = client.get(f"/api/v1/training/models/{plugin_model_id}/versions")
        assert res_versions.status_code == 200
        versions = res_versions.json()["data"]
        assert len(versions) == 1
        assert versions[0]["semver"] == "1.0.0"
        assert versions[0]["artifact_uri"].endswith("model_bundle.zip")

        res_ver_detail = client.get(f"/api/v1/training/versions/{versions[0]['version_id']}")
        assert res_ver_detail.status_code == 200
        assert res_ver_detail.json()["data"]["status"] == "CANDIDATE"

        # 7. Activate model version (SUC-10)
        res_activate = client.post(
            f"/api/v1/training/versions/{versions[0]['version_id']}/activate",
            json={"decision_threshold": 0.64, "description": "Activated via API test"},
        )
        assert res_activate.status_code == 200, res_activate.text
        activated_ver = res_activate.json()["data"]
        assert activated_ver["status"] == "APPROVED"
        assert activated_ver["decision_threshold"] == 0.64
        assert activated_ver["description"] == "Activated via API test"

        # 8. Test multipart .zip upload endpoint (SUC-17)
        svm_plugin_dir = repo_root / "custom-models" / "svm"
        svm_zip_bytes = package_directory_to_zip_bytes(svm_plugin_dir)
        res_upload_zip = client.post(
            "/api/v1/training/models/plugins/upload",
            files={"file": ("svm_plugin.zip", svm_zip_bytes, "application/zip")},
        )
        assert res_upload_zip.status_code == 201, res_upload_zip.text
        assert res_upload_zip.json()["data"]["execution_type"] == "SCRIPT"

        res_run_detail = client.get(f"/api/v1/training/runs/{run_data['run_id']}")
        assert res_run_detail.status_code == 200
        assert res_run_detail.json()["data"]["run_id"] == run_data["run_id"]
        assert res_run_detail.json()["data"]["dataset_artifact_id"] == fe_artifact_id
