import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Optional, Union

from usfds_core.domain.schemas.training_payload import TrainingRunPayload, TrainingRunResult
from usfds_core.services.training.models.trainer_factory import ModelTrainerFactory
from usfds_core.services.training.notifiers.base_notifier import ITrainingResultNotifier
from usfds_core.services.training.plugins.register import (
    extract_zip_bytes_to_directory,
    package_model_bundle_bytes,
)
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

    def _read_bytes(self, path_or_uri: Union[str, Path]) -> bytes:
        """Read bytes from IFileStorage or local filesystem fallback."""
        path_str = str(path_or_uri)
        if self.file_storage.exists(path_str):
            return self.file_storage.read_bytes(path_str)
        local_p = Path(path_str)
        if local_p.is_file():
            return local_p.read_bytes()
        # Let file_storage raise the canonical FileNotFoundError
        return self.file_storage.read_bytes(path_str)

    def _resolve_script_entrypoint(
        self,
        entrypoint_uri: Optional[str],
        workspace: TrainingRunWorkspace,
    ) -> Optional[str]:
        """If entrypoint_uri refers to a zip package in IFileStorage, extract it into workspace.plugin_src_dir."""
        if not entrypoint_uri:
            return None

        local_p = Path(entrypoint_uri)
        if local_p.exists():
            return str(local_p.resolve())

        if self.file_storage.exists(entrypoint_uri):
            raw_bytes = self.file_storage.read_bytes(entrypoint_uri)
            if entrypoint_uri.lower().endswith(".zip"):
                extract_zip_bytes_to_directory(raw_bytes, workspace.plugin_src_dir)
                return str(workspace.plugin_src_dir.resolve())
            else:
                target_py = workspace.plugin_src_dir / Path(entrypoint_uri).name
                target_py.parent.mkdir(parents=True, exist_ok=True)
                target_py.write_bytes(raw_bytes)
                return str(target_py.resolve())

        return entrypoint_uri

    def run(self, payload: TrainingRunPayload) -> TrainingRunResult:
        """Execute the training workflow: download data -> train -> upload artifacts -> notify."""
        start_time = time.time()
        workspace = TrainingRunWorkspace(run_id=payload.run_id)

        try:
            workspace.initialize()

            logger.info(f"Downloading training data from {payload.train_storage_path}...")
            train_bytes = self._read_bytes(payload.train_storage_path)
            with open(workspace.train_data_path, "wb") as f:
                f.write(train_bytes)

            if payload.test_storage_path:
                logger.info(f"Downloading test data from {payload.test_storage_path}...")
                test_bytes = self._read_bytes(payload.test_storage_path)
                with open(workspace.test_data_path, "wb") as f:
                    f.write(test_bytes)

            with open(workspace.config_path, "w", encoding="utf-8") as f:
                json.dump(payload.model_dump(mode="json"), f, indent=2)

            resolved_entrypoint = self._resolve_script_entrypoint(payload.entrypoint_uri, workspace)

            # Resolve trainer & run training
            trainer = ModelTrainerFactory.create_trainer(
                execution_type=payload.execution_type,
                model_name=payload.model_name,
                entrypoint_uri=resolved_entrypoint,
            )

            metrics = trainer.train(
                workspace=workspace,
                target_column=payload.target_column,
                hyperparameters=payload.hyperparameters,
            )

            # Upload model artifacts
            model_files = [p for p in workspace.model_dir.glob("*") if p.is_file()]
            if not model_files:
                raise FileNotFoundError(f"No model artifacts found in {workspace.model_dir}")

            main_model_file = model_files[0]
            for f in model_files:
                if f.name in ["model.joblib", "model.pt", "model.pth", "model.json", "model.onnx"]:
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

            # Copy fitted_feature_engineers.joblib and column_mapping.json into the model run folder for self-contained inference
            if payload.fe_artifact_path:
                try:
                    fe_bytes = self._read_bytes(payload.fe_artifact_path)
                    fe_uri = f"models/{payload.model_id}/runs/{payload.run_id}/fitted_feature_engineers.joblib"
                    self.file_storage.save_bytes(fe_uri, fe_bytes)
                except Exception as fe_ex:
                    logger.warning(f"Failed to bundle fitted_feature_engineers.joblib into model run: {fe_ex}")

            if payload.column_mapping:
                try:
                    cm_bytes = json.dumps(payload.column_mapping, indent=2).encode("utf-8")
                    cm_uri = f"models/{payload.model_id}/runs/{payload.run_id}/column_mapping.json"
                    self.file_storage.save_bytes(cm_uri, cm_bytes)
                except Exception as cm_ex:
                    logger.warning(f"Failed to bundle column_mapping.json into model run: {cm_ex}")

            # Package self-contained model_bundle.zip for SCRIPT plugins (or multi-artifact runs)
            is_script_plugin = (
                str(payload.execution_type).upper() == "SCRIPT"
                and (workspace.plugin_src_dir / "main.py").exists()
            )
            if is_script_plugin:
                bundle_bytes = package_model_bundle_bytes(
                    artifact_dir=workspace.model_dir,
                    plugin_src_dir=workspace.plugin_src_dir,
                )
                bundle_uri = f"models/{payload.model_id}/runs/{payload.run_id}/model_bundle.zip"
                self.file_storage.save_bytes(bundle_uri, bundle_bytes)
                main_artifact_uri = bundle_uri
                main_checksum = hashlib.sha256(bundle_bytes).hexdigest()

            # Upload metrics.json to persistent storage
            metrics_uri = None
            if workspace.metrics_path.exists():
                with open(workspace.metrics_path, "rb") as mf:
                    metrics_bytes = mf.read()
                metrics_uri = f"models/{payload.model_id}/runs/{payload.run_id}/metrics.json"
                self.file_storage.save_bytes(metrics_uri, metrics_bytes)

            # Upload eval_predictions.parquet to persistent storage
            eval_predictions_uri = None
            if workspace.eval_predictions_path.exists():
                with open(workspace.eval_predictions_path, "rb") as epf:
                    eval_pred_bytes = epf.read()
                eval_predictions_uri = f"models/{payload.model_id}/runs/{payload.run_id}/eval_predictions.parquet"
                self.file_storage.save_bytes(eval_predictions_uri, eval_pred_bytes)

            # Determine framework
            framework = "scikit-learn"
            manifest_file = workspace.plugin_src_dir / "plugin_manifest.json"
            if manifest_file.exists():
                try:
                    with open(manifest_file, "r", encoding="utf-8") as mf:
                        framework = json.load(mf).get("framework", "scikit-learn")
                except Exception:
                    pass
            elif "xgboost" in payload.model_name.lower() or "xgb" in payload.model_name.lower():
                framework = "xgboost"

            duration = int(time.time() - start_time)

            result = TrainingRunResult(
                run_id=payload.run_id,
                is_success=True,
                metrics=metrics,
                artifact_uri=main_artifact_uri,
                checksum_sha256=main_checksum,
                framework=framework,
                metrics_uri=metrics_uri,
                eval_predictions_uri=eval_predictions_uri,
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
