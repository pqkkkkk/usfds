from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import (
    DetectionJobStatus,
    ProjectStatus,
    TrainingRunStatus,
)
from usfds_core.domain.entities.system import Project
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_dataset_repo import IDatasetRepository
from usfds_core.repositories.base_detection_job_repo import IDetectionJobRepository
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_core.repositories.base_rule_repo import IRuleRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository
from usfds_core.repositories.in_memory_repos import InMemoryProjectRepository
from usfds_core.storage.base_storage import IFileStorage


class ProjectManagementService:
    """Application Service managing Project lifecycle, cross-resource governance,
    and RAW schema locking/unlocking rules (BR-PM-01 through BR-PM-08).
    """

    def __init__(
        self,
        project_repo: Optional[IProjectRepository] = None,
        dataset_repo: Optional[IDatasetRepository] = None,
        artifact_repo: Optional[IDatasetArtifactRepository] = None,
        rule_repo: Optional[IRuleRepository] = None,
        training_run_repo: Optional[ITrainingRunRepository] = None,
        detection_job_repo: Optional[IDetectionJobRepository] = None,
        file_storage: Optional[IFileStorage] = None,
    ) -> None:
        self.project_repo = project_repo or InMemoryProjectRepository()
        self.dataset_repo = dataset_repo
        self.artifact_repo = artifact_repo
        self.rule_repo = rule_repo
        self.training_run_repo = training_run_repo
        self.detection_job_repo = detection_job_repo
        self.file_storage = file_storage

    def _compute_project_stats(self, project_id: UUID) -> Dict[str, int]:
        datasets_count = (
            len(self.dataset_repo.list_by_project(project_id))
            if self.dataset_repo is not None
            else 0
        )
        rules_count = (
            len(self.rule_repo.list_by_project(project_id))
            if self.rule_repo is not None
            else 0
        )
        detection_jobs_count = (
            len(self.detection_job_repo.list_by_project(project_id))
            if self.detection_job_repo is not None
            else 0
        )
        return {
            "datasets_count": datasets_count,
            "rules_count": rules_count,
            "detection_jobs_count": detection_jobs_count,
        }

    def _check_active_workloads(self, project_id: UUID, action_label: str = "xóa hoặc lưu trữ") -> None:
        """Enforces BR-PM-08: Prevents deleting or archiving a project with active/running jobs."""
        if self.detection_job_repo is not None:
            jobs = self.detection_job_repo.list_by_project(project_id)
            active_jobs = [
                j for j in jobs
                if str(j.status.value if hasattr(j.status, "value") else j.status)
                in (DetectionJobStatus.RUNNING.value, DetectionJobStatus.PENDING.value)
            ]
            if active_jobs:
                raise ValueError(
                    f"Không thể {action_label} dự án '{project_id}' khi đang có {len(active_jobs)} "
                    f"tác vụ DetectionJob ở trạng thái RUNNING/PENDING."
                )

        if self.training_run_repo is not None and hasattr(self.training_run_repo, "_runs"):
            runs = [
                r for r in getattr(self.training_run_repo, "_runs", {}).values()
                if getattr(r, "project_id", None) == project_id
                and str(r.status.value if hasattr(r.status, "value") else r.status)
                in (TrainingRunStatus.RUNNING.value, TrainingRunStatus.PENDING.value)
            ]
            if runs:
                raise ValueError(
                    f"Không thể {action_label} dự án '{project_id}' khi đang có {len(runs)} "
                    f"tiến trình huấn luyện (TrainingRun) ở trạng thái RUNNING/PENDING."
                )

    def create_project(
        self,
        project_name: str,
        user_id: Optional[Union[UUID, str]] = None,
        description: Optional[str] = None,
        project_id: Optional[Union[UUID, str]] = None,
    ) -> Project:
        """Creates a new Project with unlocked schema (raw_schema = None) and enforces BR-PM-07 uniqueness."""
        clean_name = (project_name or "").strip()
        if not clean_name:
            raise ValueError("Tên dự án (project_name) không được để trống.")

        effective_user_id = UUID(str(user_id)) if user_id else uuid4()
        effective_project_id = UUID(str(project_id)) if project_id else uuid4()

        existing = self.project_repo.get_by_name(effective_user_id, clean_name)
        if existing is not None:
            raise ValueError(
                f"Dự án với tên '{clean_name}' đã tồn tại cho người dùng này. Vui lòng chọn tên khác."
            )

        now = datetime.now(timezone.utc)
        project = Project(
            project_id=effective_project_id,
            project_name=clean_name,
            user_id=effective_user_id,
            description=description,
            status=ProjectStatus.ACTIVE,
            base_dataset_id=None,
            raw_schema=None,
            created_at=now,
            updated_at=now,
        )
        return self.project_repo.save(project)

    def get_project(self, project_id: Union[UUID, str]) -> Project:
        """Retrieves a Project by ID or raises LookupError if not found."""
        p_uuid = UUID(str(project_id))
        project = self.project_repo.get_by_id(p_uuid)
        if not project:
            raise LookupError(f"Dự án '{p_uuid}' không tồn tại.")
        return project

    def get_project_with_stats(self, project_id: Union[UUID, str]) -> Tuple[Project, Dict[str, int]]:
        """Retrieves a Project along with resource counts."""
        project = self.get_project(project_id)
        stats = self._compute_project_stats(project.project_id)
        return project, stats

    def list_projects(
        self,
        user_id: Optional[Union[UUID, str]] = None,
        status: Optional[Union[ProjectStatus, str]] = None,
        search: Optional[str] = None,
    ) -> List[Tuple[Project, Dict[str, int]]]:
        """Lists projects with optional filtering and attaches resource statistics."""
        u_uuid = UUID(str(user_id)) if user_id else None
        projects = self.project_repo.list_all(user_id=u_uuid, status=status, search=search)
        return [(p, self._compute_project_stats(p.project_id)) for p in projects]

    def update_project(
        self,
        project_id: Union[UUID, str],
        project_name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[Union[ProjectStatus, str]] = None,
    ) -> Project:
        """Updates Project metadata or status while enforcing BR-PM-07 and BR-PM-08."""
        project = self.get_project(project_id)

        if project_name is not None:
            clean_name = project_name.strip()
            if not clean_name:
                raise ValueError("Tên dự án (project_name) không được để trống.")
            if clean_name.lower() != project.project_name.lower():
                existing = self.project_repo.get_by_name(project.user_id, clean_name)
                if existing is not None and existing.project_id != project.project_id:
                    raise ValueError(
                        f"Dự án với tên '{clean_name}' đã tồn tại cho người dùng này. Vui lòng chọn tên khác."
                    )
            project.project_name = clean_name

        if description is not None:
            project.description = description

        if status is not None:
            target_status = (
                status
                if isinstance(status, ProjectStatus)
                else ProjectStatus(str(status).upper())
            )
            if target_status == ProjectStatus.ARCHIVED:
                self._check_active_workloads(project.project_id, action_label="lưu trữ (ARCHIVE)")
            project.status = target_status

        project.updated_at = datetime.now(timezone.utc)
        return self.project_repo.save(project)

    def reset_project_schema(self, project_id: Union[UUID, str]) -> Project:
        """Explicitly unlocks/resets `project.raw_schema = None` when no dependent resources exist (BR-PM-03)."""
        project = self.get_project(project_id)
        stats = self._compute_project_stats(project.project_id)

        if stats["datasets_count"] > 0 or stats["rules_count"] > 0 or stats["detection_jobs_count"] > 0:
            raise ValueError(
                f"Không thể đặt lại (reset) RAW schema khi dự án vẫn còn tài nguyên phụ thuộc "
                f"(datasets={stats['datasets_count']}, rules={stats['rules_count']}, "
                f"detection_jobs={stats['detection_jobs_count']}). "
                f"Vui lòng xóa các tài nguyên phụ thuộc trước."
            )

        project.raw_schema = None
        project.base_dataset_id = None
        project.updated_at = datetime.now(timezone.utc)
        return self.project_repo.save(project)

    def handle_dataset_deleted(
        self,
        project_id: Union[UUID, str],
        deleted_dataset_id: Union[UUID, str],
    ) -> Optional[Project]:
        """Automatically unlocks `raw_schema` if the last dataset in a project is deleted and no rules/jobs exist,
        or preserves `raw_schema` if other resources still depend on it.
        """
        p_uuid = UUID(str(project_id))
        d_uuid = UUID(str(deleted_dataset_id))
        project = self.project_repo.get_by_id(p_uuid)
        if not project:
            return None

        remaining_datasets = (
            self.dataset_repo.list_by_project(p_uuid)
            if self.dataset_repo is not None
            else []
        )
        remaining_rules = (
            self.rule_repo.list_by_project(p_uuid)
            if self.rule_repo is not None
            else []
        )
        remaining_jobs = (
            self.detection_job_repo.list_by_project(p_uuid)
            if self.detection_job_repo is not None
            else []
        )

        if not remaining_datasets and not remaining_rules and not remaining_jobs:
            project.raw_schema = None
            project.base_dataset_id = None
            project.updated_at = datetime.now(timezone.utc)
            return self.project_repo.save(project)

        if project.base_dataset_id == d_uuid:
            # Keep raw_schema intact on the Project record, update base_dataset_id pointer
            project.base_dataset_id = (
                remaining_datasets[-1].dataset_id if remaining_datasets else None
            )
            project.updated_at = datetime.now(timezone.utc)
            return self.project_repo.save(project)

        return project

    def delete_project(self, project_id: Union[UUID, str]) -> bool:
        """Deletes a Project and cascades deletion to its datasets, rules, and physical storage (BR-PM-08)."""
        project = self.get_project(project_id)
        p_uuid = project.project_id

        # 1. Verify no running/pending jobs
        self._check_active_workloads(p_uuid, action_label="xóa (DELETE)")

        # 2. Cascade delete Rules in project
        if self.rule_repo is not None:
            for rule in self.rule_repo.list_by_project(p_uuid):
                self.rule_repo.delete(rule.rule_id)

        # 3. Cascade delete Datasets & their physical files in project
        if self.dataset_repo is not None:
            for ds in self.dataset_repo.list_by_project(p_uuid):
                if self.file_storage is not None:
                    try:
                        self.file_storage.delete(f"datasets/{ds.dataset_id}")
                    except Exception:
                        pass
                self.dataset_repo.delete(ds.dataset_id)

        # 4. Clean up project-level inference/model storage directories if any
        if self.file_storage is not None:
            for prefix in (f"datasets/{p_uuid}", f"models/{p_uuid}"):
                try:
                    self.file_storage.delete(prefix)
                except Exception:
                    pass

        # 5. Delete Project record
        return self.project_repo.delete(p_uuid)


__all__ = ["ProjectManagementService"]
