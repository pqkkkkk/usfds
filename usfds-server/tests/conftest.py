"""Server test fixtures. Every test gets isolated settings (temp SQLite + temp local storage, sync dispatch).

Fixtures:
	server_settings          autouse; per-test settings, restored automatically (never assign `settings.x = ...` in tests)
	client                   TestClient on the real app, sync dispatch (default mode for API tests)
	client_queue_mode        TestClient with USFDS_DISPATCH_BACKEND=queue; jobs run through InlineJobQueue
	                         (router -> JSON payload -> worker handler). Inspect `client.job_queue.jobs`.
	server_session_factory   session factory of the running app, for seeding / asserting DB state
Shared fixtures (db_engine, session_factory, local_storage, s3_storage, worker_context, inline_job_queue)
come from the plugins below.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest_plugins = ["usfds_infra.testing.pytest_plugin", "usfds_worker.testing"]


@pytest.fixture(autouse=True)
def server_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	from usfds_server.config import settings

	overrides = {
		"db_path": str(tmp_path / "server.db"),
		"storage_dir": str(tmp_path / "storage"),
		"db_url": None,
		"storage_backend": "local",
		"dispatch_backend": "sync",
	}
	for name, value in overrides.items():
		monkeypatch.setattr(settings, name, value)
	yield settings


@pytest.fixture
def client(server_settings):
	from usfds_server.api import app

	with TestClient(app) as test_client:
		yield test_client


@pytest.fixture
def client_queue_mode(server_settings, monkeypatch: pytest.MonkeyPatch):
	from usfds_server import dependencies
	from usfds_server.api import app
	from usfds_worker.handlers import WorkerContext
	from usfds_worker.testing import InlineJobQueue

	monkeypatch.setattr(server_settings, "dispatch_backend", "queue")
	with TestClient(app) as test_client:
		queue = InlineJobQueue(
			lambda: WorkerContext(session_factory=dependencies._session_factory, storage=dependencies.get_storage())
		)
		dependencies._job_queue = queue
		test_client.job_queue = queue
		yield test_client


@pytest.fixture
def server_session_factory(client):
	from usfds_server import dependencies

	return dependencies._session_factory
