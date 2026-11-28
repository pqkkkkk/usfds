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
from usfds_infra.database import SqliteDatasetArtifactRepository, SqliteDatasetRepository


# DEPRECATED [26-11-14]: replaced by the autouse `server_settings` fixture in tests/conftest.py (ISS-025).
# @pytest.fixture(autouse=True)
# def temporary_environment():
#     temp_dir = tempfile.mkdtemp(prefix="usfds_training_api_test_")
#     db_file = os.path.join(temp_dir, "test.db")
#     storage_path = os.path.join(temp_dir, "storage")
#
#     settings.db_path = db_file
#     settings.storage_dir = storage_path
#     dependencies._engine = None
#     dependencies._session_factory = None
#     dependencies._storage = None
#
#     yield temp_dir
#
#     dependencies.teardown_infrastructure()
#     dependencies._session_factory = None
#     dependencies._storage = None
#     if os.path.exists(temp_dir):
#         shutil.rmtree(temp_dir, ignore_errors=True)


def _seed_feature_engineered_artifact(storage_dir: str, project_id: str | None = None) -> tuple[str, str]:
    """Seed a synthetic FEATURE_ENGINEERED Dataset + DatasetArtifact into the test SQLite DB and storage."""
    from uuid import UUID

    assert dependencies._session_factory is not None
    session = dependencies._session_factory()
    try:
        ds_repo = SqliteDatasetRepository(session)
        art_repo = SqliteDatasetArtifactRepository(session)
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
        resolved_project_id = UUID(project_id) if project_id else uuid4()
        train_rel = f"datasets/{dataset_id}/artifacts/{artifact_id}/train_enriched.parquet"
        test_rel = f"datasets/{dataset_id}/artifacts/{artifact_id}/test_enriched.parquet"
        storage.save_bytes(train_rel, pq_bytes)
        storage.save_bytes(test_rel, pq_bytes)

        from usfds_core.domain.entities.system import Project
        from usfds_infra.database import SqliteProjectRepository, SqlUserRepository

        admin_id = SqlUserRepository(session).get_by_username("admin").user_id
        proj_repo = SqliteProjectRepository(session)
        if proj_repo.get_by_id(resolved_project_id) is None:
            proj_repo.save(
                Project(
                    project_id=resolved_project_id,
                    user_id=admin_id,
                    project_name=f"proj_{resolved_project_id.hex[:8]}",
                )
            )

        dataset = Dataset(
            dataset_id=dataset_id,
            project_id=resolved_project_id,
            user_id=admin_id,
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
        return str(artifact_id), str(resolved_project_id)
    finally:
        session.close()


def test_training_router_builtin_and_plugin_models_lifecycle(server_settings):
    repo_root = Path(__file__).resolve().parent.parent.parent
    lr_plugin_dir = repo_root / "custom-models" / "logistic_regression"

    with TestClient(app) as client:
        fe_artifact_id, project_id = _seed_feature_engineered_artifact(settings.storage_dir)

        # 1. Verify Built-in models (random_forest, xgboost) are pre-seeded and available out-of-the-box
        res_list = client.get("/api/v1/training/models", params={"project_id": project_id})
        assert res_list.status_code == 200
        initial_models = res_list.json()["data"]["items"]
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
            json={"model_artifact_path": plugin_zip_rel, "project_id": project_id},
        )
        assert res_plugin.status_code == 201, res_plugin.text
        plugin_model = res_plugin.json()["data"]
        plugin_model_id = plugin_model["model_id"]
        assert plugin_model["execution_type"] == "SCRIPT"
        assert plugin_model["model_name"] == "custom_logistic_regression"

        # 3. Model catalog now has 3 models (2 built-in + 1 plugin)
        res_list_after = client.get("/api/v1/training/models", params={"project_id": project_id})
        assert res_list_after.status_code == 200
        assert len(res_list_after.json()["data"]["items"]) == 3

        # 4. Run training for built-in Random Forest model
        res_rf_run = client.post(
            "/api/v1/training/runs",
            json={
                "project_id": project_id,
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
                "project_id": project_id,
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
        res_versions = client.get(f"/api/v1/training/models/{plugin_model_id}/versions", params={"project_id": project_id})
        assert res_versions.status_code == 200
        versions = res_versions.json()["data"]["items"]
        assert len(versions) == 1
        assert versions[0]["semver"] == "v1"
        assert versions[0]["artifact_uri"].endswith("model_bundle.zip")

        res_ver_detail = client.get(f"/api/v1/training/versions/{versions[0]['version_id']}", params={"project_id": project_id})
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

        res_run_detail = client.get(f"/api/v1/training/runs/{run_data['run_id']}", params={"project_id": project_id})
        assert res_run_detail.status_code == 200
        assert res_run_detail.json()["data"]["run_id"] == run_data["run_id"]
        assert res_run_detail.json()["data"]["dataset_artifact_id"] == fe_artifact_id


def _seed_lineage_chain():
    """Seed RAW -> MAPPED -> FEATURE_ENGINEERED -> TrainingRun -> ModelVersion in SQLite."""
    from datetime import datetime, timedelta, timezone
    from usfds_core.domain.entities.enums import DatasetRole, ModelVersionStatus, TrainingRunStatus
    from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
    from usfds_infra.database import (
        SqliteModelRepository,
        SqliteModelVersionRepository,
        SqliteTrainingRunRepository,
    )

    assert dependencies._session_factory is not None
    session = dependencies._session_factory()
    try:
        ds_repo = SqliteDatasetRepository(session)
        art_repo = SqliteDatasetArtifactRepository(session)
        model_repo = SqliteModelRepository(session)
        run_repo = SqliteTrainingRunRepository(session)
        ver_repo = SqliteModelVersionRepository(session)

        t0 = datetime(2026, 11, 14, 2, 0, 0, tzinfo=timezone.utc)
        dataset_id = uuid4()
        project_id = uuid4()
        from usfds_core.domain.entities.system import Project
        from usfds_infra.database import SqliteProjectRepository, SqlUserRepository

        user_id = SqlUserRepository(session).get_by_username("admin").user_id
        SqliteProjectRepository(session).save(
            Project(project_id=project_id, user_id=user_id, project_name=f"lineage_proj_{project_id.hex[:6]}")
        )

        ds_repo.save(
            Dataset(
                dataset_id=dataset_id,
                project_id=project_id,
                user_id=user_id,
                dataset_name="lineage_ds",
            )
        )

        raw = DatasetArtifact(
            dataset_id=dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path="raw.parquet",
            validation_status=ValidationStatus.PASSED,
            row_count=50,
            column_count=5,
            created_at=t0,
        )
        mapped = DatasetArtifact(
            dataset_id=dataset_id,
            parent_artifact_id=raw.artifact_id,
            pipeline_stage=PipelineStage.MAPPED,
            storage_path="mapped.parquet",
            validation_status=ValidationStatus.PASSED,
            row_count=50,
            column_count=5,
            created_at=t0 + timedelta(minutes=1),
        )
        fe = DatasetArtifact(
            dataset_id=dataset_id,
            parent_artifact_id=mapped.artifact_id,
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
            storage_path="fe.parquet",
            validation_status=ValidationStatus.PASSED,
            row_count=50,
            column_count=9,
            created_at=t0 + timedelta(minutes=2),
        )
        art_repo.save(raw)
        art_repo.save(mapped)
        art_repo.save(fe)

        model = Model(model_name=f"rf_lineage_{uuid4().hex[:6]}", display_name="RF Lineage", user_id=user_id)
        model_repo.save(model)

        run = TrainingRun(
            run_name="lineage-run-1",
            project_id=project_id,
            user_id=user_id,
            model_id=model.model_id,
            status=TrainingRunStatus.COMPLETED,
            created_at=t0 + timedelta(minutes=3),
        )
        version = ModelVersion(
            model_id=model.model_id,
            project_id=project_id,
            user_id=user_id,
            run_id=run.run_id,
            semver="1.0.0",
            artifact_uri="models/rf/1.0.0/model.joblib",
            checksum_sha256="b" * 64,
            status=ModelVersionStatus.CANDIDATE,
            registered_at=t0 + timedelta(minutes=4),
        )
        run.version_id = version.version_id

        run_repo.save(run)
        run_repo.link_dataset(run.run_id, fe.artifact_id, DatasetRole.TRAIN)
        ver_repo.save(version)
        session.commit()
        return str(version.version_id), str(run.run_id), str(project_id)
    finally:
        session.close()


def test_get_version_lineage_endpoint_returns_dag(server_settings):
    """ISS-008: GET /api/v1/training/versions/{version_id}/lineage returns full upstream DAG."""
    with TestClient(app) as client:
        version_id, run_id, project_id = _seed_lineage_chain()
        res = client.get(f"/api/v1/training/versions/{version_id}/lineage", params={"project_id": project_id})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        assert data["root_version_id"] == version_id
        assert data["root_run_id"] == run_id
        assert [n["stage"] for n in data["nodes"]] == [
            "RAW",
            "MAPPED",
            "FEATURE_ENGINEERED",
            "TRAINING_RUN",
            "MODEL_VERSION",
        ]
        assert len(data["edges"]) == 4


def test_get_run_lineage_endpoint_returns_dag_and_404(server_settings):
    """ISS-008: GET /api/v1/training/runs/{run_id}/lineage returns DAG for valid run and 404 for unknown."""
    with TestClient(app) as client:
        version_id, run_id, project_id = _seed_lineage_chain()
        res = client.get(f"/api/v1/training/runs/{run_id}/lineage", params={"project_id": project_id})
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["root_run_id"] == run_id
        assert data["root_version_id"] == version_id
        assert len(data["nodes"]) == 5

        res_missing = client.get(f"/api/v1/training/runs/{uuid4()}/lineage", params={"project_id": project_id})
        assert res_missing.status_code == 404


def test_plugin_upload_rejects_oversize_content_length_and_stream(server_settings, monkeypatch):
    """ISS-016: /models/plugins/upload must reject > max_plugin_upload_mb with HTTP 413 on both Content-Length and chunked stream."""
    monkeypatch.setattr(server_settings, "max_plugin_upload_mb", 1)
    oversize_bytes = b"PK\x03\x04" + (b"\x00" * (1024 * 1024 + 64))

    with TestClient(app) as client:
        # 1. Standard multipart/raw upload with Content-Length > 1 MB
        res_cl = client.post(
            "/api/v1/training/models/plugins/upload",
            files={"file": ("big_plugin.zip", oversize_bytes, "application/zip")},
        )
        assert res_cl.status_code == 413, res_cl.text

        # 2. Chunked stream without Content-Length header exceeding 1 MB
        def _chunk_stream():
            chunk_size = 256 * 1024
            for offset in range(0, len(oversize_bytes), chunk_size):
                yield oversize_bytes[offset : offset + chunk_size]

        res_stream = client.post(
            "/api/v1/training/models/plugins/upload",
            content=_chunk_stream(),
            headers={"Content-Type": "application/zip"},
        )
        assert res_stream.status_code == 413, res_stream.text


def test_plugin_upload_does_not_block_event_loop(server_settings, monkeypatch):
    """ISS-019: Blocking registration/enqueue_and_wait inside upload endpoint must not freeze the ASGI event loop."""
    import asyncio
    import threading
    import time
    import httpx
    from usfds_core.domain.entities.enums import ExecutionType
    from usfds_core.domain.entities.model import Model
    from usfds_core.services.training.training_service import TrainingOrchestrationService

    # Ensure app infrastructure is initialized via lifespan before AsyncClient requests
    with TestClient(app):
        pass

    dummy_model = Model(
        model_id=uuid4(),
        model_name="slow_plugin_test",
        user_id=uuid4(),
        execution_type=ExecutionType.SCRIPT,
    )
    entered = threading.Event()

    def _slow_register(self, *args, **kwargs):
        entered.set()
        time.sleep(0.4)
        return dummy_model

    monkeypatch.setattr(TrainingOrchestrationService, "register_plugged_model", _slow_register)

    async def _run_concurrent():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            upload_task = asyncio.create_task(
                ac.post(
                    "/api/v1/training/models/plugins/upload",
                    files={"file": ("slow_plugin.zip", b"PK\x03\x04dummy", "application/zip")},
                )
            )
            while not entered.is_set():
                await asyncio.sleep(0.005)
            t0 = time.perf_counter()
            health_res = await ac.get("/health")
            health_elapsed = time.perf_counter() - t0
            upload_finished_first = upload_task.done()
            upload_res = await upload_task
            return health_res, health_elapsed, upload_finished_first, upload_res

    health_res, health_elapsed, upload_finished_first, upload_res = asyncio.run(_run_concurrent())
    assert health_res.status_code == 200
    assert upload_res.status_code == 201, upload_res.text
    assert not upload_finished_first, "Event loop was blocked until upload finished!"
    assert health_elapsed < 0.2, f"/health was blocked by upload endpoint ({health_elapsed:.3f}s)"


def test_list_model_versions_filters_by_project_id(server_settings):
    """ISS-010 / BR-PM-06: GET /models/{model_id}/versions?project_id=... isolates versions per project on BUILTIN models."""
    with TestClient(app) as client:
        project_a = str(uuid4())
        project_b = str(uuid4())
        fe_artifact_a, _ = _seed_feature_engineered_artifact(settings.storage_dir, project_id=project_a)
        fe_artifact_b, _ = _seed_feature_engineered_artifact(settings.storage_dir, project_id=project_b)
        models = client.get("/api/v1/training/models", params={"project_id": project_a}).json()["data"]["items"]
        rf_model = next(m for m in models if m["model_name"] == "random_forest")

        res_a = client.post(
            "/api/v1/training/runs",
            json={
                "model_id": rf_model["model_id"],
                "dataset_artifact_id": fe_artifact_a,
                "project_id": project_a,
                "hyperparameters": {"n_estimators": 5},
                "run_name": "run-proj-a",
            },
        )
        assert res_a.status_code == 201, res_a.text

        res_b = client.post(
            "/api/v1/training/runs",
            json={
                "model_id": rf_model["model_id"],
                "dataset_artifact_id": fe_artifact_b,
                "project_id": project_b,
                "hyperparameters": {"n_estimators": 5},
                "run_name": "run-proj-b",
            },
        )
        assert res_b.status_code == 201, res_b.text

        ver_res_a = client.get(f"/api/v1/training/models/{rf_model['model_id']}/versions", params={"project_id": project_a})
        ver_res_b = client.get(f"/api/v1/training/models/{rf_model['model_id']}/versions", params={"project_id": project_b})
        assert ver_res_a.status_code == 200
        assert ver_res_b.status_code == 200

        versions_a = ver_res_a.json()["data"]["items"]
        versions_b = ver_res_b.json()["data"]["items"]
        assert len(versions_a) == 1
        assert len(versions_b) == 1
        assert versions_a[0]["project_id"] == project_a
        assert versions_a[0]["semver"] == "v1"
        assert versions_b[0]["project_id"] == project_b
        assert versions_b[0]["semver"] == "v1"


def test_compute_targets_endpoint_enforces_project_rbac_and_syncs_remote_run(
    server_settings,
    monkeypatch,
):
    """ISS-009, ISS-042: GET /compute-targets enforces project RBAC; POST /runs offloads to remote provider and GET /runs/{id} syncs completion."""
    from uuid import UUID
    from usfds_core.domain.schemas.training_payload import (
        RemoteJobStatus,
        RemoteTrainingJobSpec,
        TrainingRunResult,
    )
    from usfds_infra.security import PasswordHasher
    from usfds_core.services.training.providers.base_provider import (
        IRemoteComputeProvider,
        RemoteProviderRegistry,
    )
    from usfds_core.domain.entities.auth import ProjectMember
    from usfds_core.domain.entities.enums import RoleScope
    from usfds_core.domain.entities.system import User
    from usfds_infra.database import (
        SqlProjectMemberRepository,
        SqlRoleRepository,
        SqlUserRepository,
        session_scope,
    )
    from usfds_server.providers.training import get_remote_provider_registry

    class _FakeModalProvider(IRemoteComputeProvider):
        def __init__(self):
            self.submitted: list[RemoteTrainingJobSpec] = []
            self.completed_result: TrainingRunResult | None = None

        @property
        def provider_id(self) -> str:
            return "modal"

        @property
        def display_name(self) -> str:
            return "Modal Serverless"

        def is_available(self):
            return True, None

        def submit(self, job_spec: RemoteTrainingJobSpec) -> str:
            self.submitted.append(job_spec)
            self.completed_result = TrainingRunResult(
                run_id=job_spec.payload.run_id,
                is_success=True,
                metrics={"accuracy": 0.93, "precision": 0.9, "recall": 0.87, "f1_score": 0.88},
                artifact_uri=f"models/{job_spec.payload.model_id}/runs/{job_spec.payload.run_id}/model.joblib",
                checksum_sha256="sha256-remote",
                framework="scikit-learn",
                duration_seconds=11,
            )
            return "fc-server-1"

        def poll(self, external_job_id: str, timeout_seconds: float = 5.0) -> RemoteJobStatus:
            return RemoteJobStatus(state="COMPLETED", result=self.completed_result)

    fake_provider = _FakeModalProvider()
    fake_registry = RemoteProviderRegistry()
    fake_registry.register(fake_provider)

    monkeypatch.setattr(server_settings, "auth_mode", "required")
    monkeypatch.setattr(server_settings, "auto_compute_row_threshold", 50)
    monkeypatch.setattr(server_settings, "remote_poller_enabled", False)

    app.dependency_overrides[get_remote_provider_registry] = lambda: fake_registry
    try:
        with TestClient(app) as client:
            project_id = str(uuid4())
            fe_artifact_id, _ = _seed_feature_engineered_artifact(
                settings.storage_dir,
                project_id=project_id,
            )
            # Patch presigned URL methods on the active storage instance so remote dispatch succeeds without S3
            storage = dependencies.get_storage()
            monkeypatch.setattr(
                storage,
                "generate_presigned_download_url",
                lambda file_path, filename=None, expires_in=900: f"https://s3.test/get/{file_path}",
            )
            monkeypatch.setattr(
                storage,
                "generate_presigned_upload_url",
                lambda file_path, content_type=None, expires_in=900: f"https://s3.test/put/{file_path}",
            )

            # Seed 1 member in project and 1 outsider user
            hasher = PasswordHasher()
            with session_scope(dependencies._session_factory) as session:
                user_repo = SqlUserRepository(session)
                role_repo = SqlRoleRepository(session)
                member_repo = SqlProjectMemberRepository(session)
                ds_role = role_repo.get_by_scope_and_name(RoleScope.PROJECT, "data_scientist")
                assert ds_role is not None

                member_user = User(
                    user_id=uuid4(),
                    username="proj_member",
                    email="proj_member@usfds.local",
                    full_name="Project Member",
                    password_hash=hasher.hash("MemberPass123!"),
                )
                outsider_user = User(
                    user_id=uuid4(),
                    username="outsider_user",
                    email="outsider@usfds.local",
                    full_name="Outsider",
                    password_hash=hasher.hash("OutsiderPass123!"),
                )
                user_repo.save(member_user)
                user_repo.save(outsider_user)
                member_repo.add_member(
                    project_id=UUID(project_id),
                    user_id=member_user.user_id,
                    role_id=ds_role.role_id,
                )

            def _login(username: str, password: str) -> dict[str, str]:
                resp = client.post(
                    "/api/v1/auth/login",
                    json={"username": username, "password": password},
                )
                assert resp.status_code == 200, resp.text
                token = resp.json()["data"]["access_token"]
                return {"Authorization": f"Bearer {token}"}

            member_headers = _login("proj_member", "MemberPass123!")
            outsider_headers = _login("outsider_user", "OutsiderPass123!")

            models_res = client.get(
                "/api/v1/training/models",
                params={"project_id": project_id},
                headers=member_headers,
            )
            assert models_res.status_code == 200, models_res.text
            rf_model = next(
                m for m in models_res.json()["data"]["items"] if m["model_name"] == "random_forest"
            )

            # 1. Outsider gets 403 on GET /compute-targets
            forbidden_res = client.get(
                "/api/v1/training/compute-targets",
                params={
                    "project_id": project_id,
                    "model_id": rf_model["model_id"],
                    "dataset_artifact_id": fe_artifact_id,
                },
                headers=outsider_headers,
            )
            assert forbidden_res.status_code == 403

            # 2. Valid project member gets targets + auto recommendation -> modal (80 rows >= 50 threshold)
            targets_res = client.get(
                "/api/v1/training/compute-targets",
                params={
                    "project_id": project_id,
                    "model_id": rf_model["model_id"],
                    "dataset_artifact_id": fe_artifact_id,
                },
                headers=member_headers,
            )
            assert targets_res.status_code == 200, targets_res.text
            targets_data = targets_res.json()["data"]
            target_ids = [t["target_id"] for t in targets_data["targets"]]
            assert "auto" in target_ids
            assert "local" in target_ids
            assert "modal" in target_ids
            assert targets_data["recommendation"]["resolved_target"] == "modal"

            # 3. POST /runs with compute_target="auto" submits to Modal and returns RUNNING + external_job_id
            run_res = client.post(
                "/api/v1/training/runs",
                json={
                    "model_id": rf_model["model_id"],
                    "dataset_artifact_id": fe_artifact_id,
                    "project_id": project_id,
                    "compute_target": "auto",
                    "run_name": "remote-auto-run",
                },
                headers=member_headers,
            )
            assert run_res.status_code == 201, run_res.text
            run_data = run_res.json()["data"]
            assert run_data["status"] == "RUNNING"
            assert run_data["compute_target"] == "modal"
            assert run_data["external_job_id"] == "fc-server-1"
            assert run_data["compute_metadata"]["resolved_target"] == "modal"

            # 4. GET /runs/{run_id} syncs remote provider -> COMPLETED + attaches version_id
            detail_res = client.get(
                f"/api/v1/training/runs/{run_data['run_id']}",
                params={"project_id": project_id},
                headers=member_headers,
            )
            assert detail_res.status_code == 200, detail_res.text
            detail_data = detail_res.json()["data"]
            assert detail_data["status"] == "COMPLETED"
            assert detail_data["version_id"] is not None
            assert detail_data["f1_score"] == 0.88
    finally:
        app.dependency_overrides.pop(get_remote_provider_registry, None)


def test_get_training_run_releases_db_session_before_remote_poll(client, monkeypatch):
    """ISS-009: GET /runs/{run_id} releases DB session/connection before calling provider.poll()."""
    from usfds_core.domain.entities.enums import ExecutionType, TrainingRunStatus
    from usfds_core.domain.entities.model import Model, TrainingRun
    from usfds_core.domain.entities.system import Project
    from usfds_core.domain.schemas.training_payload import (
        RemoteJobStatus,
        RemoteTrainingJobSpec,
        TrainingRunResult,
    )
    from usfds_core.services.training.providers.base_provider import (
        IRemoteComputeProvider,
        RemoteProviderRegistry,
    )
    from usfds_infra.database import (
        SqliteModelRepository,
        SqliteModelVersionRepository,
        SqliteProjectRepository,
        SqliteTrainingRunRepository,
        SqlUserRepository,
        session_scope,
    )
    from usfds_server.config import settings as server_settings
    from usfds_server.providers.training import get_remote_provider_registry

    project_id = uuid4()
    model_id = uuid4()
    run_id = uuid4()
    observed_checkedout: list[int] = []

    class _SessionInspectingProvider(IRemoteComputeProvider):
        @property
        def provider_id(self) -> str:
            return "modal"

        @property
        def display_name(self) -> str:
            return "Modal Serverless"

        def is_available(self):
            return True, None

        def submit(self, job_spec: RemoteTrainingJobSpec) -> str:
            return "sb-1"

        def poll(self, external_job_id: str, timeout_seconds: float = 5.0) -> RemoteJobStatus:
            assert dependencies._engine is not None
            observed_checkedout.append(dependencies._engine.pool.checkedout())
            return RemoteJobStatus(
                state="COMPLETED",
                result=TrainingRunResult(
                    run_id=run_id,
                    is_success=True,
                    metrics={"accuracy": 0.93, "f1_score": 0.91},
                    artifact_uri=f"models/{model_id}/runs/{run_id}/model.joblib",
                    checksum_sha256="deadbeef",
                    framework="scikit-learn",
                    duration_seconds=9,
                ),
            )

    fake_registry = RemoteProviderRegistry()
    fake_registry.register(_SessionInspectingProvider())

    monkeypatch.setattr(server_settings, "auth_mode", "local_auto")
    monkeypatch.setattr(server_settings, "remote_poller_enabled", False)

    app.dependency_overrides[get_remote_provider_registry] = lambda: fake_registry
    try:
        with TestClient(app) as tc:
            with session_scope(dependencies._session_factory) as session:
                admin = SqlUserRepository(session).get_by_username("admin")
                assert admin is not None
                SqliteProjectRepository(session).save(
                    Project(project_id=project_id, user_id=admin.user_id, project_name="PollHygieneProj")
                )
                SqliteModelRepository(session).save(
                    Model(
                        model_id=model_id,
                        project_id=project_id,
                        user_id=admin.user_id,
                        model_name="random_forest",
                        execution_type=ExecutionType.BUILTIN,
                    )
                )
                SqliteTrainingRunRepository(session).save(
                    TrainingRun(
                        run_id=run_id,
                        project_id=project_id,
                        user_id=admin.user_id,
                        model_id=model_id,
                        run_name="modal-sb-run",
                        status=TrainingRunStatus.RUNNING,
                        compute_target="modal",
                        external_job_id="sb-1",
                        compute_metadata={"provider": "modal", "resolved_target": "modal"},
                        created_by="admin",
                    )
                )

            res = tc.get(
                f"/api/v1/training/runs/{run_id}",
                params={"project_id": str(project_id)},
            )
            assert res.status_code == 200, res.text
            data = res.json()["data"]
            assert data["status"] == "COMPLETED"
            assert data["version_id"] is not None
            assert observed_checkedout == [0], (
                f"Expected 0 DB connections checked out during provider.poll(), got {observed_checkedout}"
            )

            with session_scope(dependencies._session_factory) as session:
                versions = SqliteModelVersionRepository(session).list_by_model(
                    model_id, project_id=project_id
                )
                assert len(versions) == 1
                assert str(versions[0].version_id) == data["version_id"]
    finally:
        app.dependency_overrides.pop(get_remote_provider_registry, None)



