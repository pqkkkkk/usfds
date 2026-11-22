"""ISS-021: worker error classification (retry vs. no retry) and handler idempotency on redelivery."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from bullmq import UnrecoverableError

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus, TrainingRunStatus
from usfds_core.domain.entities.model import TrainingRun
from usfds_core.domain.entities.system import Project, User
from usfds_infra.database import (
	SqliteDetectionJobRepository,
	SqliteProjectRepository,
	SqliteTrainingRunRepository,
	SqlUserRepository,
)

from usfds_worker.handlers import handle_batch_inference, handle_training_run
from usfds_worker.main import _make_processor


def _run_processor(error: Exception):
	def handler(ctx, data):
		raise error

	processor = _make_processor(None, {"job": handler})
	return asyncio.run(processor(SimpleNamespace(name="job", data={}), "token"))


@pytest.mark.parametrize(
	"error, expected_message",
	[
		(ValueError("x"), "ValueError: x"),
		(FileNotFoundError("y"), "FileNotFoundError: y"),
		(LookupError("z"), "LookupError: z"),
	],
)
def test_processor_marks_business_errors_unrecoverable(error, expected_message):
	with pytest.raises(UnrecoverableError) as exc_info:
		_run_processor(error)
	assert str(exc_info.value) == expected_message


def test_processor_keeps_transient_errors_retryable():
	with pytest.raises(RuntimeError) as exc_info:
		_run_processor(OSError("s3 down"))
	assert not isinstance(exc_info.value, UnrecoverableError)
	assert str(exc_info.value) == "OSError: s3 down"


def _seed_user_and_project(session):
	user_id, project_id = uuid4(), uuid4()
	SqlUserRepository(session).save(
		User(user_id=user_id, username=f"u_{user_id.hex[:8]}", email=f"{user_id.hex[:8]}@usfds.local", full_name="W", password_hash="h")
	)
	SqliteProjectRepository(session).save(Project(project_id=project_id, user_id=user_id, project_name=f"p_{project_id.hex[:8]}"))
	return user_id, project_id


def test_training_and_batch_handlers_skip_records_already_in_terminal_state(worker_context, session_factory):
	run_id, job_id = uuid4(), uuid4()
	with session_factory() as s:
		user_id, project_id = _seed_user_and_project(s)
		SqliteTrainingRunRepository(s).save(
			TrainingRun(run_name="t", run_id=run_id, project_id=project_id, user_id=user_id, status=TrainingRunStatus.COMPLETED)
		)
		SqliteDetectionJobRepository(s).save(
			DetectionJob(
				job_id=job_id, project_id=project_id, user_id=user_id, job_name="b",
				status=DetectionJobStatus.FAILED, error_message="boom",
			)
		)
		s.commit()

	with patch("usfds_worker.handlers.TrainingRunExecutor") as training_executor, patch(
		"usfds_worker.handlers.BatchInferenceExecutor"
	) as batch_executor:
		handle_training_run(worker_context, {
			"run_id": str(run_id), "model_id": str(uuid4()),
			"model_name": "random_forest", "train_storage_path": "t.parquet",
		})
		handle_batch_inference(worker_context, {
			"job_id": str(job_id), "project_id": str(project_id),
			"input_path": "in.csv", "output_storage_path": "out.parquet",
		})

	training_executor.assert_not_called()
	batch_executor.assert_not_called()
	with session_factory() as s:
		assert SqliteTrainingRunRepository(s).get_by_id(run_id).status == TrainingRunStatus.COMPLETED
		job = SqliteDetectionJobRepository(s).get_by_id(job_id)
	assert job.status == DetectionJobStatus.FAILED
	assert job.error_message == "boom"
