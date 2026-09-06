from abc import ABC, abstractmethod
import json
import logging
from typing import Any, Dict, Tuple
import joblib
import pandas as pd

from usfds_core.services.training.evaluators.metric_evaluator import MetricEvaluator
from usfds_core.services.training.models.base_trainer import BaseTrainer
from usfds_core.services.training.workspace import TrainingRunWorkspace

logger = logging.getLogger(__name__)


class BuiltinModelTrainer(BaseTrainer, ABC):
    """Abstract base class for built-in models, implementing the template training method:
    Load data -> Fit estimator -> Save model artifacts -> Evaluate metrics -> Save metrics.json.
    """

    def train(
        self,
        workspace: TrainingRunWorkspace,
        target_column: str,
        hyperparameters: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute template training pipeline."""
        X_train, y_train, X_eval, y_eval = self._load_data(workspace, target_column)

        logger.info(f"Training {self.__class__.__name__} on {len(X_train)} samples...")
        model = self._fit_model(X_train, y_train, hyperparameters)

        self._save_artifacts(workspace, model)
        metrics = self._evaluate_and_save(workspace, model, X_eval, y_eval)
        return metrics

    def _load_data(
        self, workspace: TrainingRunWorkspace, target_column: str
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        """Read train and test parquet datasets from the workspace."""
        train_path = workspace.train_data_path
        if not train_path.exists():
            raise FileNotFoundError(f"Training data not found at {train_path}")

        df_train = pd.read_parquet(train_path)
        if target_column not in df_train.columns:
            raise ValueError(f"Target column '{target_column}' not found in training dataset.")

        X_train = df_train.drop(columns=[target_column])
        y_train = df_train[target_column]

        test_path = workspace.test_data_path
        if test_path.exists():
            df_test = pd.read_parquet(test_path)
            if target_column in df_test.columns:
                X_eval = df_test.drop(columns=[target_column])
                y_eval = df_test[target_column]
            else:
                X_eval, y_eval = X_train, y_train
        else:
            X_eval, y_eval = X_train, y_train

        if pd.api.types.is_numeric_dtype(y_train):
            y_train = y_train.astype(int)
        if pd.api.types.is_numeric_dtype(y_eval):
            y_eval = y_eval.astype(int)

        return X_train, y_train, X_eval, y_eval

    def _evaluate_and_save(
        self,
        workspace: TrainingRunWorkspace,
        model: Any,
        X_eval: pd.DataFrame,
        y_eval: pd.Series,
    ) -> Dict[str, Any]:
        """Evaluate fitted model and write metrics.json to the workspace."""
        y_pred = model.predict(X_eval)
        y_prob = None
        if hasattr(model, "predict_proba"):
            try:
                y_prob = model.predict_proba(X_eval)[:, 1]
            except Exception as e:
                logger.warning(f"Could not compute prediction probabilities: {e}")

        metrics = MetricEvaluator.evaluate(y_eval, y_pred, y_prob)

        workspace.output_dir.mkdir(parents=True, exist_ok=True)
        with open(workspace.metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        return metrics

    @abstractmethod
    def _fit_model(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        hyperparameters: Dict[str, Any],
    ) -> Any:
        """Initialize and fit the concrete algorithm estimator."""
        pass

    @abstractmethod
    def _save_artifacts(self, workspace: TrainingRunWorkspace, model: Any) -> None:
        """Serialize and save algorithm-specific artifacts into workspace.model_dir."""
        pass


class RandomForestTrainer(BuiltinModelTrainer):
    """Concrete trainer for Scikit-Learn Random Forest Classifier."""

    def _fit_model(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        hyperparameters: Dict[str, Any],
    ) -> Any:
        from sklearn.ensemble import RandomForestClassifier

        params = {k: v for k, v in hyperparameters.items() if v is not None}
        params.setdefault("random_state", 42)

        model = RandomForestClassifier(**params)
        model.fit(X_train, y_train)
        return model

    def _save_artifacts(self, workspace: TrainingRunWorkspace, model: Any) -> None:
        workspace.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, workspace.model_dir / "model.joblib")


class XGBoostTrainer(BuiltinModelTrainer):
    """Concrete trainer for XGBoost Classifier."""

    def _fit_model(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        hyperparameters: Dict[str, Any],
    ) -> Any:
        import xgboost as xgb

        params = {k: v for k, v in hyperparameters.items() if v is not None}
        params.setdefault("random_state", 42)
        params.setdefault("eval_metric", "logloss")

        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train)
        return model

    def _save_artifacts(self, workspace: TrainingRunWorkspace, model: Any) -> None:
        workspace.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, workspace.model_dir / "model.joblib")
        try:
            model.save_model(str(workspace.model_dir / "model.json"))
        except Exception as e:
            logger.warning(f"Failed to export native xgb model.json: {e}")
