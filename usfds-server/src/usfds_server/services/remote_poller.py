"""In-server background poller for remote training runs (ISS-009).

Runs as a lightweight asyncio.Task inside FastAPI lifespan so remote compute
providers work without requiring usfds-worker or BullMQ.

DB connection pool hygiene:
- Phase 1: open a short `session_scope` to list RUNNING runs with `external_job_id`,
  copy lightweight metadata tuples, then close the session (returning the connection to the pool).
- Phase 2: call `provider.poll()` over the network with NO DB session held.
- Phase 3: only when a terminal status is returned, open a second short `session_scope`
  to apply the atomic, idempotent state transition and register ModelVersion.
"""
import asyncio
import logging
from typing import Callable, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.providers.base_provider import RemoteProviderRegistry
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteTrainingRunRepository,
	session_scope,
)

logger = logging.getLogger("usfds_server.remote_poller")


class RemoteTrainingPoller:
	"""Periodically polls external compute providers for RUNNING remote TrainingRuns."""

	def __init__(
		self,
		session_factory_getter: Callable[[], Optional[sessionmaker[Session]]],
		provider_registry_getter: Callable[[], Optional[RemoteProviderRegistry]],
		interval_seconds: float = 15.0,
		poll_timeout_seconds: float = 5.0,
	):
		self._get_session_factory = session_factory_getter
		self._get_provider_registry = provider_registry_getter
		self.interval_seconds = max(0.5, float(interval_seconds))
		self.poll_timeout_seconds = max(0.5, float(poll_timeout_seconds))
		self._task: Optional[asyncio.Task[None]] = None
		self._stop_event: Optional[asyncio.Event] = None

	def poll_once(self) -> int:
		"""Run a single poll pass across all active remote runs. Returns number of runs polled."""
		session_factory = self._get_session_factory()
		registry = self._get_provider_registry()
		if session_factory is None or registry is None:
			return 0

		# Phase 1: short read-only session to snapshot active remote runs
		pending_targets: List[Tuple[UUID, str, str]] = []
		with session_scope(session_factory) as session:
			active_runs = SqliteTrainingRunRepository(session).list_active_remote_runs()
			for run in active_runs:
				if not run.external_job_id:
					continue
				provider_id = None
				if isinstance(run.compute_metadata, dict):
					provider_id = run.compute_metadata.get("provider")
				provider_id = provider_id or run.compute_target
				if provider_id:
					pending_targets.append((run.run_id, run.external_job_id, str(provider_id)))

		if not pending_targets:
			return 0

		polled_count = 0
		for run_id, external_job_id, provider_id in pending_targets:
			provider = registry.get(provider_id)
			if provider is None:
				continue

			# Phase 2: network poll with NO DB session held
			try:
				remote_status = provider.poll(
					external_job_id,
					timeout_seconds=self.poll_timeout_seconds,
				)
				polled_count += 1
			except Exception as exc:
				logger.warning(
					"Remote poll failed for run %s (provider=%s, external_job_id=%s): %s",
					run_id,
					provider_id,
					external_job_id,
					exc,
				)
				continue

			if remote_status.state in ("PENDING", "RUNNING"):
				continue

			# Phase 3: short transactional write session to apply terminal status atomically
			try:
				with session_scope(session_factory) as session:
					service = TrainingOrchestrationService(
						dispatcher=SynchronousRunDispatcher(executor_func=lambda _p: None),
						training_run_repo=SqliteTrainingRunRepository(session),
						model_version_repo=SqliteModelVersionRepository(session),
						model_repo=SqliteModelRepository(session),
						dataset_artifact_repo=SqliteDatasetArtifactRepository(session),
						dataset_repo=SqliteDatasetRepository(session),
						provider_registry=registry,
					)
					service.apply_remote_status(run_id, remote_status)
			except Exception as exc:
				logger.error(
					"Failed to persist remote training status for run %s: %s",
					run_id,
					exc,
					exc_info=True,
				)

		return polled_count

	async def _run_loop(self) -> None:
		assert self._stop_event is not None
		while not self._stop_event.is_set():
			try:
				await asyncio.to_thread(self.poll_once)
			except asyncio.CancelledError:
				break
			except Exception as exc:
				logger.warning("RemoteTrainingPoller iteration error: %s", exc)
			try:
				await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
			except asyncio.TimeoutError:
				continue

	def start(self) -> None:
		if self._task is not None and not self._task.done():
			return
		self._stop_event = asyncio.Event()
		self._task = asyncio.create_task(self._run_loop(), name="usfds-remote-training-poller")

	async def stop(self) -> None:
		if self._stop_event is not None:
			self._stop_event.set()
		if self._task is not None:
			self._task.cancel()
			try:
				await self._task
			except asyncio.CancelledError:
				pass
			self._task = None
