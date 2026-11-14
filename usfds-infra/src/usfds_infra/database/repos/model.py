"""SQLAlchemy repositories for the `model` domain (moved from database/repositories.py, 26-11-14)."""
from datetime import datetime, timezone
from typing import Any, List, Optional, Union
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from usfds_core.domain.entities.enums import DatasetRole, ExecutionType, ModelVersionStatus, TrainingRunStatus
from usfds_core.domain.entities.model import Model, ModelVersion, RunDataset, TrainingRun
from usfds_core.repositories.base_model_repo import IModelRepository
from usfds_core.repositories.base_model_version_repo import IModelVersionRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository
from usfds_infra.database.models import MLModel, ModelVersionModel, RunDatasetModel, TrainingRunModel


class SqliteModelRepository(IModelRepository):
    """SQLite implementation of IModelRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _sanitize_json(obj: Any) -> Any:
        import math
        if isinstance(obj, float):
            if math.isnan(obj):
                return None
            if math.isinf(obj):
                return 1.0 if obj > 0 else 0.0
            return obj
        if isinstance(obj, dict):
            return {k: SqliteTrainingRunRepository._sanitize_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SqliteTrainingRunRepository._sanitize_json(v) for v in obj]
        return obj

    def _to_entity(self, record: MLModel) -> Model:
        exec_type: Union[ExecutionType, str] = ExecutionType.BUILTIN
        if record.execution_type:
            try:
                exec_type = ExecutionType(record.execution_type)
            except ValueError:
                exec_type = record.execution_type

        # TODO: ISS-035 — RiskLevel is never imported; a record with risk_level raises NameError here.
        risk_val: Optional[Union[RiskLevel, str]] = None
        if record.risk_level:
            try:
                risk_val = RiskLevel(record.risk_level)
            except ValueError:
                risk_val = record.risk_level

        return Model(
            model_id=UUID(record.model_id),
            project_id=UUID(record.project_id) if record.project_id else None,
            user_id=UUID(record.user_id),
            model_name=record.model_name,
            display_name=record.display_name,
            description=record.description,
            execution_type=exec_type,
            entrypoint_uri=record.entrypoint_uri,
            hyperparameter_schema=record.hyperparameter_schema,
            default_hyperparameters=record.default_hyperparameters,
            risk_level=risk_val,
            github_repo=record.github_repo,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def save(self, model: Model) -> Model:
        record = self.session.get(MLModel, str(model.model_id))
        exec_type_str = (
            model.execution_type.value
            if hasattr(model.execution_type, "value")
            else str(model.execution_type)
        )
        risk_str = (
            model.risk_level.value
            if hasattr(model.risk_level, "value")
            else str(model.risk_level) if model.risk_level else None
        )

        if record is None:
            record = MLModel(
                model_id=str(model.model_id),
                project_id=str(model.project_id) if model.project_id else None,
                user_id=str(model.user_id),
                model_name=model.model_name,
                display_name=model.display_name,
                description=model.description,
                execution_type=exec_type_str,
                entrypoint_uri=model.entrypoint_uri,
                hyperparameter_schema=model.hyperparameter_schema,
                default_hyperparameters=model.default_hyperparameters,
                risk_level=risk_str,
                github_repo=model.github_repo,
                created_at=model.created_at or datetime.now(timezone.utc),
                updated_at=model.updated_at or datetime.now(timezone.utc),
            )
            self.session.add(record)
        else:
            record.project_id = str(model.project_id) if model.project_id else None
            record.model_name = model.model_name
            record.display_name = model.display_name
            record.description = model.description
            record.execution_type = exec_type_str
            record.entrypoint_uri = model.entrypoint_uri
            record.hyperparameter_schema = model.hyperparameter_schema
            record.default_hyperparameters = model.default_hyperparameters
            record.risk_level = risk_str
            record.github_repo = model.github_repo
            record.updated_at = datetime.now(timezone.utc)

        self.session.flush()
        return self._to_entity(record)

    def get_by_id(self, model_id: UUID) -> Optional[Model]:
        record = self.session.get(MLModel, str(model_id))
        return self._to_entity(record) if record else None

    def list_models(self) -> List[Model]:
        stmt = select(MLModel).order_by(MLModel.created_at.desc())
        records = self.session.execute(stmt).scalars().all()
        return [self._to_entity(r) for r in records]


class SqliteModelVersionRepository(IModelVersionRepository):
    """SQLite implementation of IModelVersionRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _sanitize_json(obj: Any) -> Any:
        import math
        if isinstance(obj, float):
            if math.isnan(obj):
                return None
            if math.isinf(obj):
                return 1.0 if obj > 0 else 0.0
            return obj
        if isinstance(obj, dict):
            return {k: SqliteTrainingRunRepository._sanitize_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SqliteTrainingRunRepository._sanitize_json(v) for v in obj]
        return obj

    def _to_entity(self, record: ModelVersionModel) -> ModelVersion:
        status_val: Union[ModelVersionStatus, str] = ModelVersionStatus.DRAFT
        if record.status:
            try:
                status_val = ModelVersionStatus(record.status)
            except ValueError:
                status_val = record.status

        return ModelVersion(
            version_id=UUID(record.version_id),
            model_id=UUID(record.model_id),
            project_id=UUID(record.project_id) if record.project_id else None,
            run_id=UUID(record.run_id) if record.run_id else None,
            semver=record.semver,
            artifact_uri=record.artifact_uri,
            description=record.description,
            artifact_size_mb=record.artifact_size_mb,
            checksum_sha256=record.checksum_sha256,
            framework=record.framework,
            decision_threshold=record.decision_threshold,
            status=status_val,
            registered_by=record.registered_by,
            registered_at=record.registered_at,
        )

    def save(self, version: ModelVersion) -> ModelVersion:
        record = self.session.get(ModelVersionModel, str(version.version_id))
        status_str = (
            version.status.value
            if hasattr(version.status, "value")
            else str(version.status)
        )

        if record is None:
            record = ModelVersionModel(
                version_id=str(version.version_id),
                model_id=str(version.model_id),
                project_id=str(version.project_id) if version.project_id else None,
                run_id=str(version.run_id) if version.run_id else None,
                semver=version.semver,
                artifact_uri=version.artifact_uri,
                description=version.description,
                artifact_size_mb=version.artifact_size_mb,
                checksum_sha256=version.checksum_sha256,
                framework=version.framework,
                decision_threshold=version.decision_threshold,
                status=status_str,
                registered_by=version.registered_by,
                registered_at=version.registered_at or datetime.now(timezone.utc),
            )
            self.session.add(record)
        else:
            record.semver = version.semver
            record.artifact_uri = version.artifact_uri
            record.description = version.description
            record.artifact_size_mb = version.artifact_size_mb
            record.checksum_sha256 = version.checksum_sha256
            record.framework = version.framework
            record.decision_threshold = version.decision_threshold
            record.status = status_str

        self.session.flush()
        return self._to_entity(record)

    def get_by_id(self, version_id: UUID) -> Optional[ModelVersion]:
        record = self.session.get(ModelVersionModel, str(version_id))
        return self._to_entity(record) if record else None

    def get_latest_version(self, model_id: UUID) -> Optional[ModelVersion]:
        stmt = (
            select(ModelVersionModel)
            .where(ModelVersionModel.model_id == str(model_id))
            .order_by(ModelVersionModel.registered_at.desc())
            .limit(1)
        )
        record = self.session.execute(stmt).scalar_one_or_none()
        return self._to_entity(record) if record else None

    def list_by_model(self, model_id: UUID) -> List[ModelVersion]:
        stmt = (
            select(ModelVersionModel)
            .where(ModelVersionModel.model_id == str(model_id))
            .order_by(ModelVersionModel.registered_at.desc())
        )
        records = self.session.execute(stmt).scalars().all()
        return [self._to_entity(r) for r in records]


