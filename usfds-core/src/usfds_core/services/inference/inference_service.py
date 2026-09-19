"""USFDS Inference Service for Online and Batch Fraud Detection Inference.
Orchestrates online real-time scoring and dispatches batch inference jobs.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Any, Optional, Tuple, Union
from uuid import UUID, uuid4
import joblib
import pandas as pd

from usfds_core.domain.entities.detection import DetectionJob, Pipeline
from usfds_core.domain.entities.enums import DeploymentStatus, DetectionJobStatus
from usfds_core.domain.schemas.inference_payload import (
    BatchInferencePayload,
    BatchInferenceResult,
)
from usfds_core.repositories.base_detection_job_repo import IDetectionJobRepository
from usfds_core.repositories.pipeline_repo import IPipelineRepository
from usfds_core.services.inference.dispatchers.base_dispatcher import IBatchInferenceDispatcher
from usfds_core.services.inference.executor import (
    BatchInferenceExecutor,
    prepare_and_validate_input,
    run_feature_transformations,
)
from usfds_core.services.inference.scoring_service import ModelScorer
from usfds_core.services.inference.workspace import InferenceWorkspace
from usfds_core.storage.base_storage import IFileStorage

logger = logging.getLogger(__name__)


class InferenceService:
    """Service orchestrating ML inference workflows:
    - Online Inference: Low-latency real-time single-event scoring.
    - Batch Inference: Pre-dispatch job registration -> Payload dispatch -> Post-execution record update.
    """

    def __init__(
        self,
        pipeline_repo: IPipelineRepository,
        file_storage: IFileStorage,
        detection_job_repo: Optional[IDetectionJobRepository] = None,
        dispatcher: Optional[IBatchInferenceDispatcher] = None,
    ):
        self.pipeline_repo = pipeline_repo
        self.file_storage = file_storage
        self.detection_job_repo = detection_job_repo
        self.dispatcher = dispatcher

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
    ) -> Tuple[Any, Any, Any]:
        """Downloads and deserializes all required pipeline artifacts into the workspace."""
        # 1. Feature Engineering transformers (.joblib)
        fe_path = pipeline.feature_engineered_dataset_artifact.output_paths.get("fitted_engineers")
        if not fe_path:
            raise FileNotFoundError(
                f"Missing 'fitted_engineers' in feature_engineered_dataset_artifact output_paths: "
                f"{pipeline.feature_engineered_dataset_artifact.output_paths}"
            )
        fe_bytes = self._read_bytes(fe_path)
        with open(workspace.fitted_engineers_path, "wb") as f:
            f.write(fe_bytes)
        fitted_engineers = joblib.load(workspace.fitted_engineers_path)

        # 2. Preprocessing pipeline (.joblib)
        prep_path = pipeline.preprocessed_dataset_artifact.output_paths.get("pipeline")
        if not prep_path:
            raise FileNotFoundError(
                f"Missing 'pipeline' in preprocessed_dataset_artifact output_paths: "
                f"{pipeline.preprocessed_dataset_artifact.output_paths}"
            )
        prep_bytes = self._read_bytes(prep_path)
        with open(workspace.fitted_pipeline_path, "wb") as f:
            f.write(prep_bytes)
        preprocessing_pipeline = joblib.load(workspace.fitted_pipeline_path)

        # 3. Model weights / classifier (.joblib)
        model_uri = pipeline.model_version.artifact_uri
        if not model_uri:
            raise FileNotFoundError("Missing artifact_uri in pipeline.model_version")
        model_bytes = self._read_bytes(model_uri)
        with open(workspace.model_path, "wb") as f:
            f.write(model_bytes)
        model = joblib.load(workspace.model_path)

        return fitted_engineers, preprocessing_pipeline, model

    def online_inference(
        self,
        deployment_id: UUID,
        event: dict,
    ) -> dict:
        """Executes low-latency real-time fraud scoring on a single transaction event.

        Args:
            deployment_id: ID of the active model deployment.
            event: Dictionary of event properties (supports RAW or MAPPED schema).

        Returns:
            Dictionary containing prediction (0 or 1), fraud probability, risk score,
            and execution latency.
        """
        start_time = time.time()
        pipeline = self._validate_deployment(deployment_id)

        workspace = InferenceWorkspace(deployment_id=deployment_id)
        workspace.initialize()

        try:
            # 1. Download & load pipeline artifacts
            fitted_engineers, preprocessing_pipeline, model = self._load_pipeline_artifacts(
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

            # 4. Transform features
            X = run_feature_transformations(
                prepared_df, fitted_engineers, preprocessing_pipeline, model
            )

            # 5. Predict using model's configured decision threshold
            threshold = 0.5
            if pipeline.model_version and hasattr(pipeline.model_version, "decision_threshold"):
                threshold = getattr(pipeline.model_version, "decision_threshold", 0.5) or 0.5

            preds, fraud_probs = ModelScorer.predict_with_probabilities(model, X, threshold=threshold)
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
        """Pre-dispatch phase for batch inference:
        1. Validates deployment and extracts pipeline lineage.
        2. Persists DetectionJob entity in PENDING status with input_path.
        3. Prepares BatchInferencePayload (worker receives 0 direct DB access).
        4. Marks DetectionJob as RUNNING and dispatches to dispatcher/executor.

        Args:
            project_id: Project identifier.
            deployment_id: ID of the active model deployment.
            input_path: Storage path or URI of the input dataset uploaded to storage.
            job_name: Optional custom name for the detection job.
            user_name: Identifier of user initiating the job.
            decision_threshold: Optional override for model decision threshold.

        Returns:
            The created DetectionJob entity.
        """
        pipeline = self._validate_deployment(deployment_id)

        # 1. Extract pipeline artifact paths
        fe_path = pipeline.feature_engineered_dataset_artifact.output_paths.get("fitted_engineers")
        prep_path = pipeline.preprocessed_dataset_artifact.output_paths.get("pipeline")
        model_uri = pipeline.model_version.artifact_uri

        if not fe_path or not prep_path or not model_uri:
            raise FileNotFoundError("One or more required pipeline artifacts are missing in the pipeline lineage.")

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


        # 5. Update status to RUNNING
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
        """Post-execution handler for batch detection job results:
        Updates DetectionJob record with completion metrics or failure details.

        Args:
            result: BatchInferenceResult received from worker executor.

        Returns:
            Updated DetectionJob entity.
        """
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