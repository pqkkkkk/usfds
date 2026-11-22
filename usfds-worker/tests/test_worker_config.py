"""ISS-012: the analytics queue can run in its own worker (USFDS_WORKER_QUEUES)."""
import pytest

from usfds_worker.config import WorkerSettings
from usfds_worker.main import ANALYTICS_QUEUE_HANDLERS, selected_queue_names


@pytest.fixture
def worker_env(monkeypatch):
	for name, value in {
		"USFDS_DB_URL": "postgresql+psycopg://u:p@db/usfds", "USFDS_S3_ENDPOINT_URL": "http://s3",
		"USFDS_S3_ACCESS_KEY": "k", "USFDS_S3_SECRET_KEY": "s",
	}.items():
		monkeypatch.setenv(name, value)
	monkeypatch.delenv("USFDS_WORKER_QUEUES", raising=False)
	return monkeypatch


def test_worker_runs_all_queues_by_default_and_filters_by_env(worker_env):
	assert WorkerSettings.from_env().enabled_queues == ("training", "batch_inference", "data_pipeline", "analytics")

	worker_env.setenv("USFDS_WORKER_QUEUES", " analytics , data_pipeline ")
	settings = WorkerSettings.from_env()
	assert settings.enabled_queues == ("analytics", "data_pipeline")
	assert selected_queue_names(settings) == ["usfds-analytics", "usfds-data-pipeline"]
	assert "insight_report" in ANALYTICS_QUEUE_HANDLERS


def test_worker_rejects_unknown_queue_name(worker_env):
	worker_env.setenv("USFDS_WORKER_QUEUES", "analytics,bogus")
	with pytest.raises(RuntimeError, match="bogus"):
		WorkerSettings.from_env()
