import os
import shutil
import tempfile
from fastapi.testclient import TestClient
import pytest

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


def test_health_check_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["database"]["type"] == "sqlite"
        assert data["database"]["journal_mode"] == "WAL"
        assert data["storage"]["type"] == "local_filesystem"
        assert data["storage"]["status"] == "ready"


def test_presigned_storage_endpoints_with_s3_backend(monkeypatch):
    from uuid import uuid4
    from usfds_infra.storage.s3_storage import S3FileStorage
    import usfds_server.dependencies as deps

    project_id = str(uuid4())
    sample_key = f"exports/reports/{project_id}/sample.csv"

    class _StubS3Client:
        def __init__(self):
            self.objects = {sample_key: b"id,amount\n1,10.0\n"}

        def head_bucket(self, Bucket):
            return {}

        def head_object(self, Bucket, Key):
            if Key not in self.objects:
                err = Exception("NotFound")
                err.response = {"Error": {"Code": "404"}}
                raise err
            return {"ContentLength": len(self.objects[Key])}

        def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
            return f"http://localhost:9000/{Params['Bucket']}/{Params['Key']}?op={ClientMethod}"

    s3_storage = S3FileStorage(bucket="usfds", client=_StubS3Client())

    with TestClient(app) as client:
        monkeypatch.setattr(deps, "_storage", s3_storage)

        up_res = client.post(
            "/api/v1/storage/presigned-upload",
            json={"filename": "transactions.csv", "purpose": "dataset_raw", "project_id": project_id, "content_type": "text/csv"},
        )
        assert up_res.status_code == 200
        up_data = up_res.json()["data"]
        assert up_data["object_key"].startswith(f"uploads/dataset_raw/{project_id}/")
        assert up_data["object_key"].endswith("/transactions.csv")
        assert "op=put_object" in up_data["upload_url"]

        dl_res = client.get(
            "/api/v1/storage/presigned-download",
            params={"object_key": sample_key, "project_id": project_id, "filename": "custom.csv"},
        )
        assert dl_res.status_code == 200
        dl_data = dl_res.json()["data"]
        assert dl_data["filename"] == "custom.csv"
        assert "op=get_object" in dl_data["download_url"]


def test_cors_allows_configured_origin_with_credentials(client):
	"""ISS-014: Default local dev origin is allowed with credentials."""
	res = client.get("/health", headers={"Origin": "http://localhost:5173"})
	assert res.status_code == 200
	assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
	assert res.headers.get("access-control-allow-credentials") == "true"


def test_cors_rejects_unlisted_origin(client):
	"""ISS-014: Unlisted origin does not receive access-control-allow-origin."""
	res = client.get("/health", headers={"Origin": "https://evil.example.com"})
	assert res.status_code == 200
	assert res.headers.get("access-control-allow-origin") is None


def test_cors_wildcard_disables_credentials():
	"""ISS-014: Wildcard '*' origin disables allow_credentials."""
	from usfds_server.api import build_cors_options

	origins, allow_credentials = build_cors_options("*")
	assert origins == ["*"]
	assert allow_credentials is False

