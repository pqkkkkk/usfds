"""Test double for BullMQJobQueue: runs worker handlers in-process (no PostgreSQL, no BullMQ).

It exercises the same path as production queue mode, minus the transport:
	server router  ->  enqueue / enqueue_and_wait  ->  JSON round-trip  ->  worker handler map  ->  handler

Enable the fixtures in `tests/conftest.py`:
	pytest_plugins = ["usfds_infra.testing.pytest_plugin", "usfds_worker.testing"]
"""
import json
from typing import Any, Callable, Dict, List, Optional

import pytest

from usfds_infra.job_queue import QUEUE_BATCH_INFERENCE, QUEUE_DATA_PIPELINE, QUEUE_TRAINING
from usfds_infra.job_queue.bullmq_queue import raise_from_failed_reason
from usfds_worker.handlers import WorkerContext
from usfds_worker.main import (
	BATCH_INFERENCE_QUEUE_HANDLERS,
	DATA_PIPELINE_QUEUE_HANDLERS,
	TRAINING_QUEUE_HANDLERS,
)

_QUEUE_HANDLERS = {
	QUEUE_TRAINING: TRAINING_QUEUE_HANDLERS,
	QUEUE_BATCH_INFERENCE: BATCH_INFERENCE_QUEUE_HANDLERS,
	QUEUE_DATA_PIPELINE: DATA_PIPELINE_QUEUE_HANDLERS,
}


class InlineJobQueue:
	"""Drop-in replacement for `BullMQJobQueue` (same `enqueue` / `enqueue_and_wait` signatures).

	- Payloads are JSON round-tripped exactly like BullMQ stores them, so non-serializable data fails here too.
	- Failures are converted with the same "<ExceptionType>: <message>" contract as the real worker + producer.
	- Every job is recorded in `self.jobs` for assertions.
	"""

	def __init__(self, context_factory: Callable[[], WorkerContext]):
		self._context_factory = context_factory
		self.jobs: List[Dict[str, Any]] = []

	def _run(self, queue_name: str, job_name: str, data: Dict[str, Any]) -> Any:
		handlers = _QUEUE_HANDLERS.get(queue_name)
		if handlers is None or job_name not in handlers:
			raise ValueError(f"Unknown job '{job_name}' on queue '{queue_name}'")
		payload = json.loads(json.dumps(data, allow_nan=False))
		record: Dict[str, Any] = {"queue": queue_name, "name": job_name, "data": payload, "state": "active"}
		self.jobs.append(record)
		try:
			result = handlers[job_name](self._context_factory(), payload)
		except Exception as e:
			record["state"] = "failed"
			record["failed_reason"] = f"{type(e).__name__}: {e}"
			raise
		record["state"] = "completed"
		record["return_value"] = json.loads(json.dumps(result, allow_nan=False)) if result is not None else None
		return record["return_value"]

	def enqueue(
		self,
		queue_name: str,
		job_name: str,
		data: Dict[str, Any],
		job_id: Optional[str] = None,
		attempts: int = 1,
		backoff_ms: int = 5000,
	) -> None:
		# Fire-and-forget in production: a handler failure is recorded, never raised to the producer.
		# Serialization errors still raise, as `queue.add` would.
		json.dumps(data, allow_nan=False)
		try:
			self._run(queue_name, job_name, data)
		except Exception:
			pass

	def enqueue_and_wait(
		self,
		queue_name: str,
		job_name: str,
		data: Dict[str, Any],
		job_id: Optional[str] = None,
		timeout_seconds: float = 300.0,
		poll_interval_seconds: float = 0.25,
	) -> Any:
		try:
			return self._run(queue_name, job_name, data)
		except Exception as e:
			raise_from_failed_reason(f"{type(e).__name__}: {e}")


@pytest.fixture
def worker_context(session_factory, local_storage) -> WorkerContext:
	return WorkerContext(session_factory=session_factory, storage=local_storage)


@pytest.fixture
def inline_job_queue(worker_context) -> InlineJobQueue:
	return InlineJobQueue(lambda: worker_context)
