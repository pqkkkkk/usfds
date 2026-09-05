from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import MissingValueStrategy
from usfds_core.services.preprocessing.cleansers.base_cleanser import BaseDataCleanser
from usfds_core.services.preprocessing.cleansers.timestamp_normalizer import TimestampNormalizer
from usfds_core.services.preprocessing.cleansers.type_coercer import NumericTypeCoercer


class StandardDataCleanser(BaseDataCleanser):
    """Stateful implementation for data cleansing, type coercion, timestamp normalization, and imputation."""

    def __init__(self, config):
        super().__init__(config)
        self.imputation_values_: Dict[str, Any] = {}
        self.outlier_bounds_: Dict[str, Tuple[float, float]] = {}

    def _resolve_col(self, df: pd.DataFrame, col_name: Optional[str]) -> Optional[str]:
        if not col_name or not isinstance(df, pd.DataFrame):
            return None
        if col_name in df.columns:
            return col_name
        for c in df.columns:
            if str(c).lower() == str(col_name).lower():
                return c
        return None

    def fit_clean(
        self,
        df: pd.DataFrame,
        time_col: Optional[str] = None,
        amount_col: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        report: Dict[str, Any] = {
            "initial_rows": len(df),
            "initial_columns": len(df.columns),
            "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
            "duplicate_rows": int(df.duplicated().sum()),
        }
        df_cleaned = df.copy()

        # 1. Type coercion on amount column
        resolved_amount = self._resolve_col(df_cleaned, amount_col)
        if resolved_amount:
            df_cleaned[resolved_amount] = NumericTypeCoercer.coerce_numeric(df_cleaned[resolved_amount])

        # 2. Timestamp normalization
        resolved_time = self._resolve_col(df_cleaned, time_col)
        if resolved_time:
            df_cleaned[resolved_time] = TimestampNormalizer.normalize(
                df_cleaned[resolved_time],
                time_format=getattr(self.config, "time_format", "auto"),
            )

        # 3. Handle Duplicates
        if self.config.drop_duplicates:
            df_cleaned = df_cleaned.drop_duplicates()
            report["removed_duplicates"] = report["initial_rows"] - len(df_cleaned)
        else:
            report["removed_duplicates"] = 0

        # 4. Handle Missing Values (fit parameters on train)
        strat = self.config.missing_value_strategy
        if strat in (MissingValueStrategy.DROP, "drop"):
            df_cleaned = df_cleaned.dropna()
        elif strat in (MissingValueStrategy.MEAN, "mean"):
            means = df_cleaned.mean(numeric_only=True).to_dict()
            self.imputation_values_ = {k: float(v) for k, v in means.items()}
            df_cleaned = df_cleaned.fillna(self.imputation_values_)
        elif strat in (MissingValueStrategy.MEDIAN, "median"):
            medians = df_cleaned.median(numeric_only=True).to_dict()
            self.imputation_values_ = {k: float(v) for k, v in medians.items()}
            df_cleaned = df_cleaned.fillna(self.imputation_values_)
        elif strat in (MissingValueStrategy.CONSTANT, "constant") and self.config.fill_value is not None:
            self.imputation_values_ = self.config.fill_value
            df_cleaned = df_cleaned.fillna(self.config.fill_value)

        # 5. Outlier Clipping (fit bounds on train)
        if self.config.outlier_clipping and len(df_cleaned) > 0:
            num_cols = df_cleaned.select_dtypes(include=[np.number]).columns
            for col in num_cols:
                lower = float(df_cleaned[col].quantile(self.config.outlier_lower_percentile))
                upper = float(df_cleaned[col].quantile(self.config.outlier_upper_percentile))
                self.outlier_bounds_[str(col)] = (lower, upper)
                df_cleaned[col] = df_cleaned[col].clip(lower=lower, upper=upper)
            report["outlier_clipped"] = True

        report["final_rows"] = len(df_cleaned)
        report["final_columns"] = len(df_cleaned.columns)
        return df_cleaned, report

    def clean(
        self,
        df: pd.DataFrame,
        time_col: Optional[str] = None,
        amount_col: Optional[str] = None,
    ) -> pd.DataFrame:
        if df.empty:
            return df.copy()

        df_out = df.copy()

        # 1. Type coercion on amount
        resolved_amount = self._resolve_col(df_out, amount_col)
        if resolved_amount:
            df_out[resolved_amount] = NumericTypeCoercer.coerce_numeric(df_out[resolved_amount])

        # 2. Timestamp normalization
        resolved_time = self._resolve_col(df_out, time_col)
        if resolved_time:
            df_out[resolved_time] = TimestampNormalizer.normalize(
                df_out[resolved_time],
                time_format=getattr(self.config, "time_format", "auto"),
            )

        # 3. Missing value handling using learned parameters
        strat = self.config.missing_value_strategy
        if strat in (MissingValueStrategy.DROP, "drop"):
            df_out = df_out.dropna()
        elif self.imputation_values_:
            df_out = df_out.fillna(self.imputation_values_)

        # 4. Outlier clipping using learned bounds
        if self.outlier_bounds_:
            for col, (lower, upper) in self.outlier_bounds_.items():
                if col in df_out.columns:
                    df_out[col] = df_out[col].clip(lower=lower, upper=upper)

        return df_out

    def clean_and_validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, str, Dict[str, Any]]:
        df_cleaned, report = self.fit_clean(df)
        validation_status = "passed" if len(df_cleaned) > 0 else "failed"
        return df_cleaned, validation_status, report
