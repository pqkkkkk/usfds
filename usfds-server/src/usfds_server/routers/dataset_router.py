from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import DataClassification
from usfds_core.domain.schemas.preprocessing_config import (
    DataMappingConfig,
    FeatureEngineeringConfig,
)
from usfds_core.services.data_management.service import DataManagementService
from usfds_server.dependencies import get_data_management_service
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.dataset_api_schemas import (
    DatasetArtifactResponse,
    DatasetDetailResponse,
    DatasetResponse,
    ExportDatasetRequest,
    ImportDatasetRequest,
)

router = APIRouter(prefix="/api/v1/datasets", tags=["Data Management"])


def _build_dataset_response(
    dataset: Dataset,
    artifacts: List[DatasetArtifact],
) -> DatasetResponse:
    latest_art = artifacts[-1] if artifacts else None
    latest_stage = (
        str(latest_art.pipeline_stage.value if hasattr(latest_art.pipeline_stage, "value") else latest_art.pipeline_stage)
        if latest_art else None
    )
    latest_status = (
        str(latest_art.validation_status.value if hasattr(latest_art.validation_status, "value") else latest_art.validation_status)
        if latest_art else None
    )

    quality_score = None
    if latest_art and isinstance(latest_art.validation_report, dict):
        quality_score = latest_art.validation_report.get("quality_score")

    return DatasetResponse(
        dataset_id=dataset.dataset_id,
        project_id=dataset.project_id,
        user_id=dataset.user_id,
        dataset_name=dataset.dataset_name,
        display_name=dataset.display_name,
        description=dataset.description,
        contains_pii=dataset.contains_pii,
        data_classification=(
            str(dataset.data_classification.value if hasattr(dataset.data_classification, "value") else dataset.data_classification)
            if dataset.data_classification else None
        ),
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        latest_stage=latest_stage,
        latest_validation_status=latest_status,
        quality_score=quality_score,
        artifacts_count=len(artifacts),
    )


def _build_artifact_response(art: DatasetArtifact) -> DatasetArtifactResponse:
    stage_str = str(art.pipeline_stage.value if hasattr(art.pipeline_stage, "value") else art.pipeline_stage)
    status_str = (
        str(art.validation_status.value if hasattr(art.validation_status, "value") else art.validation_status)
        if art.validation_status else None
    )
    quality_score = None
    if isinstance(art.validation_report, dict):
        quality_score = art.validation_report.get("quality_score")

    return DatasetArtifactResponse(
        artifact_id=art.artifact_id,
        dataset_id=art.dataset_id,
        parent_artifact_id=art.parent_artifact_id,
        pipeline_stage=stage_str,
        change_type=art.change_type,
        storage_path=art.storage_path,
        output_paths=art.output_paths,
        checksum_sha256=art.checksum_sha256,
        schema_snapshot=art.schema_snapshot,
        row_count=art.row_count,
        column_count=art.column_count,
        validation_status=status_str,
        quality_score=quality_score,
        validation_report=art.validation_report,
        created_by=art.created_by,
        created_at=art.created_at,
    )




@router.post("/import", response_model=ApiResponse[DatasetDetailResponse], status_code=status.HTTP_201_CREATED)
def import_dataset(
    req: ImportDatasetRequest,
    service: DataManagementService = Depends(get_data_management_service),
) -> ApiResponse[DatasetDetailResponse]:
    """Entry point for Data Management: Ingest raw dataset from local file path, create Dataset entity,
    compute basic data profiling, and generate RAW artifact in one step.
    """
    try:
        classification = None
        if req.data_classification:
            try:
                classification = DataClassification(req.data_classification)
            except ValueError:
                classification = DataClassification.INTERNAL

        dataset, artifact = service.import_dataset(
            file_path=req.file_path,
            dataset_name=req.dataset_name,
            display_name=req.display_name,
            description=req.description,
            project_id=req.project_id,
            user_id=req.user_id,
            contains_pii=req.contains_pii,
            data_classification=classification,
        )
        lineage = service.get_lineage(dataset.dataset_id)
        detail = DatasetDetailResponse(
            dataset=_build_dataset_response(dataset, [artifact]),
            artifacts=[_build_artifact_response(artifact)],
            lineage=lineage.to_dict(),
        )
        return ApiResponse.ok(
            data=detail,
            status_code=status.HTTP_201_CREATED,
            message="Dataset imported successfully",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=ApiResponse[List[DatasetResponse]])
