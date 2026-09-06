import hashlib
import json
import logging
import time
from typing import Optional

from usfds_core.domain.schemas.training_payload import TrainingRunPayload, TrainingRunResult
from usfds_core.services.training.models.trainer_factory import ModelTrainerFactory
from usfds_core.services.training.notifiers.base_notifier import ITrainingResultNotifier
from usfds_core.services.training.workspace import TrainingRunWorkspace
from usfds_core.storage.base_storage import IFileStorage

logger = logging.getLogger(__name__)


class TrainingRunExecutor:
    """Worker-side training run execution engine, manages the training run lifecycle.
    Operates without direct database access.
    """

    def __init__(
        self,
        file_storage: IFileStorage,
        notifier: Optional[ITrainingResultNotifier] = None,
    ):
        self.file_storage = file_storage
        self.notifier = notifier

    def run(self, payload: TrainingRunPayload) -> TrainingRunResult:
        """Execute the training workflow: download data -> train -> upload artifacts -> notify."""
        start_time = time.time()
        workspace = TrainingRunWorkspace(run_id=payload.run_id)

        try:
            workspace.initialize()

            logger.info(f"Downloading training data from {payload.train_storage_path}...")
            train_bytes = self.file_storage.read_bytes(payload.train_storage_path)
            with open(workspace.train_data_path, "wb") as f:
                f.write(train_bytes)

            if payload.test_storage_path:
                logger.info(f"Downloading test data from {payload.test_storage_path}...")
                test_bytes = self.file_storage.read_bytes(payload.test_storage_path)
                with open(workspace.test_data_path, "wb") as f:
                    f.write(test_bytes)

            with open(workspace.config_path, "w", encoding="utf-8") as f:
                json.dump(payload.model_dump(mode="json"), f, indent=2)

            # Resolve trainer & run training
            trainer = ModelTrainerFactory.create_trainer(
                execution_type=payload.execution_type,
                model_name=payload.model_name,
                entrypoint_uri=payload.entrypoint_uri,
            )

            metrics = trainer.train(
                workspace=workspace,
                target_column=payload.target_column,
                hyperparameters=payload.hyperparameters,
            )

            # Upload model artifacts
            model_files = list(workspace.model_dir.glob("*"))
            if not model_files:
                raise FileNotFoundError(f"No model artifacts found in {workspace.model_dir}")

            main_model_file = model_files[0]
            for f in model_files:
                if f.name in ["model.joblib", "model.json"]:
                    main_model_file = f
                    break

            main_artifact_uri = None
            main_checksum = None

            for file_path in model_files:
                with open(file_path, "rb") as mf:
                    artifact_bytes = mf.read()
                storage_uri = f"models/{payload.model_id}/runs/{payload.run_id}/{file_path.name}"
                self.file_storage.save_bytes(storage_uri, artifact_bytes)

                if file_path == main_model_file:
                    main_artifact_uri = storage_uri
                    main_checksum = hashlib.sha256(artifact_bytes).hexdigest()

            # Determine framework
            framework = (
                "xgboost"
                if "xgboost" in payload.model_name.lower() or "xgb" in payload.model_name.lower()
                else "scikit-learn"
            )
            duration = int(time.time() - start_time)

            result = TrainingRunResult(
                run_id=payload.run_id,
                is_success=True,
                metrics=metrics,
                artifact_uri=main_artifact_uri,
                checksum_sha256=main_checksum,
                framework=framework,
                duration_seconds=duration,
            )

        except Exception as ex:
            logger.error(f"Training run {payload.run_id} failed: {ex}", exc_info=True)
            result = TrainingRunResult(
                run_id=payload.run_id,
                is_success=False,
                error_message=str(ex),
                duration_seconds=int(time.time() - start_time),
            )
        finally:
            workspace.cleanup()

        if self.notifier:
            self.notifier.notify(result)

        return result
