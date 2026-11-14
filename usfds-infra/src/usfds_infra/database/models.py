"""Compatibility shim: ORM tables now live in `usfds_infra.database.tables.<domain>` (split 26-11-14, ISS-026).

New tables go into a new or existing `tables/<domain>.py`; then append the import below (append-only hot spot).
Importing this module registers every table on `Base.metadata` (used by Alembic env and repositories).
"""
from usfds_infra.database.tables.project import ProjectModel
from usfds_infra.database.tables.dataset import DatasetArtifactModel, DatasetModel
from usfds_infra.database.tables.rule import RuleModel, RuleVersionModel
from usfds_infra.database.tables.model import MLModel, ModelVersionModel, RunDatasetModel, TrainingRunModel
from usfds_infra.database.tables.detection import DetectionJobModel

__all__ = [
	"ProjectModel",
	"DatasetModel",
	"DatasetArtifactModel",
	"RuleModel",
	"RuleVersionModel",
	"MLModel",
	"ModelVersionModel",
	"TrainingRunModel",
	"RunDatasetModel",
	"DetectionJobModel",
]
