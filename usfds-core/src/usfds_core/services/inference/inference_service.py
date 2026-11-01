"""USFDS Inference Service for Online and Batch Fraud Detection Inference.
Orchestrates online real-time scoring and dispatches batch inference jobs.
Supports both Built-in models and custom Plugin Model Bundles (model_bundle.zip).
"""

from datetime import datetime, timezone
import io
import json
import logging
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4
import joblib
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.detection import DetectionJob, Pipeline
from usfds_core.domain.entities.enums import (
    DeploymentStatus,
    DetectionJobStatus,
    InvestigationStatus,
    ModelVersionStatus,
    PipelineStage,
    ProjectStatus,
    RiskLevel,
)
from usfds_core.domain.entities.investigation import InvestigationCase
from usfds_core.domain.schemas.inference_payload import (
    ActiveRuleSnapshot,
    BatchInferencePayload,
    BatchInferenceResult,
)
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_dataset_repo import IDatasetRepository
from usfds_core.repositories.base_detection_job_repo import IDetectionJobRepository
from usfds_core.repositories.base_investigation_repo import IInvestigationRepository
from usfds_core.repositories.base_model_repo import IModelRepository
from usfds_core.repositories.base_model_version_repo import IModelVersionRepository
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository
from usfds_core.repositories.pipeline_repo import IPipelineRepository
from usfds_core.services.inference.dispatchers.base_dispatcher import IBatchInferenceDispatcher
from usfds_core.services.inference.executor import (
    BatchInferenceExecutor,
    apply_domain_feature_engineers,
    execute_plugin_bundle_inference,
    prepare_and_validate_input,
    run_feature_transformations,
)
from usfds_core.services.inference.scoring_service import ModelScorer
from usfds_core.services.inference.workspace import InferenceWorkspace
from usfds_core.services.project_management.schema_validator import ProjectSchemaValidator
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_core.storage.base_storage import IFileStorage

logger = logging.getLogger(__name__)


