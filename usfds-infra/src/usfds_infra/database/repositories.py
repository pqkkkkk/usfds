from datetime import datetime, timezone
from typing import List, Optional, Union
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import (
    DataClassification,
    DatasetRole,
    ExecutionType,
    ModelVersionStatus,
    PipelineStage,
    ProjectStatus,
    RiskLevel,
    RuleAction,
    RuleStatus,
    TrainingRunStatus,
    ValidationStatus,
)
from usfds_core.domain.entities.model import Model, ModelVersion, RunDataset, TrainingRun
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.domain.entities.system import Project
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_dataset_repo import IDatasetRepository
from usfds_core.repositories.base_model_repo import IModelRepository
from usfds_core.repositories.base_model_version_repo import IModelVersionRepository
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_core.repositories.base_rule_repo import IRuleRepository, IRuleVersionRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository
from usfds_infra.database.models import (
    DatasetArtifactModel,
    DatasetModel,
    MLModel,
    ModelVersionModel,
    ProjectModel,
    RuleModel,
    RuleVersionModel,
    RunDatasetModel,
    TrainingRunModel,
)


class SqliteProjectRepository(IProjectRepository):
    """SQLite implementation of IProjectRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _to_entity(self, model: ProjectModel) -> Project:
        status_val: Union[ProjectStatus, str] = ProjectStatus.ACTIVE
        if model.status:
            try:
                status_val = ProjectStatus(model.status)
            except ValueError:
                status_val = model.status

        return Project(
            project_id=UUID(model.project_id),
            project_name=model.project_name,
            user_id=UUID(model.user_id),
            description=model.description,
            status=status_val,
            base_dataset_id=UUID(model.base_dataset_id) if model.base_dataset_id else None,
            raw_schema=model.raw_schema,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(self, project: Project) -> Project:
        model = self.session.get(ProjectModel, str(project.project_id))
        status_str = (
            project.status.value
            if hasattr(project.status, "value")
            else str(project.status) if project.status else ProjectStatus.ACTIVE.value
        )

        if model is None:
            model = ProjectModel(
                project_id=str(project.project_id),
                project_name=project.project_name,
                user_id=str(project.user_id),
                description=project.description,
                status=status_str,
                base_dataset_id=str(project.base_dataset_id) if project.base_dataset_id else None,
                raw_schema=project.raw_schema,
                created_at=project.created_at or datetime.now(timezone.utc),
                updated_at=project.updated_at or datetime.now(timezone.utc),
            )
            self.session.add(model)
        else:
            model.project_name = project.project_name
            model.description = project.description
            model.status = status_str
            model.base_dataset_id = str(project.base_dataset_id) if project.base_dataset_id else None
            model.raw_schema = project.raw_schema
            model.updated_at = project.updated_at or datetime.now(timezone.utc)

        self.session.flush()
        return self._to_entity(model)

    def get_by_id(self, project_id: UUID) -> Optional[Project]:
        model = self.session.get(ProjectModel, str(project_id))
        return self._to_entity(model) if model else None

    def get_by_name(self, user_id: UUID, project_name: str) -> Optional[Project]:
        stmt = select(ProjectModel).where(
            ProjectModel.user_id == str(user_id),
            func.lower(ProjectModel.project_name) == project_name.lower(),
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return self._to_entity(model) if model else None

    def list_all(
        self,
        user_id: Optional[UUID] = None,
        status: Optional[Union[ProjectStatus, str]] = None,
        search: Optional[str] = None,
    ) -> List[Project]:
        stmt = select(ProjectModel)
        if user_id:
            stmt = stmt.where(ProjectModel.user_id == str(user_id))
        if status:
            status_str = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(ProjectModel.status == status_str)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    ProjectModel.project_name.ilike(search_pattern),
                    ProjectModel.description.ilike(search_pattern),
                )
            )
        stmt = stmt.order_by(ProjectModel.created_at.desc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_entity(m) for m in models]

    def delete(self, project_id: UUID) -> bool:
        model = self.session.get(ProjectModel, str(project_id))
        if model:
            self.session.delete(model)
            self.session.flush()
            return True
        return False


class SqliteDatasetRepository(IDatasetRepository):
    """SQLite implementation of IDatasetRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _to_entity(self, model: DatasetModel) -> Dataset:
        classification = None
        if model.data_classification:
            try:
                classification = DataClassification(model.data_classification)
            except ValueError:
                classification = model.data_classification

        return Dataset(
            dataset_id=UUID(model.dataset_id),
            project_id=UUID(model.project_id),
            user_id=UUID(model.user_id),
            dataset_name=model.dataset_name,
            display_name=model.display_name,
            description=model.description,
            contains_pii=model.contains_pii,
            data_classification=classification,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(self, dataset: Dataset) -> Dataset:
        model = self.session.get(DatasetModel, str(dataset.dataset_id))
        cls_str = (
            dataset.data_classification.value
            if hasattr(dataset.data_classification, "value")
            else str(dataset.data_classification) if dataset.data_classification else None
        )

        if model is None:
            model = DatasetModel(
                dataset_id=str(dataset.dataset_id),
                project_id=str(dataset.project_id),
                user_id=str(dataset.user_id),
                dataset_name=dataset.dataset_name,
                display_name=dataset.display_name,
                description=dataset.description,
                contains_pii=dataset.contains_pii,
                data_classification=cls_str,
                created_at=dataset.created_at or datetime.now(timezone.utc),
                updated_at=dataset.updated_at or datetime.now(timezone.utc),
            )
            self.session.add(model)
        else:
            model.dataset_name = dataset.dataset_name
            model.display_name = dataset.display_name
            model.description = dataset.description
            model.contains_pii = dataset.contains_pii
            model.data_classification = cls_str
            model.updated_at = datetime.now(timezone.utc)

        self.session.flush()
        return self._to_entity(model)

    def get_by_id(self, dataset_id: UUID) -> Optional[Dataset]:
        model = self.session.get(DatasetModel, str(dataset_id))
        return self._to_entity(model) if model else None

    def get_by_name(self, project_id: UUID, dataset_name: str) -> Optional[Dataset]:
        stmt = select(DatasetModel).where(
            DatasetModel.project_id == str(project_id),
            DatasetModel.dataset_name == dataset_name,
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return self._to_entity(model) if model else None

    def list_by_project(self, project_id: UUID) -> List[Dataset]:
        stmt = select(DatasetModel).where(
            DatasetModel.project_id == str(project_id)
        ).order_by(DatasetModel.created_at.desc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_entity(m) for m in models]

    def list_all(
        self,
        project_id: Optional[UUID] = None,
        search: Optional[str] = None,
    ) -> List[Dataset]:
        stmt = select(DatasetModel)
        if project_id:
            stmt = stmt.where(DatasetModel.project_id == str(project_id))
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    DatasetModel.dataset_name.ilike(search_pattern),
                    DatasetModel.display_name.ilike(search_pattern),
                    DatasetModel.description.ilike(search_pattern),
                )
            )
        stmt = stmt.order_by(DatasetModel.created_at.desc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_entity(m) for m in models]

    def delete(self, dataset_id: UUID) -> bool:
        model = self.session.get(DatasetModel, str(dataset_id))
        if model:
            self.session.delete(model)
            self.session.flush()
            return True
        return False


