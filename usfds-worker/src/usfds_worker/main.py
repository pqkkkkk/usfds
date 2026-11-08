import asyncio
import logging
import signal
from typing import Any, Callable, Dict

from usfds_infra.database import create_postgres_engine, create_session_factory
from usfds_infra.job_queue import QUEUE_BATCH_INFERENCE, QUEUE_TRAINING, build_bullmq_opts
from usfds_infra.storage.s3_storage import S3FileStorage

from usfds_worker.config import WorkerSettings
from usfds_worker.handlers import WorkerContext, handle_batch_inference, handle_training_run

logger = logging.getLogger("usfds_worker")


def _make_processor(ctx: WorkerContext, handler: Callable[[WorkerContext, Dict[str, Any]], None]):
	async def processor(job, token):
		# Executors are CPU-bound and blocking: keep them off the event loop so BullMQ can renew job locks.
		await asyncio.to_thread(handler, ctx, job.data)

	return processor


async def _serve(settings: WorkerSettings) -> None:
	from bullmq import Worker

	engine = create_postgres_engine(settings.db_url)
	ctx = WorkerContext(
		session_factory=create_session_factory(engine),
		storage=S3FileStorage(
			bucket=settings.s3_bucket,
			endpoint_url=settings.s3_endpoint_url,
			access_key=settings.s3_access_key,
			secret_key=settings.s3_secret_key,
			region=settings.s3_region,
		),
	)
	opts = {
		**build_bullmq_opts(settings.db_url, settings.bullmq_schema),
		"concurrency": settings.concurrency,
		"lockDuration": settings.lock_duration_ms,
	}
	workers = [
		Worker(QUEUE_TRAINING, _make_processor(ctx, handle_training_run), opts),
		Worker(QUEUE_BATCH_INFERENCE, _make_processor(ctx, handle_batch_inference), opts),
	]
	logger.info(f"usfds-worker listening on {QUEUE_TRAINING}, {QUEUE_BATCH_INFERENCE}")

	stop = asyncio.Event()
	loop = asyncio.get_running_loop()
	for sig in (signal.SIGINT, signal.SIGTERM):
		loop.add_signal_handler(sig, stop.set)
	await stop.wait()

	logger.info("Shutting down usfds-worker...")
	await asyncio.gather(*(w.close() for w in workers))
	engine.dispose()


def run_worker() -> None:
	"""CLI entrypoint: `usfds-worker`."""
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
	asyncio.run(_serve(WorkerSettings.from_env()))


if __name__ == "__main__":
	run_worker()
