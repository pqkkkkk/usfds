"""Acceptance tests for in-server RemoteTrainingPoller (no usfds-worker / BullMQ required, ISS-009)."""
from typing import List, Optional, Tuple
from uuid import uuid4

from usfds_core.domain.entities.enums import (
	ExecutionType,
	ModelVersionStatus,
	TrainingRunStatus,
)
from usfds_core.domain.entities.model import Model, TrainingRun
from usfds_core.domain.entities.system import Project
from usfds_core.domain.schemas.training_payload import (
	RemoteJobStatus,
	RemoteTrainingJobSpec,
	TrainingRunResult,
)
from usfds_core.services.training.providers.base_provider import (
	IRemoteComputeProvider,
	RemoteProviderRegistry,
)
from usfds_infra.database import (
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteProjectRepository,
	SqliteTrainingRunRepository,
	SqlUserRepository,
	session_scope,
)
from usfds_server.services.remote_poller import RemoteTrainingPoller


class _SequencedFakeProvider(IRemoteComputeProvider):
	def __init__(self, statuses: List[RemoteJobStatus]):
		self._statuses = list(statuses)
		self.poll_calls: List[str] = []

	@property
	def provider_id(self) -> str:
		return "modal"

	@property
	def display_name(self) -> str:
		return "Modal Serverless"

	def is_available(self) -> Tuple[bool, Optional[str]]:
		return True, None

	def submit(self, job_spec: RemoteTrainingJobSpec) -> str:
		return "fc-1"

	def poll(self, external_job_id: str, timeout_seconds: float = 5.0) -> RemoteJobStatus:
		self.poll_calls.append(external_job_id)
		if self._statuses:
			return self._statuses.pop(0)
		return RemoteJobStatus(state="RUNNING")


def test_remote_training_poller_syncs_running_jobs_without_worker(
	client,
	server_session_factory,
	monkeypatch,
):
	"""ISS-009: RemoteTrainingPoller polls RUNNING remote runs on the server and registers ModelVersion without worker."""
	# Seed project, model, 1 RUNNING remote run, 1 local RUNNING run (ignored), and 1 COMPLETED remote run (ignored)
	project_id = uuid4()
	model_id = uuid4()
	remote_run_id = uuid4()
	local_run_id = uuid4()
	done_run_id = uuid4()

	with session_scope(server_session_factory) as session:
		admin = SqlUserRepository(session).get_by_username("admin")
		assert admin is not None
		SqliteProjectRepository(session).save(
			Project(project_id=project_id, user_id=admin.user_id, project_name="PollerProj")
		)
		SqliteModelRepository(session).save(
			Model(
				model_id=model_id,
				project_id=project_id,
				user_id=admin.user_id,
				model_name="random_forest",
				execution_type=ExecutionType.BUILTIN,
			)
		)
		run_repo = SqliteTrainingRunRepository(session)
		run_repo.save(
			TrainingRun(
				run_id=remote_run_id,
				project_id=project_id,
				user_id=admin.user_id,
				model_id=model_id,
				run_name="remote-modal-run",
				status=TrainingRunStatus.RUNNING,
				compute_target="modal",
				external_job_id="fc-1",
				compute_metadata={"provider": "modal", "resolved_target": "modal"},
				created_by="admin",
			)
		)
		run_repo.save(
			TrainingRun(
				run_id=local_run_id,
				project_id=project_id,
				user_id=admin.user_id,
				model_id=model_id,
				run_name="local-run",
				status=TrainingRunStatus.RUNNING,
				compute_target="local",
				external_job_id=None,
				created_by="admin",
			)
		)
		run_repo.save(
			TrainingRun(
				run_id=done_run_id,
				project_id=project_id,
				user_id=admin.user_id,
				model_id=model_id,
				run_name="already-done-remote",
				status=TrainingRunStatus.COMPLETED,
				compute_target="modal",
				external_job_id="fc-old",
				compute_metadata={"provider": "modal", "resolved_target": "modal"},
				created_by="admin",
			)
		)

	completed_result = TrainingRunResult(
		run_id=remote_run_id,
		is_success=True,
		metrics={"accuracy": 0.94, "precision": 0.9, "recall": 0.88, "f1_score": 0.89},
		artifact_uri=f"models/{model_id}/runs/{remote_run_id}/model.joblib",
		checksum_sha256="deadbeef",
		framework="scikit-learn",
		duration_seconds=15,
	)
	fake_provider = _SequencedFakeProvider(
		statuses=[
			RemoteJobStatus(state="RUNNING"),
			RemoteJobStatus(state="COMPLETED", result=completed_result),
		]
	)
	registry = RemoteProviderRegistry()
	registry.register(fake_provider)

	poller = RemoteTrainingPoller(
		session_factory_getter=lambda: server_session_factory,
		provider_registry_getter=lambda: registry,
		interval_seconds=1.0,
	)

	# Tick 1: still RUNNING
	polled_1 = poller.poll_once()
	assert polled_1 == 1
	assert fake_provider.poll_calls == ["fc-1"]
	with session_scope(server_session_factory) as session:
		r1 = SqliteTrainingRunRepository(session).get_by_id(remote_run_id)
		assert r1 is not None and r1.status == TrainingRunStatus.RUNNING
		assert r1.version_id is None

	# Tick 2: COMPLETED + creates exactly 1 CANDIDATE ModelVersion
	polled_2 = poller.poll_once()
	assert polled_2 == 1
	assert fake_provider.poll_calls == ["fc-1", "fc-1"]
	with session_scope(server_session_factory) as session:
		r2 = SqliteTrainingRunRepository(session).get_by_id(remote_run_id)
		assert r2 is not None and r2.status == TrainingRunStatus.COMPLETED
		assert r2.version_id is not None
		versions = SqliteModelVersionRepository(session).list_by_model(model_id, project_id=project_id)
		assert len(versions) == 1
		assert versions[0].status == ModelVersionStatus.CANDIDATE

	# Tick 3: nothing left to poll
	polled_3 = poller.poll_once()
	assert polled_3 == 0
	assert len(fake_provider.poll_calls) == 2