def list_datasets(
    project_id: Optional[UUID] = Query(None, description="Filter by Project ID"),
    search: Optional[str] = Query(None, description="Search query by name or description"),
    service: DataManagementService = Depends(get_data_management_service),
) -> ApiResponse[List[DatasetResponse]]:
    """List all datasets with latest pipeline stage and quality score summary."""
    items = service.list_datasets(project_id=project_id, search=search)
    return ApiResponse.ok(
        data=[_build_dataset_response(ds, arts) for ds, arts in items],
        message="Datasets retrieved successfully",
    )


@router.get("/{dataset_id}", response_model=ApiResponse[DatasetDetailResponse])
def get_dataset(
    dataset_id: UUID,
    service: DataManagementService = Depends(get_data_management_service),
) -> ApiResponse[DatasetDetailResponse]:
    """Retrieve complete metadata, history of artifacts, and lineage DAG for a dataset."""
    try:
        dataset, artifacts, lineage = service.get_dataset(dataset_id)
        detail = DatasetDetailResponse(
            dataset=_build_dataset_response(dataset, artifacts),
            artifacts=[_build_artifact_response(a) for a in artifacts],
            lineage=lineage.to_dict(),
        )
        return ApiResponse.ok(data=detail, message="Dataset retrieved successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{dataset_id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
def delete_dataset(
    dataset_id: UUID,
    service: DataManagementService = Depends(get_data_management_service),
) -> ApiResponse[None]:
    """Delete a dataset and all associated artifacts."""
    try:
        service.delete_dataset(dataset_id)
        return ApiResponse.ok(data=None, message="Dataset deleted successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))



@router.post("/{dataset_id}/schema-mapping", response_model=ApiResponse[DatasetArtifactResponse], status_code=status.HTTP_201_CREATED)
def map_schema(
    dataset_id: UUID,
    mapping_config: DataMappingConfig,
    service: DataManagementService = Depends(get_data_management_service),
) -> ApiResponse[DatasetArtifactResponse]:
    """Map raw columns to standard 5-core FDS fields, convert to mapped.parquet, and validate."""
    try:
        artifact = service.map_schema(dataset_id=dataset_id, mapping_config=mapping_config)
        return ApiResponse.ok(
            data=_build_artifact_response(artifact),
            status_code=status.HTTP_201_CREATED,
            message="Schema mapped and validated successfully",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{dataset_id}/artifacts/{artifact_id}", response_model=ApiResponse[DatasetArtifactResponse])
def get_artifact(
    dataset_id: UUID,
    artifact_id: UUID,
    service: DataManagementService = Depends(get_data_management_service),
) -> ApiResponse[DatasetArtifactResponse]:
    """Retrieve complete metadata and validation details for a specific artifact."""
    try:
        artifact = service.get_artifact(dataset_id, artifact_id)
        return ApiResponse.ok(
            data=_build_artifact_response(artifact),
            message="Artifact retrieved successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{dataset_id}/feature-engineering", response_model=ApiResponse[DatasetArtifactResponse], status_code=status.HTTP_201_CREATED)
def execute_feature_engineering(
    dataset_id: UUID,
    config: FeatureEngineeringConfig,
    service: DataManagementService = Depends(get_data_management_service),
) -> ApiResponse[DatasetArtifactResponse]:
    """Execute feature engineering pipeline stage from MAPPED artifact."""
    try:
        artifact = service.execute_feature_engineering(dataset_id, config)
        return ApiResponse.ok(
            data=_build_artifact_response(artifact),
            status_code=status.HTTP_201_CREATED,
            message="Feature engineering completed successfully",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



@router.post("/{dataset_id}/artifacts/{artifact_id}/export")
def export_normalized_dataset(
    dataset_id: UUID,
    artifact_id: UUID,
    req: ExportDatasetRequest,
    service: DataManagementService = Depends(get_data_management_service),
) -> Response:
    """Export normalized dataset files as a compressed ZIP package."""
    try:
        zip_bytes, filename = service.export_dataset(
            dataset_id=dataset_id,
            artifact_id=artifact_id,
            include_train=req.include_train,
            include_test=req.include_test,
            include_pipeline=req.include_pipeline,
            include_schema=req.include_schema,
            file_format=req.file_format,
        )
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


__all__ = ["router"]
