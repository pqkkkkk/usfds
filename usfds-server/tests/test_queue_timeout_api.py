"""ISS-021: queue wait timeout is mapped to a 504 ApiResponse envelope (no raw 500)."""
import pytest

from usfds_infra.job_queue import QueueWaitTimeoutError

from .test_queue_mode_api import _import_payload, _write_raw_csv


@pytest.mark.parametrize("cancelled", [True, False])
def test_queue_wait_timeout_returns_504_envelope(client_queue_mode, server_settings, monkeypatch, cancelled):
	payload = _import_payload(_write_raw_csv(server_settings.storage_dir), client_queue_mode)

	def _raise_timeout(*args, **kwargs):
		raise QueueWaitTimeoutError("ingest-abc", cancelled=cancelled)

	monkeypatch.setattr(client_queue_mode.job_queue, "enqueue_and_wait", _raise_timeout)

	res = client_queue_mode.post("/api/v1/datasets/import", json=payload)

	assert res.status_code == 504, res.text
	body = res.json()
	assert body["success"] is False
	assert "ingest-abc" not in body["message"] and "ingest-abc" not in str(body["error"])
	assert ("đã bị hủy" in body["message"]) is cancelled
	assert body["data"]["job_id"] == "ingest-abc"
