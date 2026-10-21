"""Custom Support Vector Machine (SVM) Model Plugin for USFDS.

Demonstrates:
1. Consuming CSV files (`pd.read_csv`) via automatic platform Parquet->CSV adaptation.
2. Fitting and persisting a model-specific preprocessing pipeline (`preprocessor.joblib`) alongside `model.joblib`.
3. End-to-end `run_training` and `run_inference` execution.
"""

from pathlib import Path
from typing import Any, Dict, List, Set
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import LinearSVC

NON_PREDICTIVE_COLS: Set[str] = {
    "event_id",
    "transaction_id",
    "user_id",
    "timestamp",
    "transaction_time",
    "label",
    "is_fraud",
    "target",
    "class",
}


def _build_and_fit_preprocessor(df: pd.DataFrame) -> tuple[ColumnTransformer, np.ndarray]:
    drop_cols = [c for c in df.columns if str(c).lower() in NON_PREDICTIVE_COLS]
    X_df = df.drop(columns=drop_cols, errors="ignore")

    cat_cols: List[str] = [
        c for c in X_df.columns
        if pd.api.types.is_object_dtype(X_df[c])
        or isinstance(X_df[c].dtype, pd.CategoricalDtype)
        or pd.api.types.is_string_dtype(X_df[c])
    ]
    num_cols: List[str] = [c for c in X_df.columns if c not in cat_cols]

    transformers = []
    if num_cols:
        transformers.append((
            "num",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]),
            num_cols,
        ))
    if cat_cols:
        transformers.append((
            "cat",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]),
            cat_cols,
        ))

    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
    X_transformed = np.asarray(preprocessor.fit_transform(X_df), dtype=np.float32)
    return preprocessor, X_transformed


def _transform_with_preprocessor(df: pd.DataFrame, preprocessor: ColumnTransformer) -> np.ndarray:
    drop_cols = [c for c in df.columns if str(c).lower() in NON_PREDICTIVE_COLS]
    X_df = df.drop(columns=drop_cols, errors="ignore")
    return np.asarray(preprocessor.transform(X_df), dtype=np.float32)


def run_training(
    train_file: str,
    test_file: str,
    artifact_dir: str,
    target_column: str,
    hyperparameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Train Calibrated LinearSVC on CSV input files."""
    df_train = pd.read_csv(train_file)
    df_test = pd.read_csv(test_file)

    y_train = df_train[target_column].astype(int).to_numpy()
    y_test = df_test[target_column].astype(int).to_numpy()

    preprocessor, X_train = _build_and_fit_preprocessor(df_train.drop(columns=[target_column]))
    X_test = _transform_with_preprocessor(df_test.drop(columns=[target_column]), preprocessor)

    c_val = float(hyperparameters.get("C", 0.5))
    max_iter = int(hyperparameters.get("max_iter", 500))

    base_svm = LinearSVC(
        C=c_val,
        max_iter=max_iter,
        class_weight="balanced",
        random_state=42,
    )
    model = CalibratedClassifierCV(estimator=base_svm, cv=2)
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
    """Run fraud probability inference on unlabeled CSV input."""
    df_input = pd.read_csv(input_file)

    art_path = Path(artifact_dir)
    preprocessor: ColumnTransformer = joblib.load(art_path / "preprocessor.joblib")
    model: CalibratedClassifierCV = joblib.load(art_path / "model.joblib")

    X_input = _transform_with_preprocessor(df_input, preprocessor)
    y_prob = model.predict_proba(X_input)[:, 1]
    return np.asarray(y_prob, dtype=float)
