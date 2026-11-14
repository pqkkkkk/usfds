"""SQLAlchemy repositories for the `project` domain (moved from database/repositories.py, 26-11-14)."""
from datetime import datetime, timezone
from typing import Any, List, Optional, Union
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from usfds_core.domain.entities.enums import ProjectStatus
from usfds_core.domain.entities.system import Project
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_infra.database.models import ProjectModel
from usfds_infra.database.repos.model import SqliteTrainingRunRepository  # shared _sanitize_json helper


class SqliteProjectRepository(IProjectRepository):
    """SQLite implementation of IProjectRepository using SQLAlchemy."""

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
