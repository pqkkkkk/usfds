from abc import ABC, abstractmethod
from typing import Tuple
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import SplitConfig


class BaseDataSplitter(ABC):
    """Abstract base class for dataset train/test splitting."""

    def __init__(self, config: SplitConfig):
        self.config = config

    @abstractmethod
    def split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """Splits the dataframe into X_train, X_test, y_train, y_test.

        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        pass
