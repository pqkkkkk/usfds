"""Synchronous job handlers. Each opens its own DB session so that the worker never shares state between jobs."""

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from usfds_core.domain.entities.enums import (
	DataClassification,
	DetectionJobStatus,
	RuleAction,
	TrainingRunStatus,
)
from usfds_core.domain.schemas.inference_payload import BatchInferencePayload
from usfds_core.domain.schemas.model_plugin import ModelPluginManifest
from usfds_core.domain.schemas.preprocessing_config import (
	DataMappingConfig,
	FeatureEngineeringConfig,
)
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.data_management.service import DataManagementService
from usfds_core.services.inference.executor import BatchInferenceExecutor
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.project_management.project_service import ProjectManagementService
from usfds_core.services.rule_engine.executor import RuleExecutor
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.plugins.register import ModelPluginRegistrationService
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_core.storage.base_storage import IFileStorage
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteDetectionJobRepository,
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteProjectRepository,
	SqliteRuleRepository,
	SqliteRuleVersionRepository,
	SqliteTrainingRunRepository,
)
from usfds_infra.database.case_repositories import SqliteCaseRepository

logger = logging.getLogger(__name__)


@dataclass
class WorkerContext:
	session_factory: sessionmaker[Session]
	storage: IFileStorage


def _build_data_management_service(session: Session, storage: IFileStorage) -> DataManagementService:
	dataset_repo = SqliteDatasetRepository(session)
	artifact_repo = SqliteDatasetArtifactRepository(session)
	project_repo = SqliteProjectRepository(session)
	rule_repo = SqliteRuleRepository(session)
	project_service = ProjectManagementService(
		project_repo=project_repo,
		dataset_repo=dataset_repo,
		artifact_repo=artifact_repo,
		rule_repo=rule_repo,
		file_storage=storage,
	)
	return DataManagementService(
		dataset_repo=dataset_repo,
		artifact_repo=artifact_repo,
		file_storage=storage,
		project_repo=project_repo,
		project_service=project_service,
	)


def _load_artifact_dataframe(artifact_path: str, storage: IFileStorage) -> pd.DataFrame:
	"""Load a Parquet or CSV DataFrame from IFileStorage or local path."""
	raw_bytes: Optional[bytes] = None
	if storage.exists(artifact_path):
		raw_bytes = storage.read_bytes(artifact_path)
	else:
		local_p = Path(artifact_path)
		if local_p.is_file():
			raw_bytes = local_p.read_bytes()

	if raw_bytes is None:
		raise FileNotFoundError(f"Dataset artifact file not found at '{artifact_path}'")

	if artifact_path.lower().endswith(".csv"):
		return pd.read_csv(io.BytesIO(raw_bytes))
	return pd.read_parquet(io.BytesIO(raw_bytes))


def handle_training_run(ctx: WorkerContext, data: Dict[str, Any]) -> None:
	"""Execute a training run and persist the result (TrainingRun status + candidate ModelVersion)."""
	payload = TrainingRunPayload.model_validate(data)
	logger.info(f"Executing training run {payload.run_id}")
	with ctx.session_factory() as session:
		run_repo = SqliteTrainingRunRepository(session)
		existing_run = run_repo.get_by_id(payload.run_id)
		if existing_run and existing_run.status == TrainingRunStatus.PENDING:
			existing_run.status = TrainingRunStatus.RUNNING
			existing_run.started_at = datetime.now(timezone.utc)
			run_repo.save(existing_run)
			session.commit()

		service = TrainingOrchestrationService(
			dispatcher=None,  # type: ignore[arg-type]  # worker never dispatches
			training_run_repo=run_repo,
			model_version_repo=SqliteModelVersionRepository(session),
			model_repo=SqliteModelRepository(session),
			dataset_artifact_repo=SqliteDatasetArtifactRepository(session),
			file_storage=ctx.storage,
		)
		executor = TrainingRunExecutor(
			file_storage=ctx.storage,
			notifier=CallbackResultNotifier(callback=service.handle_training_completion),
		)
		try:
			executor.run(payload)
			session.commit()
		except Exception as e:
			session.rollback()
			failed_run = run_repo.get_by_id(payload.run_id)
			if failed_run and failed_run.status in (TrainingRunStatus.PENDING, TrainingRunStatus.RUNNING):
				failed_run.status = TrainingRunStatus.FAILED
				failed_run.error_message = str(e)
				failed_run.completed_at = datetime.now(timezone.utc)
				run_repo.save(failed_run)
				session.commit()
			raise


