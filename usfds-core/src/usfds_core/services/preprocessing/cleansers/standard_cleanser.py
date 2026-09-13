from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import (
    CategoricalImputationStrategy,
    MissingValueStrategy,
    NumericalImputationStrategy,
)
from usfds_core.services.preprocessing.cleansers.base_cleanser import BaseDataCleanser
from usfds_core.services.preprocessing.cleansers.timestamp_normalizer import TimestampNormalizer
from usfds_core.services.preprocessing.cleansers.type_coercer import NumericTypeCoercer


class StandardDataCleanser(BaseDataCleanser):
    """Stateful implementation for data cleansing, column pruning, type coercion,
    timestamp normalization, and imputation."""

    def __init__(self, config):
        super().__init__(config)
        self.imputation_values_: Dict[str, Any] = {}
        self.outlier_bounds_: Dict[str, Tuple[float, float]] = {}
        self.dropped_columns_: List[str] = []

    def _resolve_col(self, df: pd.DataFrame, col_name: Optional[str]) -> Optional[str]:
        if not col_name or not isinstance(df, pd.DataFrame):
            return None
        if col_name in df.columns:
            return col_name
        for c in df.columns:
            if str(c).lower() == str(col_name).lower():
                return c
        return None

    @staticmethod
    def _compute_null_empty_ratio(series: pd.Series) -> float:
        """Calculates the ratio of null/NaN/NaT values as well as empty/whitespace strings."""
        if len(series) == 0:
            return 0.0
        null_mask = series.isna()
        if series.dtype == "object" or isinstance(series.dtype, pd.StringDtype):
            non_null_vals = series[~null_mask]
            if len(non_null_vals) > 0:
                str_series = non_null_vals.astype(str).str.strip().str.lower()
                empty_mask = str_series.isin(["", "nan", "null", "none", "<na>", "n/a"])
                total_missing = int(null_mask.sum() + empty_mask.sum())
            else:
                total_missing = int(null_mask.sum())
        else:
            total_missing = int(null_mask.sum())
        return total_missing / len(series)

    def fit_clean(
        self,
        df: pd.DataFrame,
        time_col: Optional[str] = None,
        amount_col: Optional[str] = None,
        target_col: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        report: Dict[str, Any] = {
            "initial_rows": len(df),
            "initial_columns": len(df.columns),
            "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
            "duplicate_rows": int(df.duplicated().sum()),
            "dropped_columns": [],
            "user_dropped_columns": [],
            "null_dropped_columns": {},
        }
        df_cleaned = df.copy()

        # Identify protected core columns (never auto-drop these)
        resolved_amount = self._resolve_col(df_cleaned, amount_col)
        resolved_time = self._resolve_col(df_cleaned, time_col)
        resolved_target = self._resolve_col(df_cleaned, target_col)
        protected_cols = {c for c in [resolved_time, resolved_amount, resolved_target] if c}

        # 1. Prune Unnecessary Columns
        # 1a. User-specified columns
        user_drop_candidates = getattr(self.config, "drop_columns", []) or []
        user_dropped_cols: List[str] = []
        for u_col in user_drop_candidates:
            resolved = self._resolve_col(df_cleaned, u_col)
            if resolved:
                if resolved_target and resolved == resolved_target:
                    raise ValueError(
                        f"Cannot drop target column '{resolved_target}' as it is essential for model training."
                    )
                user_dropped_cols.append(resolved)

        # 1b. Auto-detect high null / empty columns
        drop_threshold = getattr(self.config, "drop_null_threshold", None)

        null_dropped_cols: Dict[str, float] = {}
        if drop_threshold is not None:
            threshold = float(drop_threshold)
            for col in df_cleaned.columns:
                if col in protected_cols or col in user_dropped_cols:
                    continue
                ratio = self._compute_null_empty_ratio(df_cleaned[col])
                if ratio > threshold or (threshold >= 1.0 and ratio >= 1.0):
                    null_dropped_cols[str(col)] = round(ratio, 4)

        all_to_drop = sorted(list(set(user_dropped_cols + list(null_dropped_cols.keys()))))
        self.dropped_columns_ = all_to_drop
        if self.dropped_columns_:
            df_cleaned = df_cleaned.drop(columns=self.dropped_columns_, errors="ignore")

        report["dropped_columns"] = self.dropped_columns_
        report["user_dropped_columns"] = user_dropped_cols
        report["null_dropped_columns"] = null_dropped_cols

        # 2. Type coercion on amount column
        resolved_amount = self._resolve_col(df_cleaned, amount_col)
        if resolved_amount:
            df_cleaned[resolved_amount] = NumericTypeCoercer.coerce_numeric(df_cleaned[resolved_amount])

        # 3. Timestamp normalization
        resolved_time = self._resolve_col(df_cleaned, time_col)
        if resolved_time:
            df_cleaned[resolved_time] = TimestampNormalizer.normalize(
                df_cleaned[resolved_time],
                time_format=getattr(self.config, "time_format", "auto"),
            )

        # 4. Handle Duplicates
        if self.config.drop_duplicates:
            df_cleaned = df_cleaned.drop_duplicates()
            report["removed_duplicates"] = report["initial_rows"] - len(df_cleaned)
        else:
            report["removed_duplicates"] = 0

        # 5. Handle Missing Values (fit parameters on train)
        strat = self.config.missing_value_strategy
        num_strat = getattr(self.config, "num_impute_strategy", None)
        cat_strat = getattr(self.config, "cat_impute_strategy", None)

        if strat in (MissingValueStrategy.DROP, "drop"):
            df_cleaned = df_cleaned.dropna()
        elif strat in (MissingValueStrategy.NONE, "none") and not (num_strat or cat_strat):
            pass
        else:
            num_cols = df_cleaned.select_dtypes(include=[np.number]).columns
            cat_cols = df_cleaned.select_dtypes(exclude=[np.number]).columns

            # Resolve effective numerical strategy
            if num_strat is None:
                if strat in (MissingValueStrategy.MEAN, "mean"):
                    num_strat = NumericalImputationStrategy.MEAN
                elif strat in (MissingValueStrategy.MEDIAN, "median"):
                    num_strat = NumericalImputationStrategy.MEDIAN
                elif strat in (MissingValueStrategy.CONSTANT, "constant"):
                    num_strat = NumericalImputationStrategy.CONSTANT
                elif strat in (MissingValueStrategy.IMPUTE, "impute"):
                    num_strat = NumericalImputationStrategy.CONSTANT
                else:
                    num_strat = NumericalImputationStrategy.NONE

            # Resolve effective categorical strategy
            if cat_strat is None:
                if strat in (MissingValueStrategy.MEAN, "mean", MissingValueStrategy.MEDIAN, "median"):
                    cat_strat = CategoricalImputationStrategy.MODE
                elif strat in (MissingValueStrategy.CONSTANT, "constant"):
                    cat_strat = CategoricalImputationStrategy.CONSTANT
                elif strat in (MissingValueStrategy.IMPUTE, "impute"):
                    cat_strat = CategoricalImputationStrategy.CONSTANT
                else:
                    cat_strat = CategoricalImputationStrategy.NONE

            imputation_dict: Dict[str, Any] = {}

            # Numerical columns imputation
            if num_strat in (NumericalImputationStrategy.MEAN, "mean"):
                means = df_cleaned[num_cols].mean(numeric_only=True).to_dict()
                default_num = getattr(self.config, "num_fill_value", -999.0)
                num_fallback = float(default_num) if default_num is not None else -999.0
                for k, v in means.items():
                    imputation_dict[k] = float(v) if pd.notnull(v) else num_fallback
            elif num_strat in (NumericalImputationStrategy.MEDIAN, "median"):
                medians = df_cleaned[num_cols].median(numeric_only=True).to_dict()
                default_num = getattr(self.config, "num_fill_value", -999.0)
                num_fallback = float(default_num) if default_num is not None else -999.0
                for k, v in medians.items():
                    imputation_dict[k] = float(v) if pd.notnull(v) else num_fallback
            elif num_strat in (NumericalImputationStrategy.CONSTANT, "constant"):
                if self.config.fill_value is not None and isinstance(self.config.fill_value, (int, float)):
                    num_val = float(self.config.fill_value)
                elif getattr(self.config, "num_fill_value", None) is not None:
                    num_val = float(self.config.num_fill_value)
                else:
                    num_val = -999.0
                for col in num_cols:
                    imputation_dict[col] = num_val

            # Categorical columns imputation
            if cat_strat in (CategoricalImputationStrategy.MODE, "mode", CategoricalImputationStrategy.MOST_FREQUENT, "most_frequent"):
                fallback_cat = getattr(self.config, "cat_fill_value", "missing") or "missing"
                for col in cat_cols:
                    modes = df_cleaned[col].mode(dropna=True)
                    if not modes.empty:
                        imputation_dict[col] = modes.iloc[0]
                    else:
                        imputation_dict[col] = fallback_cat
            elif cat_strat in (CategoricalImputationStrategy.CONSTANT, "constant"):
                if self.config.fill_value is not None and isinstance(self.config.fill_value, str):
                    cat_val = self.config.fill_value
                elif getattr(self.config, "cat_fill_value", None) is not None:
                    cat_val = str(self.config.cat_fill_value)
                else:
                    cat_val = "missing"
                for col in cat_cols:
                    imputation_dict[col] = cat_val

            # Direct dictionary override if fill_value is provided as a dict
            if isinstance(self.config.fill_value, dict):
                imputation_dict.update(self.config.fill_value)

            self.imputation_values_ = imputation_dict
            if self.imputation_values_:
                df_cleaned = df_cleaned.fillna(self.imputation_values_)

            report["imputation_details"] = {
                "numerical_strategy": str(num_strat),
                "categorical_strategy": str(cat_strat),
                "imputed_columns_count": len(self.imputation_values_),
            }

        # 6. Outlier Clipping (fit bounds on train)
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
        target_col: Optional[str] = None,
    ) -> pd.DataFrame:
        if df.empty:
            return df.copy()

        df_out = df.copy()

        # 1. Prune columns learned during fit_clean
        if self.dropped_columns_:
            cols_to_drop = [c for c in self.dropped_columns_ if c in df_out.columns]
            if cols_to_drop:
                df_out = df_out.drop(columns=cols_to_drop, errors="ignore")

        # 2. Type coercion on amount
        resolved_amount = self._resolve_col(df_out, amount_col)
        if resolved_amount:
            df_out[resolved_amount] = NumericTypeCoercer.coerce_numeric(df_out[resolved_amount])

        # 3. Timestamp normalization
        resolved_time = self._resolve_col(df_out, time_col)
        if resolved_time:
            df_out[resolved_time] = TimestampNormalizer.normalize(
                df_out[resolved_time],
                time_format=getattr(self.config, "time_format", "auto"),
            )

        # 4. Missing value handling using learned parameters
        strat = self.config.missing_value_strategy
        if strat in (MissingValueStrategy.DROP, "drop"):
            df_out = df_out.dropna()
        elif self.imputation_values_:
            if isinstance(self.imputation_values_, dict):
                cols_to_fill = {k: v for k, v in self.imputation_values_.items() if k in df_out.columns}
                df_out = df_out.fillna(cols_to_fill)
            else:
                df_out = df_out.fillna(self.imputation_values_)

        # 5. Outlier clipping using learned bounds
        if self.outlier_bounds_:
            for col, (lower, upper) in self.outlier_bounds_.items():
                if col in df_out.columns:
                    df_out[col] = df_out[col].clip(lower=lower, upper=upper)

        return df_out

    def clean_and_validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, str, Dict[str, Any]]:
        df_cleaned, report = self.fit_clean(df)
        validation_status = "passed" if len(df_cleaned) > 0 and len(df_cleaned.columns) > 0 else "failed"
        return df_cleaned, validation_status, report
