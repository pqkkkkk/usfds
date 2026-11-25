import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID
import pandas as pd

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import DataClassification, PipelineStage
from usfds_core.domain.entities.feature import DatasetArtifactFeatureLink, Feature
from usfds_core.domain.schemas.preprocessing_config import (
    DataMappingConfig,
    FeatureEngineeringConfig,
)
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_dataset_repo import IDatasetRepository
from usfds_core.repositories.base_detection_job_repo import IDetectionJobRepository
from usfds_core.repositories.base_feature_repo import IFeatureRepository, IFeatureSetRepository
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_core.repositories.base_system_metadata_repo import ISystemColumnMetadataRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository
from usfds_core.services.data_management.export import DatasetExportService
from usfds_core.services.data_management.ingestion import DatasetIngestionService
from usfds_core.services.data_management.lineage import DataLineageService, LineageGraph
from usfds_core.services.data_management.mapping import DataMappingService
from usfds_core.services.data_management.profiling import DataProfilingService
from usfds_core.services.data_management.validation import DataQualityValidationService
from usfds_core.services.preprocessing.feature_engineering_service import (
    FeatureEngineeringExecutionService,
)
from usfds_core.services.project_management.project_service import ProjectManagementService
from usfds_core.storage.base_storage import IFileStorage


class DatasetInUseError(ValueError):
    """Raised when attempting to delete a dataset currently referenced by active runs or jobs."""