def handle_batch_inference(ctx: WorkerContext, data: Dict[str, Any]) -> None:
	"""Execute a batch detection job and persist the result (DetectionJob status + summary)."""
	payload = BatchInferencePayload.model_validate(data)
	logger.info(f"Executing batch inference job {payload.job_id}")
	with ctx.session_factory() as session:
		job_repo = SqliteDetectionJobRepository(session)
		existing_job = job_repo.get_by_id(payload.job_id)
		if existing_job and existing_job.status == DetectionJobStatus.PENDING:
			existing_job.status = DetectionJobStatus.RUNNING
			existing_job.started_at = datetime.now(timezone.utc)
			job_repo.save(existing_job)
			session.commit()

		service = InferenceService(
			file_storage=ctx.storage,
			detection_job_repo=job_repo,
			project_repo=SqliteProjectRepository(session),
			dataset_repo=SqliteDatasetRepository(session),
			artifact_repo=SqliteDatasetArtifactRepository(session),
			model_repo=SqliteModelRepository(session),
			model_version_repo=SqliteModelVersionRepository(session),
			training_run_repo=SqliteTrainingRunRepository(session),
			rule_manager=RuleManager(
				rule_repo=SqliteRuleRepository(session),
				version_repo=SqliteRuleVersionRepository(session),
				project_repo=SqliteProjectRepository(session),
			),
			case_repo=SqliteCaseRepository(session),
		)
		executor = BatchInferenceExecutor(
			file_storage=ctx.storage,
			notifier=service.handle_job_completion,
		)
		try:
			executor.run(payload)
			session.commit()
		except Exception as e:
			session.rollback()
			failed_job = job_repo.get_by_id(payload.job_id)
			if failed_job and failed_job.status in (DetectionJobStatus.PENDING, DetectionJobStatus.RUNNING):
				failed_job.status = DetectionJobStatus.FAILED
				failed_job.error_message = str(e)
				failed_job.completed_at = datetime.now(timezone.utc)
				job_repo.save(failed_job)
				session.commit()
			raise


def handle_dataset_ingestion(ctx: WorkerContext, data: Dict[str, Any]) -> Dict[str, Any]:
	"""Execute dataset ingestion and profiling on the worker."""
	logger.info(f"Executing dataset ingestion for '{data.get('dataset_name')}'")
	classification: Optional[DataClassification] = None
	raw_cls = data.get("data_classification")
	if raw_cls:
		try:
			classification = DataClassification(raw_cls)
		except ValueError:
			classification = DataClassification.INTERNAL

	project_id = UUID(str(data["project_id"])) if data.get("project_id") else None
	user_id = UUID(str(data["user_id"])) if data.get("user_id") else None

	with ctx.session_factory() as session:
		service = _build_data_management_service(session, ctx.storage)
		dataset, artifact = service.import_dataset(
			file_path=str(data["file_path"]),
			dataset_name=str(data["dataset_name"]),
			display_name=data.get("display_name"),
			description=data.get("description"),
			project_id=project_id,
			user_id=user_id,
			contains_pii=bool(data.get("contains_pii", False)),
			data_classification=classification,
		)
		session.commit()
		return {
			"dataset_id": str(dataset.dataset_id),
			"artifact_id": str(artifact.artifact_id),
		}


def handle_schema_mapping(ctx: WorkerContext, data: Dict[str, Any]) -> Dict[str, Any]:
	"""Execute schema mapping and quality validation on the worker."""
	dataset_id = UUID(str(data["dataset_id"]))
	mapping_config = DataMappingConfig.model_validate(data["mapping_config"])
	user_name = str(data.get("user_name", "system"))
	logger.info(f"Executing schema mapping for dataset {dataset_id}")
	with ctx.session_factory() as session:
		service = _build_data_management_service(session, ctx.storage)
		artifact = service.map_schema(
			dataset_id=dataset_id,
			mapping_config=mapping_config,
			user_name=user_name,
		)
		session.commit()
		return {
			"dataset_id": str(dataset_id),
			"artifact_id": str(artifact.artifact_id),
		}


