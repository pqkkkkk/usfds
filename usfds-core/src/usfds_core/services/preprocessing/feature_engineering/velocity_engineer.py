from typing import Any, List, Optional, Union
import numpy as np
import pandas as pd

from usfds_core.services.preprocessing.feature_engineering.base_engineer import BaseFeatureEngineer


class VelocityFeatureEngineer(BaseFeatureEngineer):
    """Generates rolling window velocity statistics (transaction frequency / sum) per entity/customer."""

    def __init__(
        self,
        customer_id_col: Optional[str] = None,
        time_col: Optional[str] = "Time",
        amount_col: Optional[str] = "Amount",
        windows: Optional[List[int]] = None,
    ):
        self.customer_id_col = customer_id_col
        self.time_col = time_col
        self.amount_col = amount_col
        self.windows = windows or [1, 24, 168]

    def fit(self, X: Any, y: Optional[Any] = None) -> "VelocityFeatureEngineer":
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        if not isinstance(X, pd.DataFrame) or not self.customer_id_col or self.customer_id_col not in X.columns:
            return X

        X_out = X.copy()
        # If time_col exists, ensure rows are chronologically ordered per customer
        if self.time_col and self.time_col in X_out.columns:
            sorted_indices = X_out.sort_values(by=[self.customer_id_col, self.time_col]).index
            for w in self.windows:
                freq_col = f"tx_freq_last_{w}h"
                X_out.loc[sorted_indices, freq_col] = (
                    X_out.loc[sorted_indices]
                    .groupby(self.customer_id_col)[self.time_col]
                    .rolling(window=w, min_periods=1)
                    .count()
                    .reset_index(level=0, drop=True)
                )
                if self.amount_col and self.amount_col in X_out.columns:
                    sum_col = f"tx_sum_last_{w}h"
                    X_out.loc[sorted_indices, sum_col] = (
                        X_out.loc[sorted_indices]
                        .groupby(self.customer_id_col)[self.amount_col]
                        .rolling(window=w, min_periods=1)
                        .sum()
                        .reset_index(level=0, drop=True)
                    )
        return X_out