class InferenceService:
    """Service orchestrating ML & Hybrid inference workflows:
    - Online Inference: Low-latency real-time single-event scoring.
    - Batch Inference: Pre-dispatch job registration -> Payload dispatch -> Post-execution record update.
    - Hybrid Detection Jobs (SUC-15, SUC-16, SUC-19): Combines APPROVED ModelVersion + ACTIVE Rules.
    """

    def __init__(
        self,
        pipeline_repo: Optional[IPipelineRepository] = None,
        file_storage: Optional[IFileStorage] = None,
        detection_job_repo: Optional[IDetectionJobRepository] = None,
        dispatcher: Optional[IBatchInferenceDispatcher] = None,
        project_repo: Optional[IProjectRepository] = None,
        dataset_repo: Optional[IDatasetRepository] = None,
        artifact_repo: Optional[IDatasetArtifactRepository] = None,
        model_repo: Optional[IModelRepository] = None,
        model_version_repo: Optional[IModelVersionRepository] = None,
        training_run_repo: Optional[ITrainingRunRepository] = None,
        rule_manager: Optional[RuleManager] = None,
        investigation_repo: Optional[IInvestigationRepository] = None,
    ):
        self.pipeline_repo = pipeline_repo
        self.file_storage = file_storage
        self.detection_job_repo = detection_job_repo
        self.dispatcher = dispatcher
        self.project_repo = project_repo
        self.dataset_repo = dataset_repo
        self.artifact_repo = artifact_repo
        self.model_repo = model_repo
        self.model_version_repo = model_version_repo
        self.training_run_repo = training_run_repo
        self.rule_manager = rule_manager
        self.investigation_repo = investigation_repo
        self.schema_validator = ProjectSchemaValidator()

    def _read_bytes(self, file_path_or_storage: Union[str, Path]) -> bytes:
        """Reads file bytes directly from local filesystem or through IFileStorage."""
        path_str = str(file_path_or_storage)
        p = Path(path_str)
        if p.is_file():
            return p.read_bytes()
        return self.file_storage.read_bytes(path_str)

    def _validate_deployment(self, deployment_id: UUID) -> Pipeline:
        """Retrieves and validates the deployment and its pipeline lineage."""
        pipeline = self.pipeline_repo.get_by_deployment_id(deployment_id)
        if not pipeline:
            raise ValueError(f"No pipeline found for deployment_id: '{deployment_id}'")

        if pipeline.deployment and hasattr(pipeline.deployment, "status"):
            status = pipeline.deployment.status
            if status != DeploymentStatus.RUNNING:
                raise ValueError(
                    f"Deployment '{deployment_id}' is not RUNNING (current status: '{status}')."
                )

        return pipeline

    def _load_pipeline_artifacts(
        self,
        workspace: InferenceWorkspace,
        pipeline: Pipeline,
    ) -> Tuple[Optional[Any], Optional[Any], Any]:
        """Downloads and deserializes required pipeline artifacts into the workspace."""
        # 1. Feature Engineering transformers (.joblib), optional if input is already FEATURE_ENGINEERED
        fitted_engineers = None
        if (
            pipeline.feature_engineered_dataset_artifact
            and pipeline.feature_engineered_dataset_artifact.output_paths
        ):
            fe_path = pipeline.feature_engineered_dataset_artifact.output_paths.get("fitted_engineers")
            if fe_path:
                fe_bytes = self._read_bytes(fe_path)
                with open(workspace.fitted_engineers_path, "wb") as f:
                    f.write(fe_bytes)
                fitted_engineers = joblib.load(workspace.fitted_engineers_path)

        # 2. Preprocessing pipeline (.joblib), optional when model bundles its own preprocessor
        preprocessing_pipeline = None
        if (
            pipeline.preprocessed_dataset_artifact
            and pipeline.preprocessed_dataset_artifact.output_paths
        ):
            prep_path = pipeline.preprocessed_dataset_artifact.output_paths.get("pipeline")
            if prep_path:
                prep_bytes = self._read_bytes(prep_path)
                with open(workspace.fitted_pipeline_path, "wb") as f:
                    f.write(prep_bytes)
                preprocessing_pipeline = joblib.load(workspace.fitted_pipeline_path)

        # 3. Model weights or Plugin Bundle (.joblib or .zip)
        if not pipeline.model_version or not pipeline.model_version.artifact_uri:
            raise FileNotFoundError("Missing artifact_uri in pipeline.model_version")
        model_uri = pipeline.model_version.artifact_uri
        model_bytes = self._read_bytes(model_uri)

        if model_uri.lower().endswith(".zip"):
            return fitted_engineers, preprocessing_pipeline, model_bytes

        with open(workspace.model_path, "wb") as f:
            f.write(model_bytes)
        model = joblib.load(workspace.model_path)

        if preprocessing_pipeline is None:
            companion_uri = str(Path(model_uri).parent / "preprocessor.joblib").replace("\\", "/")
            try:
                prep_bytes = self._read_bytes(companion_uri)
                with open(workspace.fitted_pipeline_path, "wb") as f:
                    f.write(prep_bytes)
                preprocessing_pipeline = joblib.load(workspace.fitted_pipeline_path)
            except Exception:
                pass

        return fitted_engineers, preprocessing_pipeline, model

    def online_inference(
        self,
        deployment_id: UUID,
        event: dict,
    ) -> dict:
        """Executes low-latency real-time fraud scoring on a single transaction event."""
        start_time = time.time()
        pipeline = self._validate_deployment(deployment_id)

        workspace = InferenceWorkspace(deployment_id=deployment_id)
        workspace.initialize()

        try:
            # 1. Download & load pipeline artifacts
            fitted_engineers, preprocessing_pipeline, model_or_bundle = self._load_pipeline_artifacts(
                workspace, pipeline
            )

            # 2. Extract column mapping
            column_mapping = {}
            if (
                pipeline.mapped_dataset_artifact
                and pipeline.mapped_dataset_artifact.validation_report
            ):
                column_mapping = pipeline.mapped_dataset_artifact.validation_report.get(
                    "column_mapping", {}
                )

            # 3. Dual-Schema validate and prepare input
            event_df = pd.DataFrame([event])
            prepared_df = prepare_and_validate_input(event_df, column_mapping)

            threshold = 0.5
            if pipeline.model_version and hasattr(pipeline.model_version, "decision_threshold"):
                threshold = getattr(pipeline.model_version, "decision_threshold", 0.5) or 0.5

            # 4. Score using Plugin Bundle or Built-in Model
            if isinstance(model_or_bundle, bytes):
                fe_df = apply_domain_feature_engineers(prepared_df, fitted_engineers)
                preds, fraud_probs = execute_plugin_bundle_inference(
                    feature_engineered_df=fe_df,
                    bundle_bytes=model_or_bundle,
                    workspace=workspace,
                    threshold=threshold,
                )
            else:
                X = run_feature_transformations(
                    prepared_df, fitted_engineers, preprocessing_pipeline, model_or_bundle
                )
                preds, fraud_probs = ModelScorer.predict_with_probabilities(
                    model_or_bundle, X, threshold=threshold
                )

            pred = int(preds[0])
            fraud_prob = float(fraud_probs[0])
            latency_ms = round((time.time() - start_time) * 1000, 2)

            return {
                "prediction": pred,
                "probability": round(fraud_prob, 6),
                "is_fraud": bool(pred == 1),
                "risk_score": round(fraud_prob * 100, 2),
                "deployment_id": str(deployment_id),
                "model_version_id": str(pipeline.model_version.version_id) if pipeline.model_version else None,
                "latency_ms": latency_ms,
            }
        finally:
            workspace.cleanup()

    def batch_inference(
        self,
        project_id: UUID,
        deployment_id: UUID,
        input_path: str,
        job_name: Optional[str] = None,
        user_name: Optional[str] = None,
        decision_threshold: Optional[float] = None,
    ) -> DetectionJob:
        """Pre-dispatch phase for batch inference."""
        pipeline = self._validate_deployment(deployment_id)

        # 1. Extract pipeline artifact paths
        fe_path = None
        if (
            pipeline.feature_engineered_dataset_artifact
            and pipeline.feature_engineered_dataset_artifact.output_paths
        ):
            fe_path = pipeline.feature_engineered_dataset_artifact.output_paths.get("fitted_engineers")

        prep_path = None
        if (
            pipeline.preprocessed_dataset_artifact
            and pipeline.preprocessed_dataset_artifact.output_paths
        ):
            prep_path = pipeline.preprocessed_dataset_artifact.output_paths.get("pipeline")

        model_uri = pipeline.model_version.artifact_uri if pipeline.model_version else None
        if not model_uri:
            raise FileNotFoundError("Missing model_version.artifact_uri in the pipeline lineage.")

        # 2. Extract column mapping
        column_mapping = {}
        if (
            pipeline.mapped_dataset_artifact
            and pipeline.mapped_dataset_artifact.validation_report
        ):
            column_mapping = pipeline.mapped_dataset_artifact.validation_report.get(
                "column_mapping", {}
            )

        # 3. Create and persist DetectionJob (PENDING)
        job_id = uuid4()
        output_storage_path = (
            f"datasets/{project_id}/inferences/{deployment_id}/{job_id}/predictions.parquet"
        )

        job = DetectionJob(
            job_id=job_id,
            project_id=project_id,
            deployment_id=deployment_id,
            input_path=input_path,
            job_name=job_name or f"Batch-Detection-{deployment_id}",
            output_path=output_storage_path,
            status=DetectionJobStatus.PENDING,
            created_by=user_name or "system",
        )

        if self.detection_job_repo:
            self.detection_job_repo.save(job)

        # 4. Resolve decision threshold from ModelVersion or ad-hoc parameter
        effective_threshold = decision_threshold
        if effective_threshold is None:
            if pipeline.model_version and hasattr(pipeline.model_version, "decision_threshold"):
                effective_threshold = getattr(pipeline.model_version, "decision_threshold", 0.5) or 0.5
            else:
                effective_threshold = 0.5

        # 5. Assemble BatchInferencePayload
        payload = BatchInferencePayload(
            job_id=job.job_id,
            project_id=project_id,
            deployment_id=deployment_id,
            input_path=input_path,
            output_storage_path=output_storage_path,
            fe_artifact_path=fe_path,
            prep_artifact_path=prep_path,
            model_artifact_uri=model_uri,
            decision_threshold=effective_threshold,
            column_mapping=column_mapping,
        )

        # 6. Update status to RUNNING
        job.status = DetectionJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        if self.detection_job_repo:
            self.detection_job_repo.save(job)

        # 7. Dispatch payload to background compute engine or executor
        if self.dispatcher:
            logger.info(f"Dispatching batch detection job {job.job_id} via {type(self.dispatcher).__name__}...")
            self.dispatcher.dispatch_batch(payload)
        else:
            logger.info(f"No dispatcher configured; executing batch detection job {job.job_id} synchronously...")
            executor = BatchInferenceExecutor(
                file_storage=self.file_storage,
                notifier=self.handle_job_completion,
            )
            executor.run(payload)

        return job

    def handle_job_completion(self, result: BatchInferenceResult) -> DetectionJob:
        """Post-execution handler for batch detection job results."""
        job: Optional[DetectionJob] = None
        if self.detection_job_repo:
            job = self.detection_job_repo.get_by_id(result.job_id)

        if not job:
            logger.warning(f"DetectionJob {result.job_id} not found in repository.")
            job = DetectionJob(
                job_id=result.job_id,
                project_id=uuid4(),
                deployment_id=uuid4(),
                input_path="",
            )

        job.completed_at = datetime.now(timezone.utc)
        job.execution_time_seconds = result.duration_seconds

        if result.is_success:
            job.status = DetectionJobStatus.COMPLETED
            job.output_path = result.output_path
            job.total_records = result.total_records
            job.fraud_records = result.fraud_records
            job.fraud_rate = result.fraud_rate
            if result.summary_metrics is not None:
                existing_meta = job.summary_metrics or {}
                job.summary_metrics = {**existing_meta, **result.summary_metrics}
            logger.info(
                f"DetectionJob {job.job_id} succeeded: "
                f"total={result.total_records}, fraud={result.fraud_records}, rate={result.fraud_rate}"
            )
        else:
            job.status = DetectionJobStatus.FAILED
            job.error_message = result.error_message
            logger.error(f"DetectionJob {job.job_id} failed: {result.error_message}")

        if self.detection_job_repo:
            self.detection_job_repo.save(job)

        return job

    def _trace_model_version_lineage(
        self,
        model_version_id: UUID,
        project_id: Optional[UUID] = None,
    ) -> Tuple[Optional[str], Optional[str], Dict[str, str], Dict[str, Any]]:
        """Traces back from ModelVersion -> TrainingRun -> RunDataset -> DatasetArtifact lineage
        to resolve (fe_artifact_path, prep_artifact_path, column_mapping, model_metadata).
        """
        if not self.model_version_repo:
            raise ValueError("ModelVersionRepository is not configured on InferenceService.")

        version = self.model_version_repo.get_by_id(model_version_id)
        if not version:
            raise ValueError(f"ModelVersion with ID '{model_version_id}' not found.")

        status_str = (
            version.status.value
            if hasattr(version.status, "value")
            else str(version.status)
        )
        if status_str != ModelVersionStatus.APPROVED.value:
            raise ValueError(
                f"ModelVersion '{version.semver}' ({model_version_id}) is not APPROVED (current status: {status_str})."
            )

        if project_id and version.project_id and str(version.project_id) != str(project_id):
            raise ValueError(
                "Selected ModelVersion does not belong to the specified project (BR-PM-06)."
            )

        model_name = "Model"
        display_name = "Model"
        if self.model_repo:
            model = self.model_repo.get_by_id(version.model_id)
            if model:
                model_name = model.model_name
                display_name = model.display_name or model.model_name

        fe_path: Optional[str] = None
        prep_path: Optional[str] = None
        column_mapping: Dict[str, str] = {}

        # 1. Check companion files bundled directly inside the model version's run folder first
        if version.artifact_uri and self.file_storage:
            run_dir_str = str(Path(version.artifact_uri).parent).replace("\\", "/")
            cand_fe_uri = f"{run_dir_str}/fitted_feature_engineers.joblib"
            if self.file_storage.exists(cand_fe_uri):
                fe_path = cand_fe_uri

            cand_prep_uri = f"{run_dir_str}/preprocessor.joblib"
            if self.file_storage.exists(cand_prep_uri):
                prep_path = cand_prep_uri

            cand_cm_uri = f"{run_dir_str}/column_mapping.json"
            if self.file_storage.exists(cand_cm_uri):
                try:
                    cm_raw = json.loads(self.file_storage.read_bytes(cand_cm_uri).decode("utf-8"))
                    if isinstance(cm_raw, dict):
                        column_mapping = {str(k): str(v) for k, v in cm_raw.items() if v}
                except Exception:
                    pass

        # 2. Trace back via TrainingRun -> RunDataset -> DatasetArtifact lineage
        if version.run_id and self.training_run_repo and self.artifact_repo:
            linked = self.training_run_repo.get_linked_datasets(version.run_id)
            if linked:
                curr_artifact: Optional[DatasetArtifact] = self.artifact_repo.get_by_id(
                    linked[0].dataset_artifact_id
                )
                visited = set()
                while curr_artifact is not None and curr_artifact.artifact_id not in visited:
                    visited.add(curr_artifact.artifact_id)
                    stage_str = (
                        curr_artifact.pipeline_stage.value
                        if hasattr(curr_artifact.pipeline_stage, "value")
                        else str(curr_artifact.pipeline_stage)
                    )
                    out_paths = curr_artifact.output_paths or {}
                    val_rep = curr_artifact.validation_report or {}

                    if stage_str == PipelineStage.PRE_PROCESSED.value and not prep_path:
                        cand_prep = out_paths.get("pipeline")
                        if cand_prep and (not self.file_storage or self.file_storage.exists(cand_prep)):
                            prep_path = cand_prep
                    elif stage_str == PipelineStage.FEATURE_ENGINEERED.value and not fe_path:
                        cand_fe = out_paths.get("fitted_engineers") or (
                            f"{curr_artifact.storage_path}/fitted_feature_engineers.joblib"
                            if curr_artifact.storage_path
                            else None
                        )
                        if cand_fe and (not self.file_storage or self.file_storage.exists(cand_fe)):
                            fe_path = cand_fe

                    if not column_mapping and isinstance(val_rep, dict):
                        cm = val_rep.get("column_mapping") or val_rep.get("mapping_config")
                        if isinstance(cm, dict) and cm:
                            column_mapping = {str(k): str(v) for k, v in cm.items() if v}

                    if curr_artifact.parent_artifact_id:
                        curr_artifact = self.artifact_repo.get_by_id(curr_artifact.parent_artifact_id)
                    else:
                        break

        meta = {
            "model_id": str(version.model_id),
            "model_version_id": str(version.version_id),
            "model_name": model_name,
            "model_display_name": display_name,
            "semver": version.semver,
            "artifact_uri": version.artifact_uri,
            "default_threshold": version.decision_threshold,
        }
        return fe_path, prep_path, column_mapping, meta

    def _resolve_input_source(
        self,
        project_id: UUID,
        job_id: UUID,
        target_artifact_id: Optional[UUID] = None,
        input_file_path: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Validates and resolves the input data source for a DetectionJob (SUC-15):
        - Option 1: target_artifact_id (MUST be at PipelineStage.RAW).
        - Option 2: input_file_path (local/storage file path validated against project.raw_schema).
        Returns (resolved_storage_or_file_path, source_meta).
        """
        if not target_artifact_id and (not input_file_path or not input_file_path.strip()):
            raise ValueError(
                "Either 'target_artifact_id' (RAW stage) or 'input_file_path' must be provided to start a detection job."
            )

        if target_artifact_id and input_file_path and input_file_path.strip():
            raise ValueError(
                "Provide either 'target_artifact_id' or 'input_file_path', not both."
            )

        project = self.project_repo.get_by_id(project_id) if self.project_repo else None
        if project:
            proj_status = (
                project.status.value
                if hasattr(project.status, "value")
                else str(project.status)
            )
            if proj_status == ProjectStatus.ARCHIVED.value:
                raise ValueError("Cannot start a detection job in an ARCHIVED project.")

        # Option 1: Existing DatasetArtifact (must be RAW)
        if target_artifact_id:
            if not self.artifact_repo:
                raise ValueError("DatasetArtifactRepository is not configured.")
            artifact = self.artifact_repo.get_by_id(target_artifact_id)
            if not artifact:
                raise ValueError(f"DatasetArtifact '{target_artifact_id}' not found.")

            dataset_name = "Dataset"
            if self.dataset_repo:
                ds = self.dataset_repo.get_by_id(artifact.dataset_id)
                if ds:
                    if str(ds.project_id) != str(project_id):
                        raise ValueError(
                            "Target DatasetArtifact does not belong to the specified project (BR-PM-06)."
                        )
                    dataset_name = ds.display_name or ds.dataset_name

            stage_str = (
                artifact.pipeline_stage.value
                if hasattr(artifact.pipeline_stage, "value")
                else str(artifact.pipeline_stage)
            )
            if stage_str != PipelineStage.RAW.value:
                raise ValueError(
                    f"Target DatasetArtifact must be at stage 'RAW', but received '{stage_str}'."
                )

            out_paths = artifact.output_paths or {}
            resolved_path = out_paths.get("raw") or artifact.storage_path
            if not resolved_path:
                raise ValueError("Selected RAW DatasetArtifact does not have a valid storage path.")

            return resolved_path, {
                "input_source_type": "ARTIFACT",
                "target_artifact_id": str(artifact.artifact_id),
                "dataset_id": str(artifact.dataset_id),
                "dataset_name": dataset_name,
                "input_label": f"{dataset_name} (RAW)",
            }

        # Option 2: Direct file path (`input_file_path`)
        assert input_file_path is not None
        clean_path_str = input_file_path.strip()
        allowed_exts = {".csv", ".parquet", ".pq", ".json"}
        ext = Path(clean_path_str).suffix.lower()
        if ext not in allowed_exts:
            raise ValueError(
                f"Unsupported file format '{ext}'. Supported formats: .csv, .parquet, .pq, .json."
            )

        raw_bytes: Optional[bytes] = None
        local_p = Path(clean_path_str)
        if local_p.is_file():
            raw_bytes = local_p.read_bytes()
        elif self.file_storage and self.file_storage.exists(clean_path_str):
            raw_bytes = self.file_storage.read_bytes(clean_path_str)
        else:
            raise FileNotFoundError(f"Input file not found at '{clean_path_str}'.")

        if not raw_bytes:
            raise ValueError(f"Input file '{clean_path_str}' is empty (0 bytes).")

        buffer = io.BytesIO(raw_bytes)
        try:
            if ext in (".parquet", ".pq"):
                df = pd.read_parquet(buffer)
            elif ext == ".json":
                df = pd.read_json(buffer)
            else:
                df = pd.read_csv(buffer)
        except Exception as err:
            raise ValueError(f"Failed to parse input file '{clean_path_str}': {err}") from err

        if df.empty or len(df.columns) == 0:
            raise ValueError(f"Input file '{clean_path_str}' contains no records or columns.")

        # Validate against project.raw_schema if locked (allow missing label/target column)
        if project and project.is_schema_locked and project.raw_schema:
            val_res = self.schema_validator.validate_dataframe(
                df, project.raw_schema, allow_missing_target=True
            )
            if not val_res.is_valid:
                raise ValueError(" ".join(val_res.errors))

        # Persist input snapshot into storage for reproducible auditability
        filename = local_p.name or f"batch_input{ext}"
        stored_input_path = f"datasets/{project_id}/inferences/inputs/{job_id}/{filename}"
        if self.file_storage:
            self.file_storage.save_bytes(stored_input_path, raw_bytes)
        else:
            stored_input_path = clean_path_str

        return stored_input_path, {
            "input_source_type": "FILE",
            "input_file_name": filename,
            "original_file_path": clean_path_str,
            "input_label": filename,
        }

    def start_detection_job(
        self,
        project_id: UUID,
        target_artifact_id: Optional[UUID] = None,
        input_file_path: Optional[str] = None,
        model_version_id: Optional[UUID] = None,
        use_rules: bool = True,
        score_threshold: Optional[float] = None,
        job_name: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> DetectionJob:
        """Starts a hybrid batch detection job (SUC-15) combining an optional APPROVED ModelVersion
        and the project's ACTIVE business rules on either a RAW DatasetArtifact or a direct file path.
        """
        job_id = uuid4()

        # 1. Resolve and validate input source (RAW artifact or direct file path)
        resolved_input_path, input_meta = self._resolve_input_source(
            project_id=project_id,
            job_id=job_id,
            target_artifact_id=target_artifact_id,
            input_file_path=input_file_path,
        )

        # 2. Resolve optional AI ModelVersion & lineage artifacts
        fe_path: Optional[str] = None
        prep_path: Optional[str] = None
        column_mapping: Dict[str, str] = {}
        model_uri: Optional[str] = None
        model_meta: Dict[str, Any] = {}
        effective_threshold = score_threshold if score_threshold is not None else 0.5

        if model_version_id is not None:
            fe_path, prep_path, column_mapping, model_meta = self._trace_model_version_lineage(
                model_version_id=model_version_id,
                project_id=project_id,
            )
            model_uri = model_meta.get("artifact_uri")
            if score_threshold is None:
                effective_threshold = float(model_meta.get("default_threshold") or 0.5)

        if not (0.0 < effective_threshold < 1.0):
            raise ValueError("score_threshold must be strictly between 0.0 and 1.0.")

        # 3. Resolve ACTIVE project rules
        active_snapshots: List[ActiveRuleSnapshot] = []
        if use_rules and self.rule_manager:
            active_pairs = self.rule_manager.get_active_rules_with_versions(project_id)
            for rule, ver in active_pairs:
                act_str = ver.action.value if hasattr(ver.action, "value") else str(ver.action)
                active_snapshots.append(
                    ActiveRuleSnapshot(
                        rule_id=str(rule.rule_id),
                        rule_version_id=str(ver.rule_version_id),
                        version_number=ver.version_number,
                        rule_code=rule.rule_code,
                        rule_name=rule.name,
                        action=act_str,
                        condition=ver.condition or {},
                    )
                )

        if model_version_id is None and len(active_snapshots) == 0:
            raise ValueError(
                "Cannot start a Rule-Only detection job when the project has no ACTIVE business rules."
            )

        # 4. Initialize and persist DetectionJob
        engine_tag = str(model_version_id) if model_version_id else "rule-only"
        output_storage_path = (
            f"datasets/{project_id}/inferences/{engine_tag}/{job_id}/predictions.parquet"
        )
        resolved_job_name = (
            job_name.strip()
            if job_name and job_name.strip()
            else f"detection-{int(datetime.now(timezone.utc).timestamp())}"
        )

        initial_meta: Dict[str, Any] = {
            **input_meta,
            **model_meta,
            "use_rules": use_rules,
            "active_rules_count": len(active_snapshots),
            "score_threshold": round(effective_threshold, 4),
        }

        job = DetectionJob(
            job_id=job_id,
            project_id=project_id,
            deployment_id=model_version_id,
            target_artifact_id=target_artifact_id,
            model_version_id=model_version_id,
            score_threshold=round(effective_threshold, 4),
            use_rules=use_rules,
            input_path=resolved_input_path,
            job_name=resolved_job_name,
            output_path=output_storage_path,
            status=DetectionJobStatus.PENDING,
            summary_metrics=initial_meta,
            created_by=user_name or "system",
        )

        if self.detection_job_repo:
            self.detection_job_repo.save(job)

        payload = BatchInferencePayload(
            job_id=job.job_id,
            project_id=project_id,
            deployment_id=model_version_id,
            model_version_id=model_version_id,
            input_path=resolved_input_path,
            output_storage_path=output_storage_path,
            fe_artifact_path=fe_path,
            prep_artifact_path=prep_path,
            model_artifact_uri=model_uri,
            decision_threshold=effective_threshold,
            column_mapping=column_mapping,
            use_rules=use_rules,
            active_rules=active_snapshots,
        )

        job.status = DetectionJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        if self.detection_job_repo:
            self.detection_job_repo.save(job)

        if self.dispatcher:
            self.dispatcher.dispatch_batch(payload)
        else:
            executor = BatchInferenceExecutor(
                file_storage=self.file_storage,
                notifier=self.handle_job_completion,
            )
            executor.run(payload)

        if self.detection_job_repo:
            updated = self.detection_job_repo.get_by_id(job.job_id)
            if updated:
                return updated
        return job

    def list_detection_jobs(
        self,
        project_id: UUID,
        status: Optional[str] = None,
    ) -> List[DetectionJob]:
        """Lists all detection jobs for a project (SUC-19), sorted by newest first."""
        if not self.detection_job_repo:
            return []
        jobs = self.detection_job_repo.list_by_project(project_id)
        if status:
            target_st = status.strip().upper()
            jobs = [
                j for j in jobs
                if (j.status.value if hasattr(j.status, "value") else str(j.status)).upper() == target_st
            ]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def get_detection_job(self, job_id: UUID) -> DetectionJob:
        """Retrieves a DetectionJob by ID or raises ValueError."""
        if not self.detection_job_repo:
            raise ValueError("DetectionJobRepository is not configured.")
        job = self.detection_job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"DetectionJob '{job_id}' not found.")
        return job

    def _load_job_predictions_df(self, job: DetectionJob) -> pd.DataFrame:
        """Loads the scored predictions.parquet DataFrame for a completed DetectionJob."""
        if not job.output_path:
            raise ValueError(f"DetectionJob '{job.job_id}' has no output predictions file.")
        raw_bytes = self._read_bytes(job.output_path)
        return pd.read_parquet(io.BytesIO(raw_bytes))

    def get_detection_job_results(
        self,
        job_id: UUID,
        action_filter: Optional[str] = None,
        rule_code: Optional[str] = None,
        search: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Retrieves summary analytics and filtered transaction results for a DetectionJob (SUC-16)."""
        job = self.get_detection_job(job_id)
        status_str = job.status.value if hasattr(job.status, "value") else str(job.status)
        if status_str != DetectionJobStatus.COMPLETED.value or not job.output_path:
            return {
                "job": job,
                "total_filtered": 0,
                "transactions": [],
                "summary_metrics": job.summary_metrics or {},
            }

        df = self._load_job_predictions_df(job)

        # Resolve canonical display columns
        id_col = next((c for c in ("event_id", "transaction_id", "tx_id", "id") if c in df.columns), None)
        user_col = next((c for c in ("user_id", "account_id", "card_id", "customer_id", "entity_id") if c in df.columns), None)
        ts_col = next((c for c in ("timestamp", "transaction_time", "tx_time", "event_timestamp", "time") if c in df.columns), None)
        amt_col = next((c for c in ("amount", "tx_amount", "transaction_amount", "amt", "Amount") if c in df.columns), None)

        # Map existing investigation cases by event_id for this project
        existing_cases_by_event: Dict[str, str] = {}
        if self.investigation_repo:
            cases = self.investigation_repo.list_cases(project_id=job.project_id, limit=1000)
            for c in cases:
                existing_cases_by_event[str(c.event_id)] = str(c.case_id)
                meta_ev = (c.metadata or {}).get("raw_event_id")
                if meta_ev is not None:
                    existing_cases_by_event[str(meta_ev)] = str(c.case_id)

        internal_cols = {
            "model_score",
            "fraud_probability",
            "triggered_rules",
            "triggered_rule_details",
            "rule_action",
            "final_action",
            "is_flagged",
            "prediction",
        }

        records = df.to_dict(orient="records")
        filtered_rows: List[Dict[str, Any]] = []

        for idx, row in enumerate(records):
            ev_val = row.get(id_col) if id_col and row.get(id_col) is not None else (idx + 1)
            ev_str = str(ev_val)
            user_str = str(row.get(user_col) if user_col and row.get(user_col) is not None else "—")
            ts_str = str(row.get(ts_col) if ts_col and row.get(ts_col) is not None else "—")
            amt_val = 0.0
            if amt_col and row.get(amt_col) is not None:
                try:
                    amt_val = float(row[amt_col])
                    if math.isnan(amt_val):
                        amt_val = 0.0
                except (ValueError, TypeError):
                    amt_val = 0.0

            m_score = float(row.get("model_score", row.get("fraud_probability", 0.0)) or 0.0)
            if math.isnan(m_score):
                m_score = 0.0

            f_action = str(row.get("final_action") or ("REVIEW" if row.get("prediction") == 1 else "ALLOW")).upper()
            r_action = str(row.get("rule_action") or "ALLOW").upper()
            is_flagged = bool(f_action in ("REJECT", "REVIEW"))

            raw_trig = row.get("triggered_rules", "[]")
            if isinstance(raw_trig, str):
                try:
                    trig_codes: List[str] = json.loads(raw_trig)
                except Exception:
                    trig_codes = []
            elif isinstance(raw_trig, list):
                trig_codes = [str(x) for x in raw_trig]
            else:
                trig_codes = []

            raw_details = row.get("triggered_rule_details", "[]")
            if isinstance(raw_details, str):
                try:
                    trig_details: List[Dict[str, Any]] = json.loads(raw_details)
                except Exception:
                    trig_details = []
            elif isinstance(raw_details, list):
                trig_details = raw_details
            else:
                trig_details = []

            # Apply filters
            if action_filter:
                af = action_filter.strip().upper()
                if af == "FLAGGED" and not is_flagged:
                    continue
                elif af in ("REJECT", "REVIEW", "ALLOW") and f_action != af:
                    continue

            if rule_code and rule_code.strip():
                if rule_code.strip() not in trig_codes:
                    continue

            if min_score is not None and m_score < min_score:
                continue
            if max_score is not None and m_score > max_score:
                continue

            if search and search.strip():
                q = search.strip().lower()
                if q not in ev_str.lower() and q not in user_str.lower():
                    continue

            # Extract clean feature snapshot for Evidence Drawer
            features_snapshot: Dict[str, Any] = {}
            for k, v in row.items():
                if k in internal_cols:
                    continue
                if isinstance(v, float) and math.isnan(v):
                    features_snapshot[str(k)] = None
                elif hasattr(v, "item"):
                    features_snapshot[str(k)] = v.item()
                else:
                    features_snapshot[str(k)] = v

            filtered_rows.append(
                {
                    "row_index": idx,
                    "event_id": ev_str,
                    "user_id": user_str,
                    "timestamp": ts_str,
                    "amount": round(amt_val, 2),
                    "model_score": round(m_score, 4),
                    "triggered_rules": trig_codes,
                    "triggered_rule_details": trig_details,
                    "rule_action": r_action,
                    "final_action": f_action,
                    "is_flagged": is_flagged,
                    "case_id": existing_cases_by_event.get(ev_str),
                    "features": features_snapshot,
                }
            )

        # Sort flagged transactions first, then by model_score descending
        action_rank = {"REJECT": 0, "REVIEW": 1, "ALLOW": 2}
        filtered_rows.sort(
            key=lambda r: (action_rank.get(r["final_action"], 3), -r["model_score"], -r["amount"])
        )

        total_filtered = len(filtered_rows)
        paginated = filtered_rows[offset : offset + limit]

        return {
            "job": job,
            "total_filtered": total_filtered,
            "transactions": paginated,
            "summary_metrics": job.summary_metrics or {},
        }

    def export_detection_job_results(
        self,
        job_id: UUID,
        file_format: str = "csv",
        only_flagged: bool = False,
    ) -> Tuple[bytes, str, str]:
        """Exports the DetectionJob results as CSV or Parquet bytes (SUC-16 6a).
        Returns (file_bytes, filename, media_type).
        """
        job = self.get_detection_job(job_id)
        df = self._load_job_predictions_df(job)

        if only_flagged and "is_flagged" in df.columns:
            df = df[df["is_flagged"] == 1]

        fmt = file_format.strip().lower()
        safe_name = (job.job_name or str(job.job_id)).replace(" ", "_")
        if fmt == "parquet":
            buf = io.BytesIO()
            df.to_parquet(buf, index=False)
            return buf.getvalue(), f"{safe_name}_results.parquet", "application/octet-stream"

        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        return buf.getvalue(), f"{safe_name}_results.csv", "text/csv"

    def dispatch_cases_to_investigation(
        self,
        job_id: UUID,
        event_ids: List[str],
        analyst_notes: Optional[str] = None,
    ) -> List[InvestigationCase]:
        """Creates InvestigationCase records for selected transactions from a DetectionJob (SUC-16)."""
        if not self.investigation_repo:
            raise ValueError("InvestigationRepository is not configured.")

        if not event_ids:
            raise ValueError("At least one transaction event_id must be selected.")

        job = self.get_detection_job(job_id)
        res = self.get_detection_job_results(job_id=job_id, limit=100000, offset=0)
        tx_map: Dict[str, Dict[str, Any]] = {
            str(tx["event_id"]): tx for tx in res["transactions"]
        }

        created_cases: List[InvestigationCase] = []
        for raw_ev_id in event_ids:
            ev_key = str(raw_ev_id)
            tx = tx_map.get(ev_key)
            if not tx:
                continue

            # Resolve numeric event_id for InvestigationCase entity
            try:
                numeric_event_id = int(float(ev_key))
            except (ValueError, TypeError):
                numeric_event_id = abs(hash(ev_key)) % 1000000000

            # Avoid duplicate case creation for the same event_id in the same project
            existing = self.investigation_repo.get_case_by_event_id(numeric_event_id)
            if existing and str(existing.project_id) == str(job.project_id):
                created_cases.append(existing)
                continue

            m_score = float(tx.get("model_score", 0.0))
            f_action = str(tx.get("final_action", "REVIEW")).upper()
            if f_action == "REJECT" or m_score >= 0.80:
                risk = RiskLevel.CRITICAL
            elif m_score >= 0.50 or f_action == "REVIEW":
                risk = RiskLevel.HIGH
            elif m_score >= 0.20:
                risk = RiskLevel.MEDIUM
            else:
                risk = RiskLevel.LOW

            case_entity = InvestigationCase(
                project_id=job.project_id,
                event_id=numeric_event_id,
                status=InvestigationStatus.PENDING,
                risk_level=risk,
                fraud_probability=m_score,
                analyst_notes=analyst_notes,
                action_taken=f_action,
                metadata={
                    "job_id": str(job.job_id),
                    "job_name": job.job_name,
                    "raw_event_id": ev_key,
                    "user_id": tx.get("user_id"),
                    "timestamp": tx.get("timestamp"),
                    "amount": tx.get("amount"),
                    "model_score": m_score,
                    "final_action": f_action,
                    "rule_action": tx.get("rule_action"),
                    "triggered_rules": tx.get("triggered_rules", []),
                    "triggered_rule_details": tx.get("triggered_rule_details", []),
                    "features": tx.get("features", {}),
                },
            )
            saved = self.investigation_repo.save_case(case_entity)
            created_cases.append(saved)

        return created_cases