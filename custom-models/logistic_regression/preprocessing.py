"""Model-owned preprocessing module for the Custom Logistic Regression plugin."""

from typing import List, Set
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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


class TabularFraudPreprocessor:
    """Encapsulates column filtering, missing value imputation, numeric scaling,
    and categorical one-hot encoding for tabular linear models.
    """

    def __init__(self) -> None:
        self.num_cols: List[str] = []
        self.cat_cols: List[str] = []
        self.transformer: ColumnTransformer | None = None

    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        feature_df = self._drop_non_predictive(df)
        self.cat_cols = [
            c for c in feature_df.columns
            if pd.api.types.is_object_dtype(feature_df[c])
            or isinstance(feature_df[c].dtype, pd.CategoricalDtype)
            or pd.api.types.is_string_dtype(feature_df[c])
        ]
        self.num_cols = [c for c in feature_df.columns if c not in self.cat_cols]

        steps = []
        if self.num_cols:
            num_pipe = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ])
            steps.append(("num", num_pipe, self.num_cols))

        if self.cat_cols:
            cat_pipe = Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ])
            steps.append(("cat", cat_pipe, self.cat_cols))

        self.transformer = ColumnTransformer(transformers=steps, remainder="drop")
        return np.asarray(self.transformer.fit_transform(feature_df), dtype=np.float32)

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if self.transformer is None:
            raise RuntimeError("TabularFraudPreprocessor has not been fitted.")
        feature_df = self._drop_non_predictive(df)
        return np.asarray(self.transformer.transform(feature_df), dtype=np.float32)

    @staticmethod
    def _drop_non_predictive(df: pd.DataFrame) -> pd.DataFrame:
        cols_to_drop = [
            c for c in df.columns
            if str(c).lower() in NON_PREDICTIVE_COLS
            or pd.api.types.is_datetime64_any_dtype(df[c])
        ]
        return df.drop(columns=cols_to_drop, errors="ignore")
