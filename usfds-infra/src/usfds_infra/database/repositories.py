"""Compatibility shim: repositories now live in `usfds_infra.database.repos.<domain>` (split 26-11-14, ISS-026).

New repositories go into a new or existing `repos/<domain>.py`; then append the import below (append-only hot spot).
"""
from usfds_infra.database.repos.project import SqliteProjectRepository
from usfds_infra.database.repos.dataset import SqliteDatasetArtifactRepository, SqliteDatasetRepository
from usfds_infra.database.repos.rule import SqliteRuleRepository, SqliteRuleVersionRepository
from usfds_infra.database.repos.model import (
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteTrainingRunRepository,
)
from usfds_infra.database.repos.detection import SqliteDetectionJobRepository

__all__ = [
	"SqliteProjectRepository",
	"SqliteDatasetRepository",
	"SqliteDatasetArtifactRepository",
	"SqliteRuleRepository",
	"SqliteRuleVersionRepository",
	"SqliteModelRepository",
	"SqliteModelVersionRepository",
	"SqliteTrainingRunRepository",
	"SqliteDetectionJobRepository",
]