class DataManagementService:
    """Unified Application Service / Facade orchestrating all Data Management use cases.

    Provides an entry-point for the desktop application, encapsulating repository access,
    file storage operations, profiling, schema mapping, validation, lineage, and export.
    """

    def __init__(
        self,
        dataset_repo: IDatasetRepository,
        artifact_repo: IDatasetArtifactRepository,
        file_storage: IFileStorage,
        project_repo: Optional[IProjectRepository] = None,
        project_service: Optional[ProjectManagementService] = None,
        training_run_repo: Optional[ITrainingRunRepository] = None,
        detection_job_repo: Optional[IDetectionJobRepository] = None,
        metadata_repo: Optional[ISystemColumnMetadataRepository] = None,
        ingestion_service: Optional[DatasetIngestionService] = None,
        profiling_service: Optional[DataProfilingService] = None,
        mapping_service: Optional[DataMappingService] = None,
        validation_service: Optional[DataQualityValidationService] = None,
        lineage_service: Optional[DataLineageService] = None,
        export_service: Optional[DatasetExportService] = None,
        fe_service: Optional[FeatureEngineeringExecutionService] = None,
        feature_repo: Optional[IFeatureRepository] = None,
        feature_set_repo: Optional[IFeatureSetRepository] = None,
    ) -> None:
        self.dataset_repo = dataset_repo
        self.artifact_repo = artifact_repo
        self.file_storage = file_storage
        self.project_repo = project_repo
        self.project_service = project_service
        self.training_run_repo = training_run_repo
        self.detection_job_repo = detection_job_repo
        self.metadata_repo = metadata_repo
        self.feature_repo = feature_repo
        self.feature_set_repo = feature_set_repo

        self.profiling_service = profiling_service or DataProfilingService()
        self.validation_service = validation_service or DataQualityValidationService()
        self.ingestion_service = ingestion_service or DatasetIngestionService(
            file_storage=file_storage,
            artifact_repo=artifact_repo,
            dataset_repo=dataset_repo,
            project_repo=project_repo,
            profiling_service=self.profiling_service,
        )
        self.mapping_service = mapping_service or DataMappingService(
            file_storage=file_storage,
            artifact_repo=artifact_repo,
            validation_service=self.validation_service,
            metadata_repo=metadata_repo,
        )
        self.lineage_service = lineage_service or DataLineageService(
            artifact_repo=artifact_repo
        )
        self.export_service = export_service or DatasetExportService(
            file_storage=file_storage
        )
        self.fe_service = fe_service or FeatureEngineeringExecutionService(
            file_storage=file_storage
        )


    def list_datasets(
        self,
        project_id: Optional[UUID] = None,
        search: Optional[str] = None,
    ) -> List[Tuple[Dataset, List[DatasetArtifact]]]:
        """Lists datasets with their associated artifacts."""
        datasets = self.dataset_repo.list_all(project_id=project_id, search=search)
        results: List[Tuple[Dataset, List[DatasetArtifact]]] = []
        for ds in datasets:
            artifacts = self.artifact_repo.list_by_dataset(ds.dataset_id)
            results.append((ds, artifacts))
        return results

    def get_dataset(self, dataset_id: UUID) -> Tuple[Dataset, List[DatasetArtifact], LineageGraph]:
        """Retrieves a single dataset, all of its artifacts, and its lineage tree/DAG."""
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' không tồn tại.")
        artifacts = self.artifact_repo.list_by_dataset(dataset_id)
        lineage = self.lineage_service.get_lineage(dataset_id)
        return dataset, artifacts, lineage

    def get_artifact(self, dataset_id: UUID, artifact_id: UUID) -> DatasetArtifact:
        """Retrieves a single artifact by its ID, ensuring it belongs to the given dataset."""
        artifact = self.artifact_repo.get_by_id(artifact_id)
        if not artifact or artifact.dataset_id != dataset_id:
            raise ValueError(f"Artifact '{artifact_id}' không tồn tại trong dataset '{dataset_id}'.")
        return artifact

    def delete_dataset(self, dataset_id: UUID) -> None:
        """Deletes a dataset, removes its physical storage files/directories, and deletes associated metadata."""
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' không tồn tại.")

        artifacts = self.artifact_repo.list_by_dataset(dataset_id)
        artifact_ids = [a.artifact_id for a in artifacts]

        # Guard against deleting datasets currently in use by active workloads (ISS-003)
        if artifact_ids:
            if self.training_run_repo is not None:
                active_runs = self.training_run_repo.list_active_by_artifact_ids(artifact_ids)
                if active_runs:
                    raise DatasetInUseError(
                        f"Không thể xóa dataset '{dataset_id}' vì đang được sử dụng bởi "
                        f"{len(active_runs)} tiến trình huấn luyện (TrainingRun) ở trạng thái PENDING/RUNNING."
                    )
            if self.detection_job_repo is not None:
                active_jobs = self.detection_job_repo.list_active_by_target_artifact_ids(artifact_ids)
                if active_jobs:
                    raise DatasetInUseError(
                        f"Không thể xóa dataset '{dataset_id}' vì đang được sử dụng bởi "
                        f"{len(active_jobs)} tác vụ phát hiện (DetectionJob) ở trạng thái PENDING/RUNNING."
                    )

        # 1. Clean up individual artifact files from storage (ISS-017)
        for artifact in artifacts:
            paths_to_delete = set()
            if artifact.storage_path:
                paths_to_delete.add(artifact.storage_path)
            if artifact.output_paths:
                for p in artifact.output_paths.values():
                    if isinstance(p, str):
                        paths_to_delete.add(p)
            for path in paths_to_delete:
                try:
                    self.file_storage.delete(path)
                except FileNotFoundError:
                    pass
                except Exception:
                    pass

        # 2. Also clean up dataset storage directory in storage
        try:
            self.file_storage.delete(f"datasets/{dataset_id}")
        except Exception:
            pass

        # 3. Delete persisted records
        self.dataset_repo.delete(dataset_id)

        # 4. Auto-unlock Project RAW schema if no dependent resources remain
        if self.project_service is not None:
            self.project_service.handle_dataset_deleted(dataset.project_id, dataset_id)
        elif self.project_repo is not None:
            temp_proj_svc = ProjectManagementService(
                project_repo=self.project_repo,
                dataset_repo=self.dataset_repo,
                artifact_repo=self.artifact_repo,
                file_storage=self.file_storage,
            )
            temp_proj_svc.handle_dataset_deleted(dataset.project_id, dataset_id)


    def import_dataset(
        self,
        file_path: Union[str, Path],
        dataset_name: Optional[str] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        project_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        contains_pii: bool = False,
        data_classification: Optional[DataClassification] = None,
        user_name: str = "system",
    ) -> Tuple[Dataset, DatasetArtifact]:
        """Imports a local raw dataset, creates the Dataset entity, calculates data profiling,

        and saves the RAW artifact.
        """
        return self.ingestion_service.import_dataset(
            file_path=file_path,
            dataset_name=dataset_name,
            display_name=display_name,
            description=description,
            project_id=project_id,
            user_id=user_id,
            contains_pii=contains_pii,
            data_classification=data_classification,
            user_name=user_name,
        )


    def map_schema(
        self,
        dataset_id: UUID,
        mapping_config: DataMappingConfig,
        user_name: str = "system",
    ) -> DatasetArtifact:
        """Executes schema mapping from RAW to standard 5-core fields and automatically validates."""
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' không tồn tại.")

        artifacts = self.artifact_repo.list_by_dataset(dataset_id)
        raw_art = next((a for a in artifacts if a.pipeline_stage == PipelineStage.RAW), None)
        if not raw_art:
            raise ValueError(f"Không tìm thấy bản ghi RAW artifact cho dataset '{dataset_id}'. Vui lòng import trước.")

        mapped_art = self.mapping_service.map_dataset(
            dataset_id=dataset_id,
            parent_artifact=raw_art,
            mapping_config=mapping_config,
            user_name=user_name,
        )
        return mapped_art

    def execute_feature_engineering(
        self,
        dataset_id: UUID,
        config: FeatureEngineeringConfig,
        user_name: str = "system",
    ) -> DatasetArtifact:
        """Executes feature engineering on a MAPPED dataset."""
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' không tồn tại.")

        artifacts = self.artifact_repo.list_by_dataset(dataset_id)
        mapped_art = next((a for a in artifacts if a.pipeline_stage == PipelineStage.MAPPED), None)
        if not mapped_art:
            raise ValueError("Kỹ thuật đặc trưng yêu cầu dataset đã hoàn tất bước Ánh xạ (MAPPED).")

        resolved_set_ids: List[UUID] = []
        if not config.feature_definitions and (config.feature_set_ids or config.feature_ids):
            if self.feature_repo is None or self.feature_set_repo is None:
                raise RuntimeError("Thiếu FeatureRepository hoặc FeatureSetRepository để giải mã Kho đặc trưng.")
            from usfds_core.services.features.compiler import DAGResolver

            for raw_sid in (config.feature_set_ids or []):
                sid = UUID(str(raw_sid))
                if sid not in resolved_set_ids:
                    resolved_set_ids.append(sid)

            origin_by_fid: Dict[UUID, Optional[UUID]] = {}
            selected_fids: List[UUID] = []
            if resolved_set_ids:
                for fs in self.feature_set_repo.list_by_ids(resolved_set_ids):
                    if fs.project_id is not None and fs.project_id != dataset.project_id:
                        raise ValueError(f"Gói đặc trưng '{fs.name}' không thuộc dự án hiện tại.")
                    for fid in (fs.feature_ids or []):
                        if fid not in origin_by_fid:
                            origin_by_fid[fid] = fs.feature_set_id
                            selected_fids.append(fid)

            for raw_fid in (config.feature_ids or []):
                fid = UUID(str(raw_fid))
                if fid not in origin_by_fid:
                    origin_by_fid[fid] = None
                    selected_fids.append(fid)

            if selected_fids:
                catalog = self.feature_repo.list_by_project(dataset.project_id, include_builtin=True)
                catalog_by_id = {f.feature_id: f for f in catalog}
                selected_feats: List[Feature] = []
                for fid in selected_fids:
                    feat = catalog_by_id.get(fid)
                    if feat is None:
                        raise ValueError(f"Đặc trưng '{fid}' không tồn tại trong phạm vi dự án.")
                    selected_feats.append(feat)

                full_feats = DAGResolver.collect_transitive_closure(selected_feats, catalog)
                def_dicts: List[Dict[str, Any]] = []
                for f in full_feats:
                    d = f.to_dict()
                    src_sid = origin_by_fid.get(f.feature_id)
                    if src_sid is not None:
                        d["source_feature_set_id"] = str(src_sid)
                    def_dicts.append(d)
                config.feature_definitions = def_dicts

        fe_artifact = self.fe_service.execute(
            parent_artifact=mapped_art,
            config=config,
            user_name=user_name,
        )
        fe_artifact.created_by = user_name
        self.artifact_repo.save(fe_artifact)

        if self.feature_set_repo is not None and resolved_set_ids:
            self.feature_set_repo.record_artifact_feature_sets(fe_artifact.artifact_id, resolved_set_ids)

        if self.feature_repo is not None and isinstance(fe_artifact.validation_report, dict):
            mat = fe_artifact.validation_report.get("materialized_features") or []
            links: List[DatasetArtifactFeatureLink] = []
            for item in mat:
                if not isinstance(item, dict) or not item.get("feature_key"):
                    continue
                links.append(
                    DatasetArtifactFeatureLink(
                        artifact_id=fe_artifact.artifact_id,
                        feature_key=str(item["feature_key"]),
                        feature_id=UUID(str(item["feature_id"])) if item.get("feature_id") else None,
                        source_feature_set_id=(
                            UUID(str(item["source_feature_set_id"]))
                            if item.get("source_feature_set_id")
                            else None
                        ),
                        status=str(item.get("status", "APPLIED")),
                    )
                )
            if links:
                self.feature_repo.record_artifact_features(fe_artifact.artifact_id, links)

        return fe_artifact


    def get_lineage(self, dataset_id: UUID) -> LineageGraph:
        """Constructs and returns the Data Lineage DAG."""
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' không tồn tại.")
        return self.lineage_service.get_lineage(dataset_id)


    def export_dataset(
        self,
        dataset_id: UUID,
        artifact_id: UUID,
        include_train: bool = True,
        include_test: bool = True,
        include_pipeline: bool = True,
        include_schema: bool = True,
        file_format: str = "parquet",
    ) -> Tuple[bytes, str]:
        """Bundles and exports normalized dataset files into a ZIP package."""
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' không tồn tại.")

        art = self.artifact_repo.get_by_id(artifact_id)
        if not art or art.dataset_id != dataset_id:
            raise ValueError(f"Artifact '{artifact_id}' không tồn tại cho dataset '{dataset_id}'.")

        return self.export_service.export_artifact_bundle(
            artifact=art,
            include_train=include_train,
            include_test=include_test,
            include_pipeline=include_pipeline,
            include_schema=include_schema,
            file_format=file_format,
        )

    def export_dataset_to_file(
        self,
        dataset_id: UUID,
        artifact_id: UUID,
        dest_path: Union[str, Path],
        include_train: bool = True,
        include_test: bool = True,
        include_pipeline: bool = True,
        include_schema: bool = True,
        file_format: str = "parquet",
    ) -> str:
        """Bundles and writes normalized dataset files into a ZIP archive on disk."""
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' không tồn tại.")

        art = self.artifact_repo.get_by_id(artifact_id)
        if not art or art.dataset_id != dataset_id:
            raise ValueError(f"Artifact '{artifact_id}' không tồn tại cho dataset '{dataset_id}'.")

        return self.export_service.export_artifact_bundle_to_file(
            artifact=art,
            dest_path=dest_path,
            include_train=include_train,
            include_test=include_test,
            include_pipeline=include_pipeline,
            include_schema=include_schema,
            file_format=file_format,
        )


__all__ = ["DataManagementService"]
