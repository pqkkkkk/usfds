from typing import Any, Optional, Union
import numpy as np
import pandas as pd

from usfds_core.services.preprocessing.feature_engineering.base_engineer import BaseFeatureEngineer


class CreditCardFeatureEngineer(BaseFeatureEngineer):
    """Generates standard credit card fraud detection features such as cyclical time and amount ratios."""

    def __init__(
        self,
        time_col: Optional[str] = "Time",
        amount_col: Optional[str] = "Amount",
        add_ratio: bool = True,
        enable_hour_of_day: bool = True,
    ):
        self.time_col = time_col
        self.amount_col = amount_col
        self.add_ratio = add_ratio
        self.enable_hour_of_day = enable_hour_of_day
        self.mean_amount_: Optional[float] = None

    def _resolve_column(self, df: pd.DataFrame, col_name: Optional[str]) -> Optional[str]:
        if not col_name or not isinstance(df, pd.DataFrame):
            return None
        if col_name in df.columns:
            return col_name
        # Case-insensitive fallback
        for c in df.columns:
            if c.lower() == col_name.lower():
                return c
        return None

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> "CreditCardFeatureEngineer":
        if isinstance(X, pd.DataFrame) and self.add_ratio and self.amount_col:
            col = self._resolve_column(X, self.amount_col)
            if col:
                numeric_amt = pd.to_numeric(X[col], errors="coerce")
                self.mean_amount_ = float(numeric_amt.mean())
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        if not isinstance(X, pd.DataFrame):
            return X

        X_out = X.copy()

        # 1. Hour of day calculation
        if self.enable_hour_of_day and self.time_col:
            t_col = self._resolve_column(X_out, self.time_col)
            if t_col:
                time_series = X_out[t_col]
                if pd.api.types.is_numeric_dtype(time_series):
                    X_out["hour_of_day"] = (time_series.astype(float) / 3600.0) % 24.0
                else:
                    # Parse datetime string (ISO formats, timestamps, etc.)
                    dt_series = pd.to_datetime(time_series, errors="coerce")
                    if not dt_series.isna().all():
                        X_out["hour_of_day"] = dt_series.dt.hour + (dt_series.dt.minute / 60.0)
                        # Drop raw string datetime column so it doesn't break PCA / ML estimators
                        X_out = X_out.drop(columns=[t_col])

        # 2. Amount to mean ratio
        if self.add_ratio and self.mean_amount_ is not None and self.amount_col:
            a_col = self._resolve_column(X_out, self.amount_col)
            if a_col:
                numeric_amt = pd.to_numeric(X_out[a_col], errors="coerce")
                X_out["amount_to_mean_ratio"] = numeric_amt / (self.mean_amount_ + 1e-6)

        return X_out


__all__ = ["CreditCardFeatureEngineer"]