class SqliteTrainingRunRepository(ITrainingRunRepository):
    """SQLite implementation of ITrainingRunRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _sanitize_json(obj: Any) -> Any:
        import math
        if isinstance(obj, float):
            if math.isnan(obj):
                return None
            if math.isinf(obj):
                return 1.0 if obj > 0 else 0.0
            return obj
        if isinstance(obj, dict):
            return {k: SqliteTrainingRunRepository._sanitize_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SqliteTrainingRunRepository._sanitize_json(v) for v in obj]
        return obj

    def _to_entity(self, record: TrainingRunModel) -> TrainingRun:
        status_val: Union[TrainingRunStatus, str] = TrainingRunStatus.PENDING
        if record.status:
            try:
                status_val = TrainingRunStatus(record.status)
            except ValueError:
                status_val = record.status

        return TrainingRun(
            run_id=UUID(record.run_id),
            project_id=UUID(record.project_id) if record.project_id else None,
            model_id=UUID(record.model_id) if record.model_id else None,
            version_id=UUID(record.version_id) if record.version_id else None,
            run_name=record.run_name,
            status=status_val,
            accuracy=record.accuracy,
            precision_score=record.precision_score,
            recall_score=record.recall_score,
            f1_score=record.f1_score,
            loss=record.loss,
            default_threshold=record.default_threshold,
            recommended_threshold=record.recommended_threshold,
            hyperparameters=record.hyperparameters,
            custom_metrics=record.custom_metrics,
            compute_target=record.compute_target,
            error_message=record.error_message,
            created_by=record.created_by,
            started_at=record.started_at,
            completed_at=record.completed_at,
            duration_seconds=record.duration_seconds,
            logs_path=record.logs_path,
            metrics_path=record.metrics_path,
            eval_predictions_path=record.eval_predictions_path,
            created_at=record.created_at,
        )

    def save(self, run: TrainingRun) -> TrainingRun:
        record = self.session.get(TrainingRunModel, str(run.run_id))
        status_str = (
            run.status.value
            if hasattr(run.status, "value")
            else str(run.status)
        )

        clean_hyperparameters = self._sanitize_json(run.hyperparameters)
        clean_custom_metrics = self._sanitize_json(run.custom_metrics)

        if record is None:
            record = TrainingRunModel(
                run_id=str(run.run_id),
                project_id=str(run.project_id) if run.project_id else None,
                model_id=str(run.model_id) if run.model_id else None,
                version_id=str(run.version_id) if run.version_id else None,
                run_name=run.run_name,
                status=status_str,
                accuracy=run.accuracy,
                precision_score=run.precision_score,
                recall_score=run.recall_score,
                f1_score=run.f1_score,
                loss=run.loss,
                default_threshold=run.default_threshold,
                recommended_threshold=run.recommended_threshold,
                hyperparameters=clean_hyperparameters,
                custom_metrics=clean_custom_metrics,
                compute_target=run.compute_target,
                error_message=run.error_message,
                created_by=run.created_by,
                started_at=run.started_at,
                completed_at=run.completed_at,
                duration_seconds=run.duration_seconds,
                logs_path=run.logs_path,
                metrics_path=run.metrics_path,
                eval_predictions_path=run.eval_predictions_path,
                created_at=run.created_at or datetime.now(timezone.utc),
            )
            self.session.add(record)
        else:
            record.version_id = str(run.version_id) if run.version_id else None
            record.status = status_str
            record.accuracy = run.accuracy
            record.precision_score = run.precision_score
            record.recall_score = run.recall_score
            record.f1_score = run.f1_score
            record.loss = run.loss
            record.default_threshold = run.default_threshold
            record.recommended_threshold = run.recommended_threshold
            record.hyperparameters = clean_hyperparameters
            record.custom_metrics = clean_custom_metrics
            record.compute_target = run.compute_target
            record.error_message = run.error_message
            record.started_at = run.started_at
            record.completed_at = run.completed_at
            record.duration_seconds = run.duration_seconds
            record.logs_path = run.logs_path
            record.metrics_path = run.metrics_path
            record.eval_predictions_path = run.eval_predictions_path

        try:
            self.session.flush()
        except Exception:
            self.session.rollback()
            raise
        return self._to_entity(record)

    def get_by_id(self, run_id: UUID) -> Optional[TrainingRun]:
        record = self.session.get(TrainingRunModel, str(run_id))
        return self._to_entity(record) if record else None

    def link_dataset(
        self,
        run_id: UUID,
        dataset_artifact_id: UUID,
        dataset_role: Union[DatasetRole, str] = DatasetRole.TRAIN,
        sample_count: Optional[int] = None,
        usage_percentage: Optional[float] = None,
    ) -> RunDataset:
        role_str = (
            dataset_role.value
            if hasattr(dataset_role, "value")
            else str(dataset_role)
        )
        record = RunDatasetModel(
            run_id=str(run_id),
            dataset_artifact_id=str(dataset_artifact_id),
            dataset_role=role_str,
            sample_count=sample_count,
            usage_percentage=usage_percentage,
        )
        self.session.add(record)
        self.session.flush()
        return RunDataset(
            run_id=run_id,
            dataset_artifact_id=dataset_artifact_id,
            dataset_role=dataset_role,
            sample_count=sample_count,
            usage_percentage=usage_percentage,
        )

    def get_linked_datasets(self, run_id: UUID) -> List[RunDataset]:
        stmt = select(RunDatasetModel).where(RunDatasetModel.run_id == str(run_id))
        records = self.session.execute(stmt).scalars().all()
        result: List[RunDataset] = []
        for r in records:
            role_val: Union[DatasetRole, str] = DatasetRole.TRAIN
            try:
                role_val = DatasetRole(r.dataset_role)
            except ValueError:
                role_val = r.dataset_role
            result.append(
                RunDataset(
                    run_id=UUID(r.run_id),
                    dataset_artifact_id=UUID(r.dataset_artifact_id),
                    dataset_role=role_val,
                    sample_count=r.sample_count,
                    usage_percentage=r.usage_percentage,
                )
            )
        return result

    def list_by_model(self, model_id: UUID) -> List[TrainingRun]:
        stmt = (
            select(TrainingRunModel)
            .where(TrainingRunModel.model_id == str(model_id))
            .order_by(TrainingRunModel.created_at.desc())
        )
        records = self.session.execute(stmt).scalars().all()
        return [self._to_entity(r) for r in records]
