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


@pytest.fixture(autouse=True)
def temporary_environment():
    temp_dir = tempfile.mkdtemp(prefix="usfds_server_test_")
    db_file = os.path.join(temp_dir, "test.db")
    storage_path = os.path.join(temp_dir, "storage")

    settings.db_path = db_file
    settings.storage_dir = storage_path

    yield

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_end_to_end_data_management_pipeline():
    with TestClient(app) as client:
        project_id = str(uuid4())
        user_id = str(uuid4())

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
        assert len(list_envelope["data"]) == 1

        # -------------------------------------------------------------
        # 3. Retrieve specific artifact details (including profiling & validation report)
        # -------------------------------------------------------------
        res_art = client.get(f"/api/v1/datasets/{dataset_id}/artifacts/{raw_artifact_id}")
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
        res_get = client.get(f"/api/v1/datasets/{dataset_id}")
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

        res_check = client.get(f"/api/v1/datasets/{dataset_id}")
        assert res_check.status_code == 404
        assert res_check.json()["success"] is False
        assert res_check.json()["statusCode"] == 404
