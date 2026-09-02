from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import CleansingConfig


class BaseDataCleanser(ABC):
    """Abstract base class for dataset cleansing and validation."""

    def __init__(self, config: CleansingConfig):
        self.config = config

    @abstractmethod
    def clean_and_validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, str, Dict[str, Any]]:
        """Cleans data and produces a validation quality report.

        Returns:
            Tuple of (cleaned_dataframe, validation_status, validation_report_dict)
        """
        pass
