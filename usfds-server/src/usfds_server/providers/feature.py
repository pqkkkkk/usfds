"""FastAPI dependency providers for Feature Management (ISS-040)."""
from fastapi import Depends

from usfds_core.services.features.code_validator import get_allowed_imports
from usfds_core.services.features.feature_service import FeatureManagementService
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_infra.database import (
	SqlFeatureRepository,
	SqlFeatureSetRepository,
	SqlSystemColumnMetadataRepository,
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteProjectRepository,
)
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.config import settings
from usfds_server.dependencies import get_storage
from usfds_server.providers.repos import (
	get_artifact_repo,
	get_dataset_repo,
	get_feature_repo,
	get_feature_set_repo,
	get_project_repo,
	get_system_metadata_repo,
)
from usfds_server.providers.rule import get_rule_manager


def get_feature_management_service(
	feature_repo: SqlFeatureRepository = Depends(get_feature_repo),
	feature_set_repo: SqlFeatureSetRepository = Depends(get_feature_set_repo),
	project_repo: SqliteProjectRepository = Depends(get_project_repo),
	dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
	artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
	metadata_repo: SqlSystemColumnMetadataRepository = Depends(get_system_metadata_repo),
	rule_manager: RuleManager = Depends(get_rule_manager),
	storage: LocalFileStorage = Depends(get_storage),
) -> FeatureManagementService:
	allowed = get_allowed_imports(settings.feature_allowed_imports.split(","))
	return FeatureManagementService(
		feature_repo=feature_repo,
		feature_set_repo=feature_set_repo,
		project_repo=project_repo,
		dataset_repo=dataset_repo,
		artifact_repo=artifact_repo,
		metadata_repo=metadata_repo,
		rule_manager=rule_manager,
		file_storage=storage,
		duckdb_memory_mb=settings.feature_duckdb_memory_mb,
		preview_max_rows=settings.feature_preview_max_rows,
		script_max_bytes=settings.feature_script_max_bytes,
		allowed_imports=allowed,
	)


__all__ = ["get_feature_management_service"]
