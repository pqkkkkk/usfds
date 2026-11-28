"""Automated worker queue & error-classification guards for usfds-worker (INV-008)."""
from usfds_infra import job_queue
from usfds_worker.main import (
	ANALYTICS_QUEUE_HANDLERS,
	BATCH_INFERENCE_QUEUE_HANDLERS,
	DATA_PIPELINE_QUEUE_HANDLERS,
	NON_RETRYABLE_ERRORS,
	TRAINING_QUEUE_HANDLERS,
	_QUEUE_NAME_BY_KEY,
)
from usfds_worker.testing import _QUEUE_HANDLERS


def test_every_infra_job_constant_is_registered_in_worker_and_inline_queue():
	"""INV-008: Keep job constants in usfds-infra, worker main handlers, and InlineJobQueue in sync."""
	infra_jobs = {
		getattr(job_queue, name)
		for name in dir(job_queue)
		if name.startswith("JOB_") and isinstance(getattr(job_queue, name), str)
	}
	worker_jobs = (
		set(TRAINING_QUEUE_HANDLERS)
		| set(BATCH_INFERENCE_QUEUE_HANDLERS)
		| set(DATA_PIPELINE_QUEUE_HANDLERS)
		| set(ANALYTICS_QUEUE_HANDLERS)
	)
	assert infra_jobs == worker_jobs, (
		f"Job mismatch between usfds_infra.job_queue and usfds_worker.main: "
		f"missing_in_worker={infra_jobs - worker_jobs}, extra_in_worker={worker_jobs - infra_jobs}"
	)

	inline_jobs = {
		job_name
		for handler_map in _QUEUE_HANDLERS.values()
		for job_name in handler_map
	}
	assert infra_jobs == inline_jobs, (
		f"Job mismatch between usfds_infra.job_queue and InlineJobQueue: "
		f"missing_in_inline={infra_jobs - inline_jobs}, extra_in_inline={inline_jobs - infra_jobs}"
	)


def test_every_infra_queue_constant_is_selectable_by_worker_settings():
	"""INV-008: Every QUEUE_* constant in usfds-infra must be exposed in usfds-worker queue selection."""
	infra_queues = {
		getattr(job_queue, name)
		for name in dir(job_queue)
		if name.startswith("QUEUE_") and isinstance(getattr(job_queue, name), str)
	}
	worker_queues = set(_QUEUE_NAME_BY_KEY.values())
	assert infra_queues == worker_queues


def test_non_retryable_errors_cover_deterministic_failures():
	"""INV-008 / ISS-021: Deterministic input/business errors must never be retried by BullMQ."""
	for err_type in (ValueError, LookupError, FileNotFoundError, TypeError, MemoryError):
		assert err_type in NON_RETRYABLE_ERRORS
