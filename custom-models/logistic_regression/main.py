"""Custom Logistic Regression Model Plugin for USFDS.

Conforms to the USFDS Entrypoint Function Contract:
- `run_training(train_file, test_file, artifact_dir, target_column, hyperparameters)`
- `run_inference(input_file, artifact_dir)`
"""

from pathlib import Path
from typing import Any, Dict
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from preprocessing import TabularFraudPreprocessor


def run_training(
    train_file: str,
    test_file: str,
    artifact_dir: str,
    target_column: str,
    hyperparameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Train Logistic Regression along with its model-specific preprocessor on FEATURE_ENGINEERED data."""
    df_train = pd.read_parquet(train_file)
    df_test = pd.read_parquet(test_file)

    y_train = df_train[target_column].astype(int).to_numpy()
    y_test = df_test[target_column].astype(int).to_numpy()

    preprocessor = TabularFraudPreprocessor()
    X_train = preprocessor.fit_transform(df_train.drop(columns=[target_column]))
    X_test = preprocessor.transform(df_test.drop(columns=[target_column]))

    c_val = float(hyperparameters.get("C", 1.0))
    max_iter = int(hyperparameters.get("max_iter", 200))
    class_weight = hyperparameters.get("class_weight", "balanced")

    model = LogisticRegression(
        C=c_val,
        max_iter=max_iter,
        class_weight=class_weight,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_prob = model.predict_proba(X_test)[:, 1]

    out_dir = Path(artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(preprocessor, out_dir / "preprocessor.joblib")
    joblib.dump(model, out_dir / "model.joblib")

    return {
        "y_true": y_test.tolist(),
        "y_prob": y_prob.tolist(),
    }


def run_inference(
    input_file: str,
    artifact_dir: str,
) -> np.ndarray:
    """Run fraud probability inference on unlabeled FEATURE_ENGINEERED data."""
    df_input = pd.read_parquet(input_file)

    art_path = Path(artifact_dir)
    preprocessor: TabularFraudPreprocessor = joblib.load(art_path / "preprocessor.joblib")
    model: LogisticRegression = joblib.load(art_path / "model.joblib")

    X_input = preprocessor.transform(df_input)
    y_prob = model.predict_proba(X_input)[:, 1]
    return np.asarray(y_prob, dtype=float)
