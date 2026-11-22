import asyncio
import logging
from pathlib import Path
import signal
from typing import Any, Callable, Dict

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from usfds_infra.database import create_postgres_engine, create_session_factory
from usfds_infra.job_queue import (
	JOB_BATCH_INFERENCE,
	JOB_DATASET_INGESTION,
	JOB_FEATURE_ENGINEERING,
	JOB_INSIGHT_REPORT,
	JOB_PLUGIN_DRY_RUN,
	JOB_RULE_BACKTEST,
	JOB_SCHEMA_MAPPING,
	JOB_TRAINING_RUN,
	QUEUE_ANALYTICS,
	QUEUE_BATCH_INFERENCE,
	QUEUE_DATA_PIPELINE,
	QUEUE_TRAINING,
	build_bullmq_opts,
)
from usfds_infra.storage.s3_storage import S3FileStorage

from usfds_worker.config import WorkerSettings
from usfds_worker.handlers import (
	WorkerContext,
	handle_batch_inference,
	handle_dataset_ingestion,
	handle_feature_engineering,
	handle_insight_report,
	handle_plugin_dry_run,
	handle_rule_backtest,
	handle_schema_mapping,
	handle_training_run,
)

logger = logging.getLogger("usfds_worker")

HandlerFn = Callable[[WorkerContext, Dict[str, Any]], Any]

TRAINING_QUEUE_HANDLERS: Dict[str, HandlerFn] = {
	JOB_TRAINING_RUN: handle_training_run,
	JOB_PLUGIN_DRY_RUN: handle_plugin_dry_run,
}

BATCH_INFERENCE_QUEUE_HANDLERS: Dict[str, HandlerFn] = {
	JOB_BATCH_INFERENCE: handle_batch_inference,
	JOB_RULE_BACKTEST: handle_rule_backtest,
}

DATA_PIPELINE_QUEUE_HANDLERS: Dict[str, HandlerFn] = {
	JOB_DATASET_INGESTION: handle_dataset_ingestion,
	JOB_SCHEMA_MAPPING: handle_schema_mapping,
	JOB_FEATURE_ENGINEERING: handle_feature_engineering,
}

ANALYTICS_QUEUE_HANDLERS: Dict[str, HandlerFn] = {
	JOB_INSIGHT_REPORT: handle_insight_report,
}

_QUEUE_NAME_BY_KEY = {
	"training": QUEUE_TRAINING,
	"batch_inference": QUEUE_BATCH_INFERENCE,
	"data_pipeline": QUEUE_DATA_PIPELINE,
	"analytics": QUEUE_ANALYTICS,
}


def selected_queue_names(settings: WorkerSettings) -> list[str]:
	"""BullMQ queue names this worker process listens on (USFDS_WORKER_QUEUES)."""
	return [_QUEUE_NAME_BY_KEY[key] for key in settings.enabled_queues]


NON_RETRYABLE_ERRORS = (ValueError, LookupError, FileNotFoundError, TypeError, MemoryError)


def _make_processor(
	ctx: WorkerContext,
	handler_or_map: HandlerFn | Dict[str, HandlerFn],
	default_handler: HandlerFn | None = None,
):
	async def processor(job, token):
		if callable(handler_or_map):
			target_handler = handler_or_map
		else:
			job_name = getattr(job, "name", None)
			target_handler = handler_or_map.get(job_name) or default_handler
			if target_handler is None:
				raise ValueError(f"Unknown job name '{job_name}'")
		try:
			# Executors are CPU-bound and blocking: keep them off the event loop so BullMQ can renew job locks.
			return await asyncio.to_thread(target_handler, ctx, job.data)
		except Exception as e:
			# Preserve exception type prefix in failedReason for BullMQJobQueue.enqueue_and_wait()
			message = f"{type(e).__name__}: {e}"
			if isinstance(e, NON_RETRYABLE_ERRORS):
				# Deterministic business/input errors: retrying cannot help (ISS-021).
				from bullmq import UnrecoverableError

				raise UnrecoverableError(message) from e
			raise RuntimeError(message) from e

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
	# DEPRECATED [26-11-22] ISS-012: fixed 3-worker list replaced by processors map filtered by USFDS_WORKER_QUEUES.
	# workers = [
	# 	Worker(
	# 		QUEUE_TRAINING,
	# 		_make_processor(ctx, TRAINING_QUEUE_HANDLERS, default_handler=handle_training_run),
	# 		opts,
	# 	),
	# 	Worker(
	# 		QUEUE_BATCH_INFERENCE,
	# 		_make_processor(ctx, BATCH_INFERENCE_QUEUE_HANDLERS, default_handler=handle_batch_inference),
	# 		opts,
	# 	),
	# 	Worker(
	# 		QUEUE_DATA_PIPELINE,
	# 		_make_processor(ctx, DATA_PIPELINE_QUEUE_HANDLERS),
	# 		opts,
	# 	),
	# ]
	# logger.info(
	# 	f"usfds-worker listening on {QUEUE_TRAINING}, {QUEUE_BATCH_INFERENCE}, {QUEUE_DATA_PIPELINE}"
	# )
	processors = {
		QUEUE_TRAINING: _make_processor(ctx, TRAINING_QUEUE_HANDLERS, default_handler=handle_training_run),
		QUEUE_BATCH_INFERENCE: _make_processor(ctx, BATCH_INFERENCE_QUEUE_HANDLERS, default_handler=handle_batch_inference),
		QUEUE_DATA_PIPELINE: _make_processor(ctx, DATA_PIPELINE_QUEUE_HANDLERS),
		QUEUE_ANALYTICS: _make_processor(ctx, ANALYTICS_QUEUE_HANDLERS),
	}
	queue_names = selected_queue_names(settings)
	workers = [Worker(name, processors[name], opts) for name in queue_names]
	logger.info(f"usfds-worker listening on {', '.join(queue_names)}")

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
