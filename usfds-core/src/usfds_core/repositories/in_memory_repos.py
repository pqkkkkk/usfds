from usfds_core.domain.entities.detection import Deployment, DetectionJob, Pipeline
from usfds_core.repositories.base_detection_job_repo import IDetectionJobRepository
from usfds_core.repositories.pipeline_repo import IPipelineRepository
from typing import Dict, List, Optional, Union
from uuid import UUID

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import DatasetRole
from usfds_core.domain.entities.model import Model, ModelVersion, RunDataset, TrainingRun
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_model_repo import IModelRepository
from usfds_core.repositories.base_model_version_repo import IModelVersionRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository
from usfds_core.domain.entities.enums import (
    DeploymentEnvironment,
    DeploymentStatus,
    PipelineStage,
)


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

class InMemoryPipelineRepository(IPipelineRepository):
    """In-memory store for Pipeline domain entities."""

    def __init__(
        self,
        pipelines: Optional[Dict[UUID, Pipeline]] = None,
        default_pipeline: Optional[Pipeline] = None,
        use_storage_fallback: bool = True,
    ):
        self._pipelines: Dict[UUID, Pipeline] = pipelines or {}
        self._default_pipeline = default_pipeline
        self._use_storage_fallback = use_storage_fallback

    def register_pipeline(self, deployment_id: UUID, pipeline: Pipeline) -> None:
        """Register a pipeline for a specific deployment ID (useful for testing)."""
        self._pipelines[deployment_id] = pipeline

    def get_by_deployment_id(
        self,
        deployment_id: UUID,
    ) -> Optional[Pipeline]:
        """Retrieve pipeline by deployment ID. Falls back to default pipeline if configured."""
        if deployment_id in self._pipelines:
            return self._pipelines[deployment_id]
        if self._default_pipeline is not None:
            return self._default_pipeline
        if self._use_storage_fallback:
            return self._build_default_storage_pipeline(deployment_id)
        return None

    @staticmethod
    def _build_default_storage_pipeline(deployment_id: UUID) -> Pipeline:
        """Constructs a default Pipeline pointing to the existing test artifacts in storage_output."""

        raw_artifact = DatasetArtifact(
            artifact_id=UUID("2a1f0a2e-4b4e-4e44-8fa2-0d19f182c111"),
            dataset_id=UUID("4b917316-bdb2-4dbc-b64c-fa49264326d4"),
            storage_path="datasets/e-commerce-fraud-detection-dataset",
            output_paths={"raw": "datasets/e-commerce-fraud-detection-dataset/raw.csv"},
            pipeline_stage=PipelineStage.RAW,
        )

        mapped_artifact = DatasetArtifact(
            artifact_id=UUID("8c5e3f1a-6d2b-4c5e-9f3a-1e2d3c4b5a6f"),
            dataset_id=UUID("4b917316-bdb2-4dbc-b64c-fa49264326d4"),
            parent_artifact_id=raw_artifact.artifact_id,
            storage_path="datasets/e-commerce-fraud-detection-dataset",
            output_paths={"mapped": "datasets/e-commerce-fraud-detection-dataset/mapped.csv"},
            pipeline_stage=PipelineStage.MAPPED,
            validation_report={
                "column_mapping": {
                    "transaction_id": "event_id",
                    "transaction_time": "timestamp",
                    "amount": "amount",
                    "user_id": "user_id",
                    "account_age_days": "account_age_days",
                    "total_transactions_user": "total_transactions_user",
                    "avg_amount_user": "avg_amount_user",
                    "country": "country",
                    "bin_country": "bin_country",
                    "channel": "channel",
                    "merchant_category": "merchant_category",
                    "promo_used": "promo_used",
                    "avs_match": "avs_match",
                    "cvv_result": "cvv_result",
                    "three_ds_flag": "three_ds_flag",
                    "shipping_distance_km": "shipping_distance_km",
                    "is_fraud": "label",
                }
            },
            schema_snapshot={
                "event_id": "int64",
                "user_id": "int64",
                "account_age_days": "int64",
                "total_transactions_user": "int64",
                "avg_amount_user": "float64",
                "amount": "float64",
                "country": "object",
                "bin_country": "object",
                "channel": "object",
                "merchant_category": "object",
                "promo_used": "int64",
                "avs_match": "int64",
                "cvv_result": "int64",
                "three_ds_flag": "int64",
                "timestamp": "object",
                "shipping_distance_km": "float64",
                "label": "int64",
            },
        )

        fe_artifact = DatasetArtifact(
            artifact_id=UUID("688f3d5a-b5c7-404f-ace5-ab1f224cfe67"),
            dataset_id=UUID("4b917316-bdb2-4dbc-b64c-fa49264326d4"),
            parent_artifact_id=mapped_artifact.artifact_id,
            storage_path="datasets/4b917316-bdb2-4dbc-b64c-fa49264326d4/artifacts/688f3d5a-b5c7-404f-ace5-ab1f224cfe67",
            output_paths={
                "train": "datasets/4b917316-bdb2-4dbc-b64c-fa49264326d4/artifacts/688f3d5a-b5c7-404f-ace5-ab1f224cfe67/train_enriched.parquet",
                "test": "datasets/4b917316-bdb2-4dbc-b64c-fa49264326d4/artifacts/688f3d5a-b5c7-404f-ace5-ab1f224cfe67/test_enriched.parquet",
                "fitted_engineers": "datasets/4b917316-bdb2-4dbc-b64c-fa49264326d4/artifacts/688f3d5a-b5c7-404f-ace5-ab1f224cfe67/fitted_feature_engineers.joblib",
            },
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
        )

        preprocessed_artifact = DatasetArtifact(
            artifact_id=UUID("170d15cd-4c67-44cc-988e-6f78c44bf1cc"),
            dataset_id=UUID("4b917316-bdb2-4dbc-b64c-fa49264326d4"),
            parent_artifact_id=fe_artifact.artifact_id,
            storage_path="datasets/4b917316-bdb2-4dbc-b64c-fa49264326d4/artifacts/170d15cd-4c67-44cc-988e-6f78c44bf1cc",
            output_paths={
                "train": "datasets/4b917316-bdb2-4dbc-b64c-fa49264326d4/artifacts/170d15cd-4c67-44cc-988e-6f78c44bf1cc/train_processed.parquet",
                "test": "datasets/4b917316-bdb2-4dbc-b64c-fa49264326d4/artifacts/170d15cd-4c67-44cc-988e-6f78c44bf1cc/test_processed.parquet",
                "pipeline": "datasets/4b917316-bdb2-4dbc-b64c-fa49264326d4/artifacts/170d15cd-4c67-44cc-988e-6f78c44bf1cc/fitted_pipeline.joblib",
            },
            pipeline_stage=PipelineStage.PRE_PROCESSED,
        )

        model_version = ModelVersion(
            version_id=UUID("e4a3b2c1-0d9e-4f8a-7b6c-5d4e3f2a1b0c"),
            model_id=UUID("10a10637-3ae8-4341-9ef0-064859398c89"),
            run_id=UUID("cc3352ac-a621-482d-81b4-2f8d03bc716d"),
            semver="1.0.0",
            artifact_uri="models/10a10637-3ae8-4341-9ef0-064859398c89/runs/cc3352ac-a621-482d-81b4-2f8d03bc716d/model.joblib",
        )

        deployment = Deployment(
            deployment_id=deployment_id,
            version_id=model_version.version_id,
            deployment_name="ecommerce-fraud-detection",
            environment=DeploymentEnvironment.PRODUCTION,
            status=DeploymentStatus.RUNNING,
        )

        return Pipeline(
            raw_dataset_artifact=raw_artifact,
            mapped_dataset_artifact=mapped_artifact,
            feature_engineered_dataset_artifact=fe_artifact,
            preprocessed_dataset_artifact=preprocessed_artifact,
            model_version=model_version,
            deployment=deployment,
        )


class InMemoryDetectionJobRepository(IDetectionJobRepository):
    """In-memory store for detection jobs."""

    def __init__(self):
        self._jobs: Dict[UUID, DetectionJob] = {}

    def save(self, job: DetectionJob) -> DetectionJob:
        self._jobs[job.job_id] = job
        return job

    def get_by_id(self, job_id: UUID) -> Optional[DetectionJob]:
        return self._jobs.get(job_id)

    def list_by_deployment(self, deployment_id: UUID) -> List[DetectionJob]:
        return [j for j in self._jobs.values() if j.deployment_id == deployment_id]

    def list_by_project(self, project_id: UUID) -> List[DetectionJob]:
        return [j for j in self._jobs.values() if j.project_id == project_id]