from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import CleansingConfig


class BaseDataCleanser(ABC):
    """Abstract base class for dataset cleansing and validation."""

    def __init__(self, config: CleansingConfig):
        self.config = config

    # TODO: Implement time col validation
    # Receive time col name name and time col format
    # Then convert to unified datetime format before using it for aggregation further
    @abstractmethod
    def clean_and_validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, str, Dict[str, Any]]:
        """Cleans data and produces a validation quality report.

        Returns:
            Tuple of (cleaned_dataframe, validation_status, validation_report_dict)
        """
        pass

    def fit_clean(
        self,
        df: pd.DataFrame,
        time_col: Optional[str] = None,
        amount_col: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Learns cleansing parameters (mean/median, outlier bounds) on train data and cleans it."""
        cleaned_df, _, report = self.clean_and_validate(df)
        return cleaned_df, report

    def clean(
        self,
        df: pd.DataFrame,
        time_col: Optional[str] = None,
        amount_col: Optional[str] = None,
    ) -> pd.DataFrame:
        """Cleans test or inference data using learned parameters without leakage."""
        cleaned_df, _, _ = self.clean_and_validate(df)
        return cleaned_df
