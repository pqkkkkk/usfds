import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID
import pandas as pd

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import DataClassification, PipelineStage
from usfds_core.domain.schemas.preprocessing_config import (
    DataMappingConfig,
    FeatureEngineeringConfig,
)
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_dataset_repo import IDatasetRepository
from usfds_core.services.data_management.export import DatasetExportService
from usfds_core.services.data_management.ingestion import DatasetIngestionService
from usfds_core.services.data_management.lineage import DataLineageService, LineageGraph
from usfds_core.services.data_management.mapping import DataMappingService
from usfds_core.services.data_management.profiling import DataProfilingService
from usfds_core.services.data_management.validation import DataQualityValidationService
from usfds_core.services.preprocessing.feature_engineering_service import (
    FeatureEngineeringExecutionService,
)
from usfds_core.storage.base_storage import IFileStorage


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
        ingestion_service: Optional[DatasetIngestionService] = None,
        profiling_service: Optional[DataProfilingService] = None,
        mapping_service: Optional[DataMappingService] = None,
        validation_service: Optional[DataQualityValidationService] = None,
        lineage_service: Optional[DataLineageService] = None,
        export_service: Optional[DatasetExportService] = None,
        fe_service: Optional[FeatureEngineeringExecutionService] = None,
    ) -> None:
        self.dataset_repo = dataset_repo
        self.artifact_repo = artifact_repo
        self.file_storage = file_storage

        self.profiling_service = profiling_service or DataProfilingService()
        self.validation_service = validation_service or DataQualityValidationService()
        self.ingestion_service = ingestion_service or DatasetIngestionService(
            file_storage=file_storage,
            artifact_repo=artifact_repo,
            dataset_repo=dataset_repo,
            profiling_service=self.profiling_service,
        )
        self.mapping_service = mapping_service or DataMappingService(
            file_storage=file_storage,
            artifact_repo=artifact_repo,
            validation_service=self.validation_service,
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
        """Deletes a dataset and removes its associated metadata."""
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' không tồn tại.")
        self.dataset_repo.delete(dataset_id)


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

        fe_artifact = self.fe_service.execute(
            parent_artifact=mapped_art,
            config=config,
            user_name=user_name,
        )
        fe_artifact.created_by = user_name
        self.artifact_repo.save(fe_artifact)
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


__all__ = ["DataManagementService"]
