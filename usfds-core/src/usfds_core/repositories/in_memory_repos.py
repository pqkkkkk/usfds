from typing import Dict, List, Optional, Union
from uuid import UUID

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import DatasetRole
from usfds_core.domain.entities.model import Model, ModelVersion, RunDataset, TrainingRun
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_model_repo import IModelRepository
from usfds_core.repositories.base_model_version_repo import IModelVersionRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository


class InMemoryModelRepository(IModelRepository):
    """In-memory store for models."""

    def __init__(self):
        self._models: Dict[UUID, Model] = {}

    def save(self, model: Model) -> Model:
        self._models[model.model_id] = model
        return model

    def get_by_id(self, model_id: UUID) -> Optional[Model]:
        return self._models.get(model_id)

    def list_models(self) -> List[Model]:
        return list(self._models.values())


class InMemoryTrainingRunRepository(ITrainingRunRepository):
    """In-memory store for training runs and run-dataset links."""

    def __init__(self):
        self._runs: Dict[UUID, TrainingRun] = {}
        self._links: List[RunDataset] = []

    def save(self, run: TrainingRun) -> TrainingRun:
        self._runs[run.run_id] = run
        return run

    def get_by_id(self, run_id: UUID) -> Optional[TrainingRun]:
        return self._runs.get(run_id)

    def link_dataset(
        self,
        run_id: UUID,
        dataset_artifact_id: UUID,
        dataset_role: Union[DatasetRole, str] = DatasetRole.TRAIN,
        sample_count: Optional[int] = None,
        usage_percentage: Optional[float] = None,
    ) -> RunDataset:
        link = RunDataset(
            run_id=run_id,
            dataset_artifact_id=dataset_artifact_id,
            dataset_role=dataset_role,
            sample_count=sample_count,
            usage_percentage=usage_percentage,
        )
        self._links.append(link)
        return link

    def get_linked_datasets(self, run_id: UUID) -> List[RunDataset]:
        return [l for l in self._links if l.run_id == run_id]

    def list_by_model(self, model_id: UUID) -> List[TrainingRun]:
        return [r for r in self._runs.values() if r.model_id == model_id]


class InMemoryModelVersionRepository(IModelVersionRepository):
    """In-memory store for model versions."""

    def __init__(self):
        self._versions: Dict[UUID, ModelVersion] = {}

    def save(self, version: ModelVersion) -> ModelVersion:
        self._versions[version.version_id] = version
        return version

    def get_by_id(self, version_id: UUID) -> Optional[ModelVersion]:
        return self._versions.get(version_id)

    def get_latest_version(self, model_id: UUID) -> Optional[ModelVersion]:
        model_versions = [v for v in self._versions.values() if v.model_id == model_id]
        if not model_versions:
            return None
        return max(model_versions, key=lambda v: v.registered_at)

    def list_by_model(self, model_id: UUID) -> List[ModelVersion]:
        return [v for v in self._versions.values() if v.model_id == model_id]


class InMemoryDatasetArtifactRepository(IDatasetArtifactRepository):
    """In-memory store for dataset artifacts."""

    def __init__(self):
        self._artifacts: Dict[UUID, DatasetArtifact] = {}

    def save(self, artifact: DatasetArtifact) -> DatasetArtifact:
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def get_by_id(self, artifact_id: UUID) -> Optional[DatasetArtifact]:
        return self._artifacts.get(artifact_id)
