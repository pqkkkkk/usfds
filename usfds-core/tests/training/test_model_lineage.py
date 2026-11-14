from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import (
	DatasetRole,
	ModelVersionStatus,
	PipelineStage,
	TrainingRunStatus,
	ValidationStatus,
)
from usfds_core.domain.entities.model import Model, ModelVersion, RunDataset, TrainingRun
from usfds_core.repositories.in_memory_repos import (
	InMemoryDatasetArtifactRepository,
	InMemoryModelRepository,
	InMemoryModelVersionRepository,
	InMemoryTrainingRunRepository,
)
from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_core.storage.in_memory_storage import InMemoryFileStorage


def _build_service():
	artifact_repo = InMemoryDatasetArtifactRepository()
	model_repo = InMemoryModelRepository()
	version_repo = InMemoryModelVersionRepository()
	run_repo = InMemoryTrainingRunRepository()
	dispatcher = SynchronousRunDispatcher(TrainingRunExecutor(InMemoryFileStorage()))
	service = TrainingOrchestrationService(
		dispatcher=dispatcher,
		training_run_repo=run_repo,
		model_version_repo=version_repo,
		model_repo=model_repo,
		dataset_artifact_repo=artifact_repo,
	)
	return service, artifact_repo, model_repo, version_repo, run_repo


def test_get_model_version_lineage_traces_full_upstream_chain():
	"""ISS-008: Trace RAW -> MAPPED -> FEATURE_ENGINEERED -> TRAINING_RUN -> MODEL_VERSION."""
	service, artifact_repo, model_repo, version_repo, run_repo = _build_service()
	t0 = datetime(2026, 11, 14, 1, 0, 0, tzinfo=timezone.utc)
	dataset_id = uuid4()
	project_id = uuid4()

	raw = DatasetArtifact(
		dataset_id=dataset_id,
		storage_path="raw.parquet",
		pipeline_stage=PipelineStage.RAW,
		validation_status=ValidationStatus.PASSED,
		row_count=100,
		column_count=10,
		created_at=t0,
	)
	mapped = DatasetArtifact(
		dataset_id=dataset_id,
		parent_artifact_id=raw.artifact_id,
		storage_path="mapped.parquet",
		pipeline_stage=PipelineStage.MAPPED,
		validation_status=ValidationStatus.PASSED,
		row_count=100,
		column_count=10,
		created_at=t0 + timedelta(minutes=1),
	)
	fe = DatasetArtifact(
		dataset_id=dataset_id,
		parent_artifact_id=mapped.artifact_id,
		storage_path="fe.parquet",
		pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
		validation_status=ValidationStatus.PASSED,
		row_count=100,
		column_count=18,
		created_at=t0 + timedelta(minutes=2),
	)
	artifact_repo.save(raw)
	artifact_repo.save(mapped)
	artifact_repo.save(fe)

	model = Model(model_name="rf_test", display_name="Random Forest", user_id=uuid4())
	model_repo.save(model)

	run = TrainingRun(
		run_name="run-001",
		project_id=project_id,
		model_id=model.model_id,
		status=TrainingRunStatus.COMPLETED,
		created_at=t0 + timedelta(minutes=3),
	)
	version = ModelVersion(
		model_id=model.model_id,
		project_id=project_id,
		run_id=run.run_id,
		semver="1.0.0",
		artifact_uri="models/rf/1.0.0/model.joblib",
		checksum_sha256="a" * 64,
		status=ModelVersionStatus.CANDIDATE,
		registered_at=t0 + timedelta(minutes=4),
	)
	run.version_id = version.version_id

	run_repo.save(run)
	run_repo.link_dataset(run.run_id, fe.artifact_id, DatasetRole.TRAIN)
	version_repo.save(version)

	graph = service.get_model_version_lineage(version.version_id)

	assert graph.root_version_id == str(version.version_id)
	assert graph.root_run_id == str(run.run_id)
	assert [n.stage for n in graph.nodes] == [
		"RAW",
		"MAPPED",
		"FEATURE_ENGINEERED",
		"TRAINING_RUN",
		"MODEL_VERSION",
	]
	assert [(e.source, e.target) for e in graph.edges] == [
		(str(raw.artifact_id), str(mapped.artifact_id)),
		(str(mapped.artifact_id), str(fe.artifact_id)),
		(str(fe.artifact_id), str(run.run_id)),
		(str(run.run_id), str(version.version_id)),
	]


def test_get_training_run_lineage_without_model_version():
	"""ISS-008: Failed/incomplete TrainingRun without ModelVersion still returns DatasetArtifact -> TRAINING_RUN."""
	service, artifact_repo, model_repo, _, run_repo = _build_service()
	t0 = datetime(2026, 11, 14, 1, 0, 0, tzinfo=timezone.utc)
	dataset_id = uuid4()

	raw = DatasetArtifact(
		dataset_id=dataset_id,
		storage_path="raw.parquet",
		pipeline_stage=PipelineStage.RAW,
		validation_status=ValidationStatus.PASSED,
		created_at=t0,
	)
	artifact_repo.save(raw)

	model = Model(model_name="xgb_test", display_name="XGBoost", user_id=uuid4())
	model_repo.save(model)

	run = TrainingRun(
		run_name="run-failed",
		model_id=model.model_id,
		status=TrainingRunStatus.FAILED,
		version_id=None,
		created_at=t0 + timedelta(minutes=1),
	)
	run_repo.save(run)
	run_repo.link_dataset(run.run_id, raw.artifact_id, DatasetRole.TRAIN)

	graph = service.get_training_run_lineage(run.run_id)

	assert graph.root_run_id == str(run.run_id)
	assert graph.root_version_id is None
	assert [n.stage for n in graph.nodes] == ["RAW", "TRAINING_RUN"]
	assert [(e.source, e.target) for e in graph.edges] == [
		(str(raw.artifact_id), str(run.run_id)),
	]


def test_get_model_version_lineage_raises_when_not_found():
	"""ISS-008: Missing version_id raises ValueError."""
	service, *_ = _build_service()
	with pytest.raises(ValueError, match="not found"):
		service.get_model_version_lineage(uuid4())
