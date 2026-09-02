from typing import Tuple
import pandas as pd

from usfds_core.services.preprocessing.splitters.base_splitter import BaseDataSplitter


class TemporalDataSplitter(BaseDataSplitter):
    """Splits dataset chronologically based on a time column to prevent future data leakage."""

    def split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        target_col = self.config.target_column
        time_col = self.config.time_column

        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataset columns: {list(df.columns)}")

        if time_col and time_col in df.columns:
            df_sorted = df.sort_values(by=time_col).reset_index(drop=True)
        else:
            df_sorted = df.reset_index(drop=True)

        split_idx = int(len(df_sorted) * (1 - self.config.test_size))
        train_df = df_sorted.iloc[:split_idx]
        test_df = df_sorted.iloc[split_idx:]

        X_train = train_df.drop(columns=[target_col])
        y_train = train_df[target_col]
        X_test = test_df.drop(columns=[target_col])
        y_test = test_df[target_col]
        return X_train, X_test, y_train, y_test
