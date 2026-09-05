from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from usfds_core.services.preprocessing.feature_engineering.base_engineer import BaseFeatureEngineer



class VelocityFeatureEngineer(BaseFeatureEngineer):
    """Generates rolling window velocity statistics (transaction frequency / sum) per entity/user."""

    def __init__(
        self,
        customer_id_col: Optional[str] = None,
        user_id_col: Optional[str] = "user_id",
        time_col: Optional[str] = "timestamp",
        amount_col: Optional[str] = "amount",
        windows: Optional[List[int]] = None,
    ):
        self.user_id_col = customer_id_col if customer_id_col is not None else user_id_col
        self.customer_id_col = self.user_id_col
        self.time_col = time_col
        self.amount_col = amount_col
        self.windows = windows or [1, 24, 168]
        self.train_history_: Optional[pd.DataFrame] = None

    def _resolve_column(
        self,
        df: pd.DataFrame,
        col_name: Optional[str],
        aliases: Optional[List[str]] = None,
    ) -> Optional[str]:
        if not col_name or not isinstance(df, pd.DataFrame):
            return None
        if col_name in df.columns:
            return col_name

        def normalize_str(s: str) -> str:
            return str(s).lower().replace("_", "").replace(" ", "").replace("-", "")

        target = normalize_str(col_name)
        for c in df.columns:
            if normalize_str(c) == target:
                return str(c)

        if aliases:
            for alias in aliases:
                alias_norm = normalize_str(alias)
                for c in df.columns:
                    if normalize_str(c) == alias_norm:
                        return str(c)
        return None

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> "VelocityFeatureEngineer":
        if not isinstance(X, pd.DataFrame):
            return self

        user_col = self._resolve_column(X, self.user_id_col, ["customer_id", "client_id", "account_id"])
        time_col = self._resolve_column(X, self.time_col, ["Time", "datetime", "date_time", "tx_time"])
        amount_col = self._resolve_column(X, self.amount_col, ["Amount", "amt", "tx_amount"])

        if user_col and time_col:
            keep_cols = [user_col, time_col]
            if amount_col:
                keep_cols.append(amount_col)
            # Store history to allow continuous rolling computation across train/test boundary
            self.train_history_ = X[keep_cols].copy()
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        if not isinstance(X, pd.DataFrame):
            return X

        user_col = self._resolve_column(X, self.user_id_col, ["customer_id", "client_id", "account_id"])
        time_col = self._resolve_column(X, self.time_col, ["Time", "datetime", "date_time", "tx_time"])
        amount_col = self._resolve_column(X, self.amount_col, ["Amount", "amt", "tx_amount"])

        if not user_col or not time_col:
            return X

        # Check if transforming test data with historical train context
        is_test_with_history = (
            self.train_history_ is not None
            and not X.empty
            and not self.train_history_.empty
            and (len(X) != len(self.train_history_) or not X.index.equals(self.train_history_.index))
        )

        if is_test_with_history:
            assert self.train_history_ is not None
            train_hist = self.train_history_.copy()
            # Align column names in train_hist if necessary
            hist_user = self._resolve_column(train_hist, self.user_id_col, ["customer_id", "client_id", "account_id"])
            hist_time = self._resolve_column(train_hist, self.time_col, ["Time", "datetime", "date_time", "tx_time"])
            hist_amt = self._resolve_column(train_hist, self.amount_col, ["Amount", "amt", "tx_amount"])
            
            rename_map: Dict[str, str] = {}
            if hist_user and hist_user != user_col:
                rename_map[hist_user] = user_col
            if hist_time and hist_time != time_col:
                rename_map[hist_time] = time_col
            if hist_amt and amount_col and hist_amt != amount_col:
                rename_map[hist_amt] = amount_col
            if rename_map:
                train_hist = train_hist.rename(columns=rename_map)

            # Combine train history and current X
            n_history = len(train_hist)
            combined_df = pd.concat([train_hist, X], ignore_index=True)
        else:
            n_history = 0
            combined_df = X.copy()

        # Parse datetime for accurate time-window rolling
        t_series = combined_df[time_col]
        if pd.api.types.is_numeric_dtype(t_series):
            # Numeric seconds/epochs
            dt_series = pd.to_datetime(t_series, unit="s", origin="unix", errors="coerce")
        else:
            dt_series = pd.to_datetime(t_series, errors="coerce")

        use_time_rolling = not dt_series.isna().all()
        if use_time_rolling:
            combined_df["_vel_dt"] = dt_series
            sorted_indices = combined_df.sort_values(by=[user_col, "_vel_dt"]).index
            df_sorted = combined_df.loc[sorted_indices]

            for w in self.windows:
                freq_col = f"tx_freq_last_{w}h"
                sum_col = f"tx_sum_last_{w}h"

                # Calculate frequency
                freq_res = (
                    df_sorted.groupby(user_col)
                    .rolling(f"{w}h", on="_vel_dt")[time_col]
                    .count()
                )
                combined_df.loc[sorted_indices, freq_col] = freq_res.to_numpy()

                # Calculate sum
                if amount_col and amount_col in combined_df.columns:
                    numeric_amt = pd.to_numeric(df_sorted[amount_col], errors="coerce").fillna(0.0)
                    df_sorted["_vel_amt"] = numeric_amt
                    sum_res = (
                        df_sorted.groupby(user_col)
                        .rolling(f"{w}h", on="_vel_dt")["_vel_amt"]
                        .sum()
                    )
                    combined_df.loc[sorted_indices, sum_col] = sum_res.to_numpy()

            combined_df = combined_df.drop(columns=["_vel_dt"], errors="ignore")
        else:
            # Fallback to row-count rolling
            sorted_indices = combined_df.sort_values(by=[user_col, time_col]).index
            df_sorted = combined_df.loc[sorted_indices]
            for w in self.windows:
                freq_col = f"tx_freq_last_{w}h"
                sum_col = f"tx_sum_last_{w}h"
                combined_df.loc[sorted_indices, freq_col] = (
                    df_sorted.groupby(user_col)[time_col]
                    .rolling(window=w, min_periods=1)
                    .count()
                    .reset_index(level=0, drop=True)
                )
                if amount_col and amount_col in combined_df.columns:
                    numeric_amt = pd.to_numeric(df_sorted[amount_col], errors="coerce").fillna(0.0)
                    df_sorted["_vel_amt"] = numeric_amt
                    combined_df.loc[sorted_indices, sum_col] = (
                        df_sorted.groupby(user_col)["_vel_amt"]
                        .rolling(window=w, min_periods=1)
                        .sum()
                        .reset_index(level=0, drop=True)
                    )

        if n_history > 0:
            X_out = combined_df.iloc[n_history:].copy()
            X_out.index = X.index
        else:
            X_out = combined_df

        return X_out


__all__ = ["VelocityFeatureEngineer"]

