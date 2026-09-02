from typing import Any, List, Optional, Union
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from usfds_core.services.preprocessing.transformations.base_transformer import BaseDataTransformer


class Log1pTransformer(BaseDataTransformer):
    """Applies log1p transformation log(1 + max(0, x)) to handle skewed financial distributions."""

    def __init__(self, columns: Optional[List[str]] = None):
        self.columns = columns

    def fit(self, X: Any, y: Optional[Any] = None) -> "Log1pTransformer":
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        if isinstance(X, pd.DataFrame):
            X_out = X.copy()
            cols = self.columns if self.columns else X_out.columns
            for col in cols:
                if col in X_out.columns and np.issubdtype(X_out[col].dtype, np.number):
                    X_out[col] = np.log1p(np.maximum(0, X_out[col]))
            return X_out
        else:
            return np.log1p(np.maximum(0, np.asarray(X, dtype=float)))


__all__ = [
    "Log1pTransformer",
    "StandardScaler",
    "MinMaxScaler",
    "RobustScaler",
]