class SqliteDatasetArtifactRepository(IDatasetArtifactRepository):
    """SQLite implementation of IDatasetArtifactRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _to_entity(self, model: DatasetArtifactModel) -> DatasetArtifact:
        stage = (
            PipelineStage(model.pipeline_stage)
            if model.pipeline_stage in PipelineStage._value2member_map_
            else model.pipeline_stage
        )
        status = (
            ValidationStatus(model.validation_status)
            if model.validation_status in ValidationStatus._value2member_map_
            else model.validation_status
        )

        return DatasetArtifact(
            artifact_id=UUID(model.artifact_id),
            dataset_id=UUID(model.dataset_id),
            parent_artifact_id=UUID(model.parent_artifact_id) if model.parent_artifact_id else None,
            pipeline_stage=stage,
            change_type=model.change_type,
            storage_path=model.storage_path,
            output_paths=model.output_paths or {},
            checksum_sha256=model.checksum_sha256,
            schema_snapshot=model.schema_snapshot,
            row_count=model.row_count,
            column_count=model.column_count,
            validation_status=status,
            validation_report=model.validation_report,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    def save(self, artifact: DatasetArtifact) -> DatasetArtifact:
        model = self.session.get(DatasetArtifactModel, str(artifact.artifact_id))
        stage_str = (
            artifact.pipeline_stage.value
            if hasattr(artifact.pipeline_stage, "value")
            else str(artifact.pipeline_stage)
        )
        status_str = (
            artifact.validation_status.value
            if hasattr(artifact.validation_status, "value")
            else str(artifact.validation_status) if artifact.validation_status else "PENDING"
        )

        if model is None:
            model = DatasetArtifactModel(
                artifact_id=str(artifact.artifact_id),
                dataset_id=str(artifact.dataset_id),
                parent_artifact_id=str(artifact.parent_artifact_id) if artifact.parent_artifact_id else None,
                pipeline_stage=stage_str,
                change_type=artifact.change_type,
                storage_path=artifact.storage_path,
                output_paths=artifact.output_paths or {},
                checksum_sha256=artifact.checksum_sha256,
                schema_snapshot=artifact.schema_snapshot,
                row_count=artifact.row_count,
                column_count=artifact.column_count,
                validation_status=status_str,
                validation_report=artifact.validation_report,
                created_by=artifact.created_by or "system",
                created_at=artifact.created_at or datetime.now(timezone.utc),
            )
            self.session.add(model)
        else:
            model.pipeline_stage = stage_str
            model.change_type = artifact.change_type
            model.storage_path = artifact.storage_path
            model.output_paths = artifact.output_paths or {}
            model.checksum_sha256 = artifact.checksum_sha256
            model.schema_snapshot = artifact.schema_snapshot
            model.row_count = artifact.row_count
            model.column_count = artifact.column_count
            model.validation_status = status_str
            model.validation_report = artifact.validation_report

        self.session.flush()
        return self._to_entity(model)

    def get_by_id(self, artifact_id: UUID) -> Optional[DatasetArtifact]:
        model = self.session.get(DatasetArtifactModel, str(artifact_id))
        return self._to_entity(model) if model else None

    def list_by_dataset(self, dataset_id: UUID) -> List[DatasetArtifact]:
        stmt = select(DatasetArtifactModel).where(
            DatasetArtifactModel.dataset_id == str(dataset_id)
        ).order_by(DatasetArtifactModel.created_at.asc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_entity(m) for m in models]

    def get_latest_artifact(self, dataset_id: UUID) -> Optional[DatasetArtifact]:
        stmt = select(DatasetArtifactModel).where(
            DatasetArtifactModel.dataset_id == str(dataset_id)
        ).order_by(DatasetArtifactModel.created_at.desc()).limit(1)
        model = self.session.execute(stmt).scalar_one_or_none()
        return self._to_entity(model) if model else None


class SqliteRuleRepository(IRuleRepository):
    """SQLite implementation of IRuleRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _to_entity(self, model: RuleModel) -> Rule:
        status_val = RuleStatus.ACTIVE
        if model.status:
            try:
                status_val = RuleStatus(model.status)
            except ValueError:
                status_val = model.status

        return Rule(
            rule_id=UUID(model.rule_id),
            project_id=UUID(model.project_id),
            rule_code=model.rule_code,
            name=model.name,
            description=model.description or "",
            status=status_val,
            current_version_id=UUID(model.current_version_id) if model.current_version_id else None,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(self, rule: Rule) -> Rule:
        model = self.session.get(RuleModel, str(rule.rule_id))
        status_str = rule.status.value if hasattr(rule.status, "value") else str(rule.status)

        if model is None:
            model = RuleModel(
                rule_id=str(rule.rule_id),
                project_id=str(rule.project_id),
                rule_code=rule.rule_code,
                name=rule.name,
                description=rule.description,
                status=status_str,
                current_version_id=str(rule.current_version_id) if rule.current_version_id else None,
                created_by=rule.created_by,
                created_at=rule.created_at or datetime.now(timezone.utc),
                updated_at=rule.updated_at or datetime.now(timezone.utc),
            )
            self.session.add(model)
        else:
            model.rule_code = rule.rule_code
            model.name = rule.name
            model.description = rule.description
            model.status = status_str
            model.current_version_id = str(rule.current_version_id) if rule.current_version_id else None
            model.updated_at = datetime.now(timezone.utc)

        self.session.flush()
        return self._to_entity(model)

    def get_by_id(self, rule_id: UUID) -> Optional[Rule]:
        model = self.session.get(RuleModel, str(rule_id))
        return self._to_entity(model) if model else None

    def get_by_code(self, project_id: UUID, rule_code: str) -> Optional[Rule]:
        stmt = select(RuleModel).where(
            RuleModel.project_id == str(project_id),
            RuleModel.rule_code == rule_code,
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return self._to_entity(model) if model else None

    def list_by_project(self, project_id: UUID) -> List[Rule]:
        stmt = select(RuleModel).where(
            RuleModel.project_id == str(project_id)
        ).order_by(RuleModel.created_at.asc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_entity(m) for m in models]

    def delete(self, rule_id: UUID) -> bool:
        model = self.session.get(RuleModel, str(rule_id))
        if model:
            self.session.delete(model)
            self.session.flush()
            return True
        return False


class SqliteRuleVersionRepository(IRuleVersionRepository):
    """SQLite implementation of IRuleVersionRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _to_entity(self, model: RuleVersionModel) -> RuleVersion:
        action_val = RuleAction.REVIEW
        if model.action:
            try:
                action_val = RuleAction(model.action)
            except ValueError:
                action_val = model.action

        return RuleVersion(
            rule_version_id=UUID(model.rule_version_id),
            rule_id=UUID(model.rule_id),
            version_number=model.version_number,
            condition=model.condition or {},
            action=action_val,
            change_summary=model.change_summary,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    def save(self, version: RuleVersion) -> RuleVersion:
        model = self.session.get(RuleVersionModel, str(version.rule_version_id))
        action_str = version.action.value if hasattr(version.action, "value") else str(version.action)

        if model is None:
            model = RuleVersionModel(
                rule_version_id=str(version.rule_version_id),
                rule_id=str(version.rule_id),
                version_number=version.version_number,
                condition=version.condition or {},
                action=action_str,
                change_summary=version.change_summary,
                created_by=version.created_by,
                created_at=version.created_at or datetime.now(timezone.utc),
            )
            self.session.add(model)
        else:
            model.condition = version.condition or {}
            model.action = action_str
            model.change_summary = version.change_summary

        self.session.flush()
        return self._to_entity(model)

    def get_by_id(self, rule_version_id: UUID) -> Optional[RuleVersion]:
        model = self.session.get(RuleVersionModel, str(rule_version_id))
        return self._to_entity(model) if model else None

    def get_latest_version(self, rule_id: UUID) -> Optional[RuleVersion]:
        stmt = select(RuleVersionModel).where(
            RuleVersionModel.rule_id == str(rule_id)
        ).order_by(RuleVersionModel.version_number.desc()).limit(1)
        model = self.session.execute(stmt).scalar_one_or_none()
        return self._to_entity(model) if model else None

    def list_by_rule(self, rule_id: UUID) -> List[RuleVersion]:
        stmt = select(RuleVersionModel).where(
            RuleVersionModel.rule_id == str(rule_id)
        ).order_by(RuleVersionModel.version_number.asc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_entity(m) for m in models]


class SqliteModelRepository(IModelRepository):
    """SQLite implementation of IModelRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _to_entity(self, record: MLModel) -> Model:
        exec_type: Union[ExecutionType, str] = ExecutionType.BUILTIN
        if record.execution_type:
            try:
                exec_type = ExecutionType(record.execution_type)
            except ValueError:
                exec_type = record.execution_type

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
                hyperparameters=run.hyperparameters,
                custom_metrics=run.custom_metrics,
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
            record.hyperparameters = run.hyperparameters
            record.custom_metrics = run.custom_metrics
            record.compute_target = run.compute_target
            record.error_message = run.error_message
            record.started_at = run.started_at
            record.completed_at = run.completed_at
            record.duration_seconds = run.duration_seconds
            record.logs_path = run.logs_path
            record.metrics_path = run.metrics_path
            record.eval_predictions_path = run.eval_predictions_path

        self.session.flush()
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


__all__ = [
    "SqliteProjectRepository",
    "SqliteDatasetRepository",
    "SqliteDatasetArtifactRepository",
    "SqliteRuleRepository",
    "SqliteRuleVersionRepository",
    "SqliteModelRepository",
    "SqliteModelVersionRepository",
    "SqliteTrainingRunRepository",
]
