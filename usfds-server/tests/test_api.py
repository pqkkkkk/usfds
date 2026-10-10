import os
import shutil
import tempfile
from fastapi.testclient import TestClient
import pytest

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
