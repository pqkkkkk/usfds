from abc import ABC, abstractmethod
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline as SklearnPipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from usfds_core.domain.schemas.preprocessing_config import NON_ML_COLUMNS
from usfds_core.services.training.evaluators.metric_evaluator import MetricEvaluator
from usfds_core.services.training.models.base_trainer import BaseTrainer
from usfds_core.services.training.workspace import TrainingRunWorkspace

logger = logging.getLogger(__name__)


class BuiltinModelTrainer(BaseTrainer, ABC):
    """Abstract base class for built-in models, implementing the template training method:
    Load data (FEATURE_ENGINEERED or PRE_PROCESSED) -> Fit model-owned preprocessor ->
    Fit estimator -> Save model & preprocessor artifacts -> Evaluate metrics -> Save metrics.json.
    """

    def train(
        self,
        workspace: TrainingRunWorkspace,
        target_column: str,
        hyperparameters: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute template training pipeline."""
        X_train_raw, y_train, X_eval_raw, y_eval = self._load_data(workspace, target_column)
        preprocessor, X_train, X_eval = self._fit_and_transform_features(X_train_raw, X_eval_raw)

        logger.info(f"Training {self.__class__.__name__} on {len(X_train)} samples...")
        model = self._fit_model(X_train, y_train, hyperparameters)

        self._save_artifacts(workspace, model, preprocessor=preprocessor)
        metrics = self._evaluate_and_save(workspace, model, X_eval, y_eval)
        return metrics

    @staticmethod
    def _resolve_target_column(df: pd.DataFrame, requested_col: str) -> str:
        """Resolve target column from dataframe columns with fallback aliases for canonical target names."""
        if requested_col in df.columns:
            return requested_col
        canonical_targets = ["label", "is_fraud", "target", "fraud", "Class", "class"]
        if str(requested_col).lower() in {c.lower() for c in canonical_targets} | {"auto"}:
            for alias in canonical_targets:
                if alias in df.columns:
                    return alias
        raise ValueError(f"Target column '{requested_col}' not found in training dataset.")

    def _load_data(
        self, workspace: TrainingRunWorkspace, target_column: str
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        """Read train and test parquet datasets from the workspace."""
        train_path = workspace.train_data_path
        if not train_path.exists():
            raise FileNotFoundError(f"Training data not found at {train_path}")

        df_train = pd.read_parquet(train_path)
        resolved_target = self._resolve_target_column(df_train, target_column)

        X_train = df_train.drop(columns=[resolved_target])
        y_train = df_train[resolved_target]

        test_path = workspace.test_data_path
        if test_path.exists():
            df_test = pd.read_parquet(test_path)
            try:
                test_target = self._resolve_target_column(df_test, resolved_target)
                X_eval = df_test.drop(columns=[test_target])
                y_eval = df_test[test_target]
            except ValueError:
                X_eval, y_eval = X_train, y_train
        else:
            X_eval, y_eval = X_train, y_train

        if pd.api.types.is_numeric_dtype(y_train):
            y_train = y_train.astype(int)
        if pd.api.types.is_numeric_dtype(y_eval):
            y_eval = y_eval.astype(int)

        return X_train, y_train, X_eval, y_eval

    def _fit_and_transform_features(
        self,
        X_train: pd.DataFrame,
        X_eval: pd.DataFrame,
    ) -> Tuple[Any, pd.DataFrame, pd.DataFrame]:
        """Filter non-predictive identifiers/timestamps and apply model-owned encoding & scaling."""
        drop_cols = [
            c for c in X_train.columns
            if str(c).lower() in NON_ML_COLUMNS
            or pd.api.types.is_datetime64_any_dtype(X_train[c])
        ]
        X_tr = X_train.drop(columns=drop_cols, errors="ignore").copy()
        X_ev = X_eval.drop(columns=drop_cols, errors="ignore").copy()

        cat_cols: List[str] = [
            c for c in X_tr.columns
            if pd.api.types.is_object_dtype(X_tr[c])
            or isinstance(X_tr[c].dtype, pd.CategoricalDtype)
            or pd.api.types.is_string_dtype(X_tr[c])
        ]
        num_cols: List[str] = [c for c in X_tr.columns if c not in cat_cols]

        transformers = []
        if num_cols:
            num_pipe = SklearnPipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ])
            transformers.append(("num", num_pipe, num_cols))

        if cat_cols:
            cat_pipe = SklearnPipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ])
            transformers.append(("cat", cat_pipe, cat_cols))

        preprocessor = ColumnTransformer(
            transformers=transformers,
            remainder="drop",
            verbose_feature_names_out=False,
        )
        X_tr_arr = preprocessor.fit_transform(X_tr)
        X_ev_arr = preprocessor.transform(X_ev)

        try:
            feature_names = list(preprocessor.get_feature_names_out())
        except Exception:
            feature_names = [f"f_{i}" for i in range(X_tr_arr.shape[1])]

        X_tr_df = pd.DataFrame(X_tr_arr, columns=feature_names, index=X_tr.index)
        X_ev_df = pd.DataFrame(X_ev_arr, columns=feature_names, index=X_ev.index)
        return preprocessor, X_tr_df, X_ev_df

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

        # Persist test predictions for threshold tuning and cost curve analysis
        try:
            df_eval_pred = pd.DataFrame({
                "y_true": np.asarray(y_eval),
                "y_prob": np.asarray(y_prob) if y_prob is not None else np.asarray(y_pred, dtype=float),
            })
            df_eval_pred.to_parquet(workspace.eval_predictions_path, index=False)
        except Exception as e:
            logger.warning(f"Failed to save eval_predictions.parquet: {e}")

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
    def _save_artifacts(
        self,
        workspace: TrainingRunWorkspace,
        model: Any,
        preprocessor: Optional[Any] = None,
    ) -> None:
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

    def _save_artifacts(
        self,
        workspace: TrainingRunWorkspace,
        model: Any,
        preprocessor: Optional[Any] = None,
    ) -> None:
        workspace.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, workspace.model_dir / "model.joblib")
        if preprocessor is not None:
            joblib.dump(preprocessor, workspace.model_dir / "preprocessor.joblib")


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

    def _save_artifacts(
        self,
        workspace: TrainingRunWorkspace,
        model: Any,
        preprocessor: Optional[Any] = None,
    ) -> None:
        workspace.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, workspace.model_dir / "model.joblib")
        if preprocessor is not None:
            joblib.dump(preprocessor, workspace.model_dir / "preprocessor.joblib")
        try:
            model.save_model(str(workspace.model_dir / "model.json"))
        except Exception as e:
            logger.warning(f"Failed to export native xgb model.json: {e}")