def handle_feature_engineering(ctx: WorkerContext, data: Dict[str, Any]) -> Dict[str, Any]:
	"""Execute feature engineering, train/test splitting, and balancing on the worker."""
	dataset_id = UUID(str(data["dataset_id"]))
	config = FeatureEngineeringConfig.model_validate(data["config"])
	user_name = str(data.get("user_name", "system"))
	logger.info(f"Executing feature engineering for dataset {dataset_id}")
	with ctx.session_factory() as session:
		service = _build_data_management_service(session, ctx.storage)
		artifact = service.execute_feature_engineering(
			dataset_id=dataset_id,
			config=config,
			user_name=user_name,
		)
		session.commit()
		return {
			"dataset_id": str(dataset_id),
			"artifact_id": str(artifact.artifact_id),
		}


def handle_plugin_dry_run(ctx: WorkerContext, data: Dict[str, Any]) -> Dict[str, Any]:
	"""Validate (AST + subprocess dry-run) and register a custom model plugin on the worker."""
	logger.info("Executing model plugin validation and dry-run")
	zip_bytes: Optional[bytes] = None
	if data.get("zip_base64"):
		b64_str = str(data["zip_base64"]).strip()
		if "," in b64_str and b64_str.startswith("data:"):
			b64_str = b64_str.split(",", 1)[1]
		zip_bytes = base64.b64decode(b64_str)

	project_id = UUID(str(data["project_id"])) if data.get("project_id") else None
	manifest_override: Optional[ModelPluginManifest] = None
	if data.get("manifest_override"):
		manifest_override = ModelPluginManifest.model_validate(data["manifest_override"])

	with ctx.session_factory() as session:
		model_repo = SqliteModelRepository(session)
		plugin_registry = ModelPluginRegistrationService(
			model_repo=model_repo,
			file_storage=ctx.storage,
		)
		service = TrainingOrchestrationService(
			dispatcher=None,  # type: ignore[arg-type]
			training_run_repo=SqliteTrainingRunRepository(session),
			model_version_repo=SqliteModelVersionRepository(session),
			model_repo=model_repo,
			dataset_artifact_repo=SqliteDatasetArtifactRepository(session),
			file_storage=ctx.storage,
			plugin_registry=plugin_registry,
		)
		model = service.register_plugged_model(
			model_artifact_path=data.get("model_artifact_path"),
			user_id=str(data.get("user_id") or "mock_user"),
			project_id=project_id,
			manifest_override=manifest_override,
			zip_bytes=zip_bytes,
		)
		session.commit()
		return {"model_id": str(model.model_id)}


def handle_rule_backtest(ctx: WorkerContext, data: Dict[str, Any]) -> Dict[str, Any]:
	"""Execute historical dataset backtest of a rule or ad-hoc JsonLogic condition on the worker."""
	artifact_id = UUID(str(data["dataset_artifact_id"]))
	logger.info(f"Executing rule backtest on artifact {artifact_id}")
	with ctx.session_factory() as session:
		artifact_repo = SqliteDatasetArtifactRepository(session)
		artifact = artifact_repo.get_by_id(artifact_id)
		if not artifact:
			raise LookupError(f"DatasetArtifact '{artifact_id}' not found")

		output_paths = artifact.output_paths or {}
		dfs: List[pd.DataFrame] = []
		if output_paths.get("train") and output_paths.get("test"):
			dfs.append(_load_artifact_dataframe(output_paths["train"], ctx.storage))
			dfs.append(_load_artifact_dataframe(output_paths["test"], ctx.storage))
		else:
			primary_path = (
				output_paths.get("mapped")
				or output_paths.get("raw")
				or output_paths.get("train")
				or artifact.storage_path
			)
			dfs.append(_load_artifact_dataframe(primary_path, ctx.storage))

		df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]

		raw_action = data.get("action") or RuleAction.REVIEW.value
		action = RuleAction(raw_action) if not isinstance(raw_action, RuleAction) else raw_action

		executor = RuleExecutor()
		bt_result = executor.backtest_dataframe(
			df=df,
			condition=data["condition"],
			action=action,
			dataset_artifact_id=str(artifact_id),
			rule_id=data.get("rule_id"),
			rule_version_id=data.get("rule_version_id"),
			version_number=int(data.get("version_number", 1)),
			rule_code=str(data.get("rule_code", "AD_HOC")),
			rule_name=str(data.get("rule_name", "Ad-hoc Rule")),
			target_column=data.get("target_column"),
			amount_column=data.get("amount_column"),
			max_samples=int(data.get("max_samples", 50)),
		)
		res_dict = asdict(bt_result)
		res_dict["action"] = str(bt_result.action.value if hasattr(bt_result.action, "value") else bt_result.action)
		return res_dict
