import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Coroutine, Dict, Optional

from usfds_infra.database.engine import to_psycopg_conninfo

QUEUE_TRAINING = "usfds-training"
QUEUE_BATCH_INFERENCE = "usfds-batch-inference"
JOB_TRAINING_RUN = "training_run"
JOB_BATCH_INFERENCE = "batch_inference"
DEFAULT_SCHEMA = "bullmq"


def build_bullmq_opts(db_url: str, schema: str = DEFAULT_SCHEMA) -> Dict[str, Any]:
	"""BullMQ options for the PostgreSQL backend (tables live in `schema`, migrated automatically)."""
	return {
		"backend": "postgres",
		"connection": to_psycopg_conninfo(db_url),
		"schema": schema,
	}


def run_sync(coro: Coroutine[Any, Any, Any]) -> Any:
	"""Run a coroutine from sync code, also when called from a thread that already has a running event loop."""
	try:
		asyncio.get_running_loop()
	except RuntimeError:
		return asyncio.run(coro)
	with ThreadPoolExecutor(max_workers=1) as pool:
		return pool.submit(asyncio.run, coro).result()


class BullMQJobQueue:
	"""Producer-side wrapper over BullMQ (PostgreSQL backend) usable from synchronous server code.

	A short-lived `Queue` is opened per enqueue: enqueues are rare (one per training run or
	detection job) and this avoids binding a connection pool to a specific event loop.
	"""

	def __init__(
		self,
		db_url: str,
		schema: str = DEFAULT_SCHEMA,
		queue_factory: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
	):
		self._opts = build_bullmq_opts(db_url, schema)
		self._queue_factory = queue_factory

	def _make_queue(self, queue_name: str) -> Any:
		if self._queue_factory is not None:
			return self._queue_factory(queue_name, self._opts)
		from bullmq import Queue

		return Queue(queue_name, self._opts)

	def enqueue(
		self,
		queue_name: str,
		job_name: str,
		data: Dict[str, Any],
		job_id: Optional[str] = None,
		attempts: int = 1,
		backoff_ms: int = 5000,
	) -> None:
		job_opts: Dict[str, Any] = {
			"attempts": attempts,
			"backoff": {"type": "exponential", "delay": backoff_ms},
			"removeOnComplete": False,
			"removeOnFail": False,
		}
		if job_id:
			job_opts["jobId"] = job_id

		async def _add() -> None:
			queue = self._make_queue(queue_name)
			try:
				await queue.add(job_name, data, job_opts)
			finally:
				await queue.close()

		run_sync(_add())
