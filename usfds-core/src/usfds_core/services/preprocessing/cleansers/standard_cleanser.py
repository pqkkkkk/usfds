from typing import Any, Dict, Tuple
import numpy as np
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import MissingValueStrategy
from usfds_core.services.preprocessing.cleansers.base_cleanser import BaseDataCleanser


class StandardDataCleanser(BaseDataCleanser):
    """Standard implementation for missing value imputation, duplicate removal, and validation reporting."""

    def clean_and_validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, str, Dict[str, Any]]:
        report: Dict[str, Any] = {
            "initial_rows": len(df),
            "initial_columns": len(df.columns),
            "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
            "duplicate_rows": int(df.duplicated().sum()),
        }
        df_cleaned = df.copy()

        # 1. Handle Duplicates
        if self.config.drop_duplicates:
            df_cleaned = df_cleaned.drop_duplicates()
            report["removed_duplicates"] = report["initial_rows"] - len(df_cleaned)
        else:
            report["removed_duplicates"] = 0

        # 2. Handle Missing Values
        strat = self.config.missing_value_strategy
        if strat in (MissingValueStrategy.DROP, "drop"):
            df_cleaned = df_cleaned.dropna()
        elif strat in (MissingValueStrategy.MEAN, "mean"):
            df_cleaned = df_cleaned.fillna(df_cleaned.mean(numeric_only=True))
        elif strat in (MissingValueStrategy.MEDIAN, "median"):
            df_cleaned = df_cleaned.fillna(df_cleaned.median(numeric_only=True))
        elif strat in (MissingValueStrategy.CONSTANT, "constant") and self.config.fill_value is not None:
            df_cleaned = df_cleaned.fillna(self.config.fill_value)

        # 3. Optional Outlier Clipping
        if self.config.outlier_clipping and len(df_cleaned) > 0:
            num_cols = df_cleaned.select_dtypes(include=[np.number]).columns
            if len(num_cols) > 0:
                lower = df_cleaned[num_cols].quantile(self.config.outlier_lower_percentile)
                upper = df_cleaned[num_cols].quantile(self.config.outlier_upper_percentile)
                df_cleaned[num_cols] = df_cleaned[num_cols].clip(lower=lower, upper=upper, axis=1)
                report["outlier_clipped"] = True

        report["final_rows"] = len(df_cleaned)
        report["final_columns"] = len(df_cleaned.columns)
        validation_status = "passed" if len(df_cleaned) > 0 else "failed"
        return df_cleaned, validation_status, report
