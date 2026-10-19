from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import DataClassification, PipelineStage, RuleAction, RuleStatus, ValidationStatus
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_dataset_repo import IDatasetRepository
from usfds_core.repositories.base_rule_repo import IRuleRepository, IRuleVersionRepository
from usfds_infra.database.models import DatasetArtifactModel, DatasetModel, RuleModel, RuleVersionModel


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


__all__ = [
    "SqliteDatasetRepository",
    "SqliteDatasetArtifactRepository",
    "SqliteRuleRepository",
    "SqliteRuleVersionRepository",
]
