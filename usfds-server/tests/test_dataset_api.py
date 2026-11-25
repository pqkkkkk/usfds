import io
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
from fastapi.testclient import TestClient
import pandas as pd
import pytest

from usfds_core.domain.schemas.preprocessing_config import SupportedTimeFormat
from usfds_server.api import app
from usfds_server.config import settings


# DEPRECATED [26-11-14]: replaced by the autouse `server_settings` fixture in tests/conftest.py (ISS-025).
# @pytest.fixture(autouse=True)
# def temporary_environment():
#     temp_dir = tempfile.mkdtemp(prefix="usfds_server_test_")
#     db_file = os.path.join(temp_dir, "test.db")
#     storage_path = os.path.join(temp_dir, "storage")
#
#     settings.db_path = db_file
#     settings.storage_dir = storage_path
#
#     yield
#
#     if os.path.exists(temp_dir):
#         shutil.rmtree(temp_dir, ignore_errors=True)


def test_end_to_end_data_management_pipeline():
    with TestClient(app) as client:
        proj_res = client.post("/api/v1/projects", json={"project_name": "DS Pipeline Project"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["data"]["project_id"]
        user_id = proj_res.json()["data"]["user_id"]

        # -------------------------------------------------------------
        # 1. Import raw dataset from local file path (Entry point)
        # -------------------------------------------------------------
        raw_df = pd.DataFrame({
            "TransactionID": [f"TX_{i:04d}" for i in range(50)],
            "TxTime": [f"2024-01-01 10:{i:02d}:00" for i in range(50)],
            "TxAmount": [10.5 + (i * 2.5) for i in range(50)],
            "AccountNo": [f"ACC_{i % 5}" for i in range(50)],
            "IsFraud": [0] * 45 + [1] * 5,
            "DeviceType": ["MOBILE"] * 30 + ["WEB"] * 20,
            "Notes": ["some notes"] * 50,  # Unused column
        })
        temp_csv_file = Path(settings.storage_dir) / "source_input.csv"
        temp_csv_file.parent.mkdir(parents=True, exist_ok=True)
        raw_df.to_csv(temp_csv_file, index=False)

        import_payload = {
            "file_path": str(temp_csv_file),
            "dataset_name": "credit_card_fraud",
            "display_name": "Credit Card Fraud 2024",
            "description": "Historical fraud dataset for model training",
            "project_id": project_id,
            "user_id": user_id,
            "contains_pii": True,
            "data_classification": "CONFIDENTIAL",
        }
        res_import = client.post("/api/v1/datasets/import", json=import_payload)
        assert res_import.status_code == 201, res_import.text
        envelope_import = res_import.json()
        assert envelope_import["success"] is True
        assert envelope_import["statusCode"] == 201
        data_import = envelope_import["data"]
        dataset_info = data_import["dataset"]
        dataset_id = dataset_info["dataset_id"]
        assert dataset_info["dataset_name"] == "credit_card_fraud"
        assert dataset_info["display_name"] == "Credit Card Fraud 2024"
        assert len(data_import["artifacts"]) == 1
        raw_art = data_import["artifacts"][0]
        assert raw_art["pipeline_stage"] == "RAW"
        assert raw_art["row_count"] == 50
        assert raw_art["column_count"] == 7
        raw_artifact_id = raw_art["artifact_id"]

        # Check duplicate name error (returns envelope with success=False)
        res_dup = client.post("/api/v1/datasets/import", json=import_payload)
        assert res_dup.status_code >= 400
        assert res_dup.json()["success"] is False

        # List datasets
        res_list = client.get(f"/api/v1/datasets?project_id={project_id}")
        assert res_list.status_code == 200
        list_envelope = res_list.json()
        assert list_envelope["success"] is True
        assert len(list_envelope["data"]["items"]) == 1

        # -------------------------------------------------------------
        # 3. Retrieve specific artifact details (including profiling & validation report)
        # -------------------------------------------------------------
        res_art = client.get(
            f"/api/v1/datasets/{dataset_id}/artifacts/{raw_artifact_id}",
            params={"project_id": project_id},
        )
        assert res_art.status_code == 200, res_art.text
        art_envelope = res_art.json()
        assert art_envelope["success"] is True
        art_data = art_envelope["data"]
        assert art_data["artifact_id"] == raw_artifact_id
        assert art_data["pipeline_stage"] == "RAW"
        assert art_data["row_count"] == 50
        assert art_data["column_count"] == 7
        assert "profiling" in art_data["validation_report"]
        profiling = art_data["validation_report"]["profiling"]
        assert profiling["row_count"] == 50
        assert profiling["field_count"] == 7
        field_names = [f["name"] for f in profiling["fields"]]
        assert "TransactionID" in field_names

        # -------------------------------------------------------------
        # 4. Map schema to 5 core fields + auto validation
        # -------------------------------------------------------------
        mapping_payload = {
            "event_id_column": "TransactionID",
            "time_column": "TxTime",
            "amount_column": "TxAmount",
            "user_id_column": "AccountNo",
            "target_column": "IsFraud",
            "optional_columns": {"DeviceType": "device_type"},
            "time_format": "auto",
        }
        res_map = client.post(f"/api/v1/datasets/{dataset_id}/schema-mapping", json=mapping_payload)
        assert res_map.status_code == 201, res_map.text
        map_envelope = res_map.json()
        assert map_envelope["success"] is True
        assert map_envelope["statusCode"] == 201
        data_map = map_envelope["data"]
        assert data_map["pipeline_stage"] == "MAPPED"
        assert data_map["column_count"] == 6  # 5 standard + 1 optional
        assert data_map["validation_status"] in ("PASSED", "WARNING")
        assert data_map["quality_score"] is not None
        mapped_artifact_id = data_map["artifact_id"]

        # -------------------------------------------------------------
        # 5. Feature engineering & dataset enrichment
        # -------------------------------------------------------------
        fe_payload = {
            "split": {
                "test_size": 0.2,
                "time_column": "timestamp",
                "target_column": "label",
            },
            "cleansing": {
                "drop_duplicates": True,
            },
            "enable_hour_of_day": True,
            "enable_amount_ratios": True,
            "enable_velocity_features": False,
        }
        res_fe = client.post(f"/api/v1/datasets/{dataset_id}/feature-engineering", json=fe_payload)
        assert res_fe.status_code == 201, res_fe.text
        fe_envelope = res_fe.json()
        assert fe_envelope["success"] is True
        assert fe_envelope["statusCode"] == 201
        data_fe = fe_envelope["data"]
        assert data_fe["pipeline_stage"] == "FEATURE_ENGINEERED"
        fe_artifact_id = data_fe["artifact_id"]

        # -------------------------------------------------------------
        # View data lineage inside GET dataset by id
        # -------------------------------------------------------------
        res_get = client.get(f"/api/v1/datasets/{dataset_id}", params={"project_id": project_id})
        assert res_get.status_code == 200, res_get.text
        get_envelope = res_get.json()
        assert get_envelope["success"] is True
        dataset_data = get_envelope["data"]
        assert "lineage" in dataset_data
        lineage_data = dataset_data["lineage"]
        assert len(lineage_data["nodes"]) == 3  # RAW -> MAPPED -> FEATURE_ENGINEERED
        assert len(lineage_data["edges"]) == 2

        # -------------------------------------------------------------
        # Export normalized dataset (raw binary ZIP, not enveloped)
        # -------------------------------------------------------------
        export_payload = {
            "include_train": True,
            "include_test": True,
            "include_pipeline": True,
            "include_schema": True,
            "file_format": "parquet",
        }
        res_export = client.post(
            f"/api/v1/datasets/{dataset_id}/artifacts/{fe_artifact_id}/export",
            json=export_payload,
        )
        assert res_export.status_code == 200, res_export.text
        assert res_export.headers["content-type"] == "application/zip"
        assert len(res_export.content) > 0

        # -------------------------------------------------------------
        #  Delete dataset
        # -------------------------------------------------------------
        res_del = client.delete(f"/api/v1/datasets/{dataset_id}")
        assert res_del.status_code == 200
        assert res_del.json()["success"] is True

        res_check = client.get(f"/api/v1/datasets/{dataset_id}", params={"project_id": project_id})
        assert res_check.status_code == 404
        assert res_check.json()["success"] is False
        assert res_check.json()["statusCode"] == 404


def test_import_dataset_from_presigned_s3_staging_key_copies_and_cleans_staging(monkeypatch):
    from moto import mock_aws
    from usfds_infra.storage.s3_storage import S3FileStorage
    import usfds_server.dependencies as deps
    from usfds_server.dependencies import SYSTEM_USER_ID

    with mock_aws():
        s3_storage = S3FileStorage(
            bucket="usfds",
            access_key="test",
            secret_key="test",
            region="us-east-1",
        )
        with TestClient(app) as client:
            monkeypatch.setattr(deps, "_storage", s3_storage)

            up_res = client.post(
                "/api/v1/storage/presigned-upload",
                json={"filename": "tx.csv", "purpose": "dataset_raw", "content_type": "text/csv"},
            )
            assert up_res.status_code == 200, up_res.text
            object_key = up_res.json()["data"]["object_key"]
            assert object_key.startswith("uploads/dataset_raw/")

            csv_bytes = (
                "TransactionID,TxTime,TxAmount,AccountNo,IsFraud\n"
                "TX_1,2024-01-01 10:00:00,100.0,ACC_1,0\n"
                "TX_2,2024-01-01 10:05:00,250.0,ACC_2,1\n"
            ).encode("utf-8")
            s3_storage.save_bytes(object_key, csv_bytes)
            assert s3_storage.exists(object_key)

            proj_res = client.post("/api/v1/projects", json={"project_name": "Presigned S3 Proj"})
            assert proj_res.status_code == 201
            res = client.post(
                "/api/v1/datasets/import",
                json={
                    "file_path": object_key,
                    "dataset_name": "presigned_s3_ds",
                    "project_id": proj_res.json()["data"]["project_id"],
                },
            )
            assert res.status_code == 201, res.text
            data = res.json()["data"]
            me_res = client.get("/api/v1/auth/me")
            assert me_res.status_code == 200
            assert data["dataset"]["user_id"] == me_res.json()["data"]["user_id"]
            raw_art = data["artifacts"][0]
            assert raw_art["storage_path"].startswith("datasets/")
            assert s3_storage.exists(raw_art["storage_path"])
            assert not s3_storage.exists(object_key)


def test_s3_storage_mode_rejects_server_local_filesystem_paths(monkeypatch, tmp_path):
    from moto import mock_aws
    from usfds_infra.storage.s3_storage import S3FileStorage
    import usfds_server.dependencies as deps

    local_secret = tmp_path / "secret.csv"
    local_secret.write_text(
        "TransactionID,TxTime,TxAmount,AccountNo,IsFraud\n"
        "TX_1,2024-01-01 10:00:00,100.0,ACC_1,0\n",
        encoding="utf-8",
    )

    with mock_aws():
        s3_storage = S3FileStorage(
            bucket="usfds",
            access_key="test",
            secret_key="test",
            region="us-east-1",
        )
        with TestClient(app) as client:
            monkeypatch.setattr(deps, "_storage", s3_storage)

            res_import = client.post(
                "/api/v1/datasets/import",
                json={
                    "file_path": str(local_secret),
                    "dataset_name": "should_fail_local_read",
                    "project_id": str(uuid4()),
                },
            )
            assert res_import.status_code == 404, res_import.text

            res_detect = client.post(
                "/api/v1/detection/jobs",
                json={
                    "project_id": str(uuid4()),
                    "input_file_path": str(local_secret),
                    "use_rules": True,
                },
            )
            assert res_detect.status_code in (400, 404), res_detect.text


def test_local_storage_mode_imports_from_external_local_filesystem_path(tmp_path):
    external_csv = tmp_path / "external_desktop_file.csv"
    external_csv.write_text(
        "TransactionID,TxTime,TxAmount,AccountNo,IsFraud\n"
        "TX_1,2024-01-01 10:00:00,100.0,ACC_1,0\n"
        "TX_2,2024-01-01 10:05:00,250.0,ACC_2,1\n",
        encoding="utf-8",
    )

    with TestClient(app) as client:
        proj_res = client.post("/api/v1/projects", json={"project_name": "Local Storage Proj"})
        assert proj_res.status_code == 201
        res = client.post(
            "/api/v1/datasets/import",
            json={
                "file_path": str(external_csv),
                "dataset_name": "electron_external_ds",
                "project_id": proj_res.json()["data"]["project_id"],
            },
        )
        assert res.status_code == 201, res.text
        data = res.json()["data"]
        assert data["artifacts"][0]["storage_path"].startswith("datasets/")


def _seed_admin_project(session, project_id=None):
	from usfds_core.domain.entities.system import Project
	from usfds_infra.database import SqliteProjectRepository, SqlUserRepository

	admin_id = SqlUserRepository(session).get_by_username("admin").user_id
	pid = project_id or uuid4()
	SqliteProjectRepository(session).save(
		Project(project_id=pid, user_id=admin_id, project_name=f"proj_{pid.hex[:8]}")
	)
	return admin_id, pid


def test_delete_dataset_removes_artifact_files_from_storage(client, server_session_factory, server_settings):
	"""ISS-017: Deleting a dataset removes artifact files stored outside datasets/{dataset_id}/ as well."""
	from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
	from usfds_core.domain.entities.enums import DataClassification, PipelineStage
	from usfds_infra.database import SqliteDatasetArtifactRepository, SqliteDatasetRepository, session_scope

	dataset_id = uuid4()
	artifact_id = uuid4()
	external_rel_path = f"custom_artifacts/{artifact_id}/mapped.parquet"
	full_file = Path(server_settings.storage_dir) / external_rel_path
	full_file.parent.mkdir(parents=True, exist_ok=True)
	full_file.write_bytes(b"parquet-bytes")

	with session_scope(server_session_factory) as session:
		user_id, project_id = _seed_admin_project(session)
		SqliteDatasetRepository(session).save(
			Dataset(
				dataset_id=dataset_id,
				project_id=project_id,
				user_id=user_id,
				dataset_name="ds_cleanup",
				data_classification=DataClassification.INTERNAL,
			)
		)
		SqliteDatasetArtifactRepository(session).save(
			DatasetArtifact(
				artifact_id=artifact_id,
				dataset_id=dataset_id,
				pipeline_stage=PipelineStage.MAPPED,
				storage_path=external_rel_path,
			)
		)

	res = client.delete(f"/api/v1/datasets/{dataset_id}")
	assert res.status_code == 200, res.text
	assert not full_file.exists()


def test_delete_dataset_used_by_active_training_run_returns_409(client, server_session_factory, server_settings):
	"""ISS-003: Deleting a dataset linked to a RUNNING TrainingRun returns 409 Conflict."""
	from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
	from usfds_core.domain.entities.enums import ExecutionType, PipelineStage, TrainingRunStatus
	from usfds_core.domain.entities.model import Model, TrainingRun
	from usfds_infra.database import (
		SqliteDatasetArtifactRepository,
		SqliteDatasetRepository,
		SqliteModelRepository,
		SqliteTrainingRunRepository,
		session_scope,
	)

	dataset_id = uuid4()
	artifact_id = uuid4()
	rel_path = f"datasets/{dataset_id}/raw/data.csv"
	full_file = Path(server_settings.storage_dir) / rel_path
	full_file.parent.mkdir(parents=True, exist_ok=True)
	full_file.write_text("a,b\n1,2\n", encoding="utf-8")

	with session_scope(server_session_factory) as session:
		user_id, project_id = _seed_admin_project(session)
		SqliteDatasetRepository(session).save(
			Dataset(dataset_id=dataset_id, project_id=project_id, user_id=user_id, dataset_name="ds_in_train")
		)
		SqliteDatasetArtifactRepository(session).save(
			DatasetArtifact(
				artifact_id=artifact_id,
				dataset_id=dataset_id,
				pipeline_stage=PipelineStage.RAW,
				storage_path=rel_path,
			)
		)
		model = SqliteModelRepository(session).save(
			Model(project_id=project_id, user_id=user_id, model_name="m1", execution_type=ExecutionType.BUILTIN)
		)
		run = SqliteTrainingRunRepository(session).save(
			TrainingRun(
				project_id=project_id,
				user_id=user_id,
				model_id=model.model_id,
				run_name="active_run",
				status=TrainingRunStatus.RUNNING,
			)
		)
		SqliteTrainingRunRepository(session).link_dataset(run.run_id, artifact_id)

	res = client.delete(f"/api/v1/datasets/{dataset_id}")
	assert res.status_code == 409, res.text
	assert full_file.exists()


def test_delete_dataset_used_by_active_detection_job_returns_409(client, server_session_factory, server_settings):
	"""ISS-003: Deleting a dataset targeted by a PENDING DetectionJob returns 409 Conflict."""
	from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
	from usfds_core.domain.entities.detection import DetectionJob
	from usfds_core.domain.entities.enums import DetectionJobStatus, PipelineStage
	from usfds_infra.database import (
		SqliteDatasetArtifactRepository,
		SqliteDatasetRepository,
		SqliteDetectionJobRepository,
		session_scope,
	)

	dataset_id = uuid4()
	artifact_id = uuid4()
	rel_path = f"datasets/{dataset_id}/raw/data.csv"
	full_file = Path(server_settings.storage_dir) / rel_path
	full_file.parent.mkdir(parents=True, exist_ok=True)
	full_file.write_text("a,b\n1,2\n", encoding="utf-8")

	with session_scope(server_session_factory) as session:
		user_id, project_id = _seed_admin_project(session)
		SqliteDatasetRepository(session).save(
			Dataset(dataset_id=dataset_id, project_id=project_id, user_id=user_id, dataset_name="ds_in_detect")
		)
		SqliteDatasetArtifactRepository(session).save(
			DatasetArtifact(
				artifact_id=artifact_id,
				dataset_id=dataset_id,
				pipeline_stage=PipelineStage.RAW,
				storage_path=rel_path,
			)
		)
		SqliteDetectionJobRepository(session).save(
			DetectionJob(
				project_id=project_id,
				user_id=user_id,
				target_artifact_id=artifact_id,
				input_path=rel_path,
				status=DetectionJobStatus.PENDING,
			)
		)

	res = client.delete(f"/api/v1/datasets/{dataset_id}")
	assert res.status_code == 409, res.text
	assert full_file.exists()


def test_delete_dataset_with_completed_jobs_succeeds(client, server_session_factory):
	"""ISS-003: Deleting a dataset whose TrainingRun and DetectionJob are COMPLETED succeeds."""
	from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
	from usfds_core.domain.entities.detection import DetectionJob
	from usfds_core.domain.entities.enums import DetectionJobStatus, ExecutionType, PipelineStage, TrainingRunStatus
	from usfds_core.domain.entities.model import Model, TrainingRun
	from usfds_infra.database import (
		SqliteDatasetArtifactRepository,
		SqliteDatasetRepository,
		SqliteDetectionJobRepository,
		SqliteModelRepository,
		SqliteTrainingRunRepository,
		session_scope,
	)

	dataset_id = uuid4()
	artifact_id = uuid4()

	with session_scope(server_session_factory) as session:
		user_id, project_id = _seed_admin_project(session)
		SqliteDatasetRepository(session).save(
			Dataset(dataset_id=dataset_id, project_id=project_id, user_id=user_id, dataset_name="ds_completed")
		)
		SqliteDatasetArtifactRepository(session).save(
			DatasetArtifact(
				artifact_id=artifact_id,
				dataset_id=dataset_id,
				pipeline_stage=PipelineStage.RAW,
				storage_path=f"datasets/{dataset_id}/raw/data.csv",
			)
		)
		model = SqliteModelRepository(session).save(
			Model(project_id=project_id, user_id=user_id, model_name="m2", execution_type=ExecutionType.BUILTIN)
		)
		run = SqliteTrainingRunRepository(session).save(
			TrainingRun(
				project_id=project_id,
				user_id=user_id,
				model_id=model.model_id,
				run_name="completed_run",
				status=TrainingRunStatus.COMPLETED,
			)
		)
		SqliteTrainingRunRepository(session).link_dataset(run.run_id, artifact_id)
		SqliteDetectionJobRepository(session).save(
			DetectionJob(
				project_id=project_id,
				user_id=user_id,
				target_artifact_id=artifact_id,
				input_path="datasets/x/raw/data.csv",
				status=DetectionJobStatus.COMPLETED,
			)
		)

	res = client.delete(f"/api/v1/datasets/{dataset_id}")
	assert res.status_code == 200, res.text


def test_export_dataset_api_streams_zip_and_presigned_upload_without_pandas(
	client, server_session_factory, server_settings, monkeypatch
):
	"""ISS-044 (M3): Dataset export endpoint streams ZIP from disk and uploads presigned export without pandas."""
	import csv
	import zipfile
	from moto import mock_aws

	from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
	from usfds_core.domain.entities.enums import DataClassification, PipelineStage, ValidationStatus
	from usfds_infra.database import SqliteDatasetArtifactRepository, SqliteDatasetRepository, session_scope
	from usfds_infra.storage.s3_storage import S3FileStorage
	from usfds_server import dependencies

	dataset_id = uuid4()
	artifact_id = uuid4()
	mapped_rel = f"datasets/{dataset_id}/mapped/{artifact_id}/mapped.parquet"
	mapped_df = pd.DataFrame(
		{
			"event_id": ["EV-1", "EV-2"],
			"timestamp": ["2024-01-01 10:00:00", "2024-01-01 10:05:00"],
			"amount": [120.5, 45.0],
			"user_id": ["U-1", "U-2"],
			"label": [0, 1],
		}
	)
	parquet_bytes = mapped_df.to_parquet(index=False)

	local_file = Path(server_settings.storage_dir) / mapped_rel
	local_file.parent.mkdir(parents=True, exist_ok=True)
	local_file.write_bytes(parquet_bytes)

	with session_scope(server_session_factory) as session:
		user_id, project_id = _seed_admin_project(session)
		SqliteDatasetRepository(session).save(
			Dataset(
				dataset_id=dataset_id,
				project_id=project_id,
				user_id=user_id,
				dataset_name="ds_stream_export",
				data_classification=DataClassification.INTERNAL,
			)
		)
		SqliteDatasetArtifactRepository(session).save(
			DatasetArtifact(
				artifact_id=artifact_id,
				dataset_id=dataset_id,
				pipeline_stage=PipelineStage.MAPPED,
				storage_path=mapped_rel,
				output_paths={"mapped": mapped_rel},
				row_count=2,
				column_count=5,
				validation_status=ValidationStatus.PASSED,
				validation_report={"quality_score": 98.0},
			)
		)

	def _forbid(*args, **kwargs):
		raise AssertionError("pandas export forbidden in ISS-044")

	monkeypatch.setattr(pd, "read_parquet", _forbid)
	monkeypatch.setattr(pd.DataFrame, "to_csv", _forbid)

	tmp_root = Path(tempfile.gettempdir())
	before_dirs = set(tmp_root.glob("usfds_ds_export_*"))

	export_payload = {
		"include_train": True,
		"include_test": False,
		"include_pipeline": False,
		"include_schema": True,
		"file_format": "csv",
	}
	res_local = client.post(
		f"/api/v1/datasets/{dataset_id}/artifacts/{artifact_id}/export",
		json=export_payload,
	)
	assert res_local.status_code == 200, res_local.text
	assert res_local.headers["content-type"] == "application/zip"
	with zipfile.ZipFile(io.BytesIO(res_local.content), "r") as zf:
		assert set(zf.namelist()) == {"train.csv", "schema_metadata.json"}
		rows = list(csv.reader(io.StringIO(zf.read("train.csv").decode("utf-8"))))
		assert rows[0] == ["event_id", "timestamp", "amount", "user_id", "label"]
		assert len(rows) == 3
	assert set(tmp_root.glob("usfds_ds_export_*")) == before_dirs

	with mock_aws():
		s3_storage = S3FileStorage(
			bucket="usfds",
			access_key="test",
			secret_key="test",
			region="us-east-1",
		)
		s3_storage.save_bytes(mapped_rel, parquet_bytes)
		monkeypatch.setattr(dependencies, "_storage", s3_storage)

		res_s3 = client.post(
			f"/api/v1/datasets/{dataset_id}/artifacts/{artifact_id}/export",
			params={"presigned": "true"},
			json=export_payload,
		)
		assert res_s3.status_code == 200, res_s3.text
		s3_data = res_s3.json()["data"]
		assert s3_data["download_url"]
		assert s3_data["object_key"].startswith(f"exports/datasets/{dataset_id}/{artifact_id}/")
		assert s3_storage.exists(s3_data["object_key"])
		with zipfile.ZipFile(io.BytesIO(s3_storage.read_bytes(s3_data["object_key"])), "r") as zf:
			assert set(zf.namelist()) == {"train.csv", "schema_metadata.json"}
		assert set(tmp_root.glob("usfds_ds_export_*")) == before_dirs

