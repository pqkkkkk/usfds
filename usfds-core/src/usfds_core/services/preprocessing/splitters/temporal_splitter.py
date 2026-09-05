from typing import Any, List, Optional, Tuple
import pandas as pd

from usfds_core.services.preprocessing.splitters.base_splitter import BaseDataSplitter


class TemporalDataSplitter(BaseDataSplitter):
    """Splits dataset chronologically based on a time column to prevent future data leakage (lookahead bias)."""

    def _resolve_col(
        self,
        df: pd.DataFrame,
        col_name: Optional[str],
        alias_groups: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Resolves column name with case-insensitivity and alias group matching."""
        if not col_name or not isinstance(df, pd.DataFrame):
            return None
        if col_name in df.columns:
            return col_name
        for c in df.columns:
            if str(c).lower() == str(col_name).lower():
                return str(c)
        # Only check alias group if col_name belongs to that alias group
        if alias_groups and any(str(col_name).lower() == a.lower() for a in alias_groups):
            for a in alias_groups:
                if a in df.columns:
                    return str(a)
                for c in df.columns:
                    if str(c).lower() == a.lower():
                        return str(c)
        return None

    def split_train_test(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Chronologically splits the full DataFrame into train and test sets, retaining all columns.

        Characteristics:
        - Keeps all original columns intact (features, target/label, event_id, user_id, timestamp...).
        - Chronologically sorts rows by `time_column` before splitting according to `test_size`,
          strictly preventing future data leakage into the training set.
        - Primary usage: Stage FEATURE_ENGINEERED (FeatureEngineeringExecutionService) to generate
          complete tabular datasets (train_enriched.parquet, test_enriched.parquet) for Rule Engine,
          Investigation Workspace, and downstream model pipelines.

        Args:
            df: Input pandas DataFrame to split.

        Returns:
            Tuple of (train_df, test_df) with reset index.
        """
        time_col = self._resolve_col(
            df,
            self.config.time_column,
            ["timestamp", "time", "datetime", "date_time", "tx_time"],
        )

        if time_col and time_col in df.columns:
            df_sorted = df.sort_values(by=time_col).reset_index(drop=True)
        else:
            df_sorted = df.reset_index(drop=True)

        if self.config.test_size <= 0:
            return df_sorted, pd.DataFrame(columns=df_sorted.columns)

        split_idx = int(len(df_sorted) * (1 - self.config.test_size))
        train_df = df_sorted.iloc[:split_idx].copy().reset_index(drop=True)
        test_df = df_sorted.iloc[split_idx:].copy().reset_index(drop=True)
        return train_df, test_df

    def split_features_target(
        self, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """Chronologically splits DataFrame into feature matrices and target series (X_train, X_test, y_train, y_test).

        Characteristics:
        - Separates the configured `target_column` from the feature matrix `X`, returning it as Series `y`.
        - Reuses the chronological partition logic from `split_train_test()`.
        - Primary usage: Stage PRE_PROCESSED (PreprocessingExecutionService) and model training pipelines
          following standard scikit-learn / imbalanced-learn interfaces (e.g. SMOTE resamplers, scalers).

        Args:
            df: Input pandas DataFrame to split.

        Returns:
            Tuple of (X_train, X_test, y_train, y_test).

        Raises:
            ValueError: If target_column is not found in DataFrame columns.
        """
        target_col = self._resolve_col(
            df,
            self.config.target_column,
            ["label", "class", "target", "is_fraud"],
        )
        if not target_col or target_col not in df.columns:
            raise ValueError(
                f"Target column '{self.config.target_column}' not found in dataset columns: {list(df.columns)}"
            )

        # Reuse chronological split logic from split_train_test
        train_df, test_df = self.split_train_test(df)

        X_train = train_df.drop(columns=[target_col])
        y_train = train_df[target_col]
        X_test = test_df.drop(columns=[target_col])
        y_test = test_df[target_col]
        return X_train, X_test, y_train, y_test



