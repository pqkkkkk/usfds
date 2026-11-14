"""SQLAlchemy repositories for the `detection` domain (moved from database/repositories.py, 26-11-14)."""
from datetime import datetime, timezone
from typing import Any, List, Optional, Union
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus
from usfds_core.repositories.base_detection_job_repo import IDetectionJobRepository
from usfds_infra.database.models import DetectionJobModel
from usfds_infra.database.repos.model import SqliteTrainingRunRepository  # shared _sanitize_json helper


class SqliteDetectionJobRepository(IDetectionJobRepository):
    """SQLite implementation of IDetectionJobRepository using SQLAlchemy."""

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

    def _to_entity(self, record: DetectionJobModel) -> DetectionJob:
        status_val: Union[DetectionJobStatus, str] = DetectionJobStatus.PENDING
        if record.status:
            try:
                status_val = DetectionJobStatus(record.status)
            except ValueError:
                status_val = record.status

        return DetectionJob(
            job_id=UUID(record.job_id),
            project_id=UUID(record.project_id),
            deployment_id=UUID(record.deployment_id) if record.deployment_id else None,
            target_artifact_id=UUID(record.target_artifact_id) if record.target_artifact_id else None,
            model_version_id=UUID(record.model_version_id) if record.model_version_id else None,
            job_name=record.job_name,
            input_path=record.input_path or "",
            output_path=record.output_path,
            score_threshold=record.score_threshold,
            use_rules=record.use_rules,
            status=status_val,
            total_records=record.total_records,
            fraud_records=record.fraud_records,
            fraud_rate=record.fraud_rate,
            summary_metrics=record.summary_metrics,
            execution_time_seconds=record.execution_time_seconds,
            error_message=record.error_message,
            created_by=record.created_by,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
        )

    def save(self, job: DetectionJob) -> DetectionJob:
        record = self.session.get(DetectionJobModel, str(job.job_id))
        status_str = (
            job.status.value
            if hasattr(job.status, "value")
            else str(job.status)
        )

        clean_summary_metrics = self._sanitize_json(job.summary_metrics)

        if record is None:
            record = DetectionJobModel(
                job_id=str(job.job_id),
                project_id=str(job.project_id),
                deployment_id=str(job.deployment_id) if job.deployment_id else None,
                target_artifact_id=str(job.target_artifact_id) if job.target_artifact_id else None,
                model_version_id=str(job.model_version_id) if job.model_version_id else None,
                job_name=job.job_name,
                input_path=job.input_path or "",
                output_path=job.output_path,
                score_threshold=job.score_threshold,
                use_rules=job.use_rules,
                status=status_str,
                total_records=job.total_records,
                fraud_records=job.fraud_records,
                fraud_rate=job.fraud_rate,
                summary_metrics=clean_summary_metrics,
                execution_time_seconds=job.execution_time_seconds,
                error_message=job.error_message,
                created_by=job.created_by,
                created_at=job.created_at or datetime.now(timezone.utc),
                started_at=job.started_at,
                completed_at=job.completed_at,
            )
            self.session.add(record)
        else:
            record.deployment_id = str(job.deployment_id) if job.deployment_id else None
            record.target_artifact_id = str(job.target_artifact_id) if job.target_artifact_id else None
            record.model_version_id = str(job.model_version_id) if job.model_version_id else None
            record.job_name = job.job_name
            record.input_path = job.input_path or ""
            record.output_path = job.output_path
            record.score_threshold = job.score_threshold
            record.use_rules = job.use_rules
            record.status = status_str
            record.total_records = job.total_records
            record.fraud_records = job.fraud_records
            record.fraud_rate = job.fraud_rate
            record.summary_metrics = clean_summary_metrics
            record.execution_time_seconds = job.execution_time_seconds
            record.error_message = job.error_message
            record.started_at = job.started_at
            record.completed_at = job.completed_at

        try:
            self.session.flush()
        except Exception:
            self.session.rollback()
            raise
        return self._to_entity(record)

    def get_by_id(self, job_id: UUID) -> Optional[DetectionJob]:
        record = self.session.get(DetectionJobModel, str(job_id))
        return self._to_entity(record) if record else None

    def list_by_deployment(self, deployment_id: UUID) -> List[DetectionJob]:
        stmt = (
            select(DetectionJobModel)
            .where(DetectionJobModel.deployment_id == str(deployment_id))
            .order_by(DetectionJobModel.created_at.desc())
        )
        records = self.session.execute(stmt).scalars().all()
        return [self._to_entity(r) for r in records]

    def list_by_project(self, project_id: UUID) -> List[DetectionJob]:
        stmt = (
            select(DetectionJobModel)
            .where(DetectionJobModel.project_id == str(project_id))
            .order_by(DetectionJobModel.created_at.desc())
        )
        records = self.session.execute(stmt).scalars().all()
        return [self._to_entity(r) for r in records]

