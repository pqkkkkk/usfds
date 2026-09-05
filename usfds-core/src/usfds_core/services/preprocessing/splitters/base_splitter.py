from abc import ABC, abstractmethod
from typing import Tuple
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import SplitConfig


class BaseDataSplitter(ABC):
    """Abstract base class for dataset splitting strategies (temporal, stratified, random, etc.)."""

    def __init__(self, config: SplitConfig):
        self.config = config

    @abstractmethod
    def split_train_test(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Splits the full DataFrame into train and test sets, retaining all columns.

        Preserves all feature columns, identifiers (e.g. event_id, user_id, timestamp), and target/label.
        Used primarily in the FEATURE_ENGINEERED stage to persist full business-semantic tables
        (train_enriched.parquet, test_enriched.parquet) for Rule Engine and Investigation Workspace.

        Args:
            df: Input pandas DataFrame to split.

        Returns:
            Tuple of (train_df, test_df) with reset indices.
        """
        pass

    @abstractmethod
    def split_features_target(
        self, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """Splits DataFrame into feature matrices and target series: (X_train, X_test, y_train, y_test).

        Extracts and drops the target column from the feature sets, following standard
        scikit-learn / imbalanced-learn machine learning conventions.
        Used primarily in the PRE_PROCESSED stage and downstream model training pipelines.

        Args:
            df: Input pandas DataFrame to split.

        Returns:
            Tuple of (X_train, X_test, y_train, y_test).
        """
        pass


