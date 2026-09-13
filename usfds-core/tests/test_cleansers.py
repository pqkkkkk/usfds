import unittest
import numpy as np
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import (
    CategoricalImputationStrategy,
    CleansingConfig,
    MissingValueStrategy,
    NumericalImputationStrategy,
)
from usfds_core.services.preprocessing.cleansers.standard_cleanser import StandardDataCleanser


class TestStandardDataCleanser(unittest.TestCase):
    def setUp(self):
        self.raw_data = pd.DataFrame({
            "Time": [100.0, 200.0, 200.0, 400.0, 500.0],
            "Amount": [10.0, np.nan, 20.0, 40.0, 1000.0],
            "Class": [0, 0, 0, 1, 0],
        })

    def test_drop_duplicates(self):
        df_with_dups = pd.DataFrame({
            "Time": [100, 100, 200],
            "Amount": [10, 10, 20],
            "Class": [0, 0, 1],
        })
        config = CleansingConfig(drop_duplicates=True, missing_value_strategy=MissingValueStrategy.NONE)
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(df_with_dups)

        self.assertEqual(len(cleaned_df), 2)
        self.assertEqual(report["removed_duplicates"], 1)
        self.assertEqual(status, "passed")

    def test_missing_value_drop(self):
        config = CleansingConfig(drop_duplicates=False, missing_value_strategy=MissingValueStrategy.DROP)
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(self.raw_data)

        self.assertEqual(len(cleaned_df), 4)
        self.assertFalse(cleaned_df["Amount"].isnull().any())
        self.assertEqual(status, "passed")

    def test_missing_value_mean(self):
        config = CleansingConfig(drop_duplicates=False, missing_value_strategy=MissingValueStrategy.MEAN)
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(self.raw_data)

        self.assertEqual(len(cleaned_df), 5)
        self.assertFalse(cleaned_df["Amount"].isnull().any())
        expected_mean = self.raw_data["Amount"].dropna().mean()
        self.assertAlmostEqual(cleaned_df.loc[1, "Amount"], expected_mean)

    def test_missing_value_constant(self):
        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.CONSTANT,
            fill_value=0.0,
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(self.raw_data)

        self.assertEqual(len(cleaned_df), 5)
        self.assertEqual(cleaned_df.loc[1, "Amount"], 0.0)

    def test_outlier_clipping(self):
        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.DROP,
            outlier_clipping=True,
            outlier_upper_percentile=0.90,
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(self.raw_data)

        self.assertTrue(report.get("outlier_clipped"))
        self.assertLess(cleaned_df["Amount"].max(), 1000.0)

    def test_drop_explicit_columns(self):
        df = self.raw_data.copy()
        df["unneeded_info"] = ["a", "b", "c", "d", "e"]
        df["legacy_code"] = [1, 2, 3, 4, 5]

        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.NONE,
            drop_columns=["unneeded_info", "legacy_code"],
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, report = cleanser.fit_clean(df, time_col="Time", amount_col="Amount")

        self.assertNotIn("unneeded_info", cleaned_df.columns)
        self.assertNotIn("legacy_code", cleaned_df.columns)
        self.assertIn("Time", cleaned_df.columns)
        self.assertIn("Amount", cleaned_df.columns)
        self.assertIn("unneeded_info", report["user_dropped_columns"])
        self.assertIn("legacy_code", report["user_dropped_columns"])
        self.assertEqual(len(cleaned_df), 5)

    def test_auto_drop_high_null_columns(self):
        df = pd.DataFrame({
            "Time": [100.0, 200.0, 300.0, 400.0, 500.0],
            "Amount": [10.0, 20.0, 30.0, 40.0, 50.0],
            "mostly_nan": [1.0, np.nan, np.nan, np.nan, 2.0],  # 3/5 = 60% NaN
            "mostly_empty_str": ["valid", "", "   ", "nan", "valid2"],  # 3/5 = 60% empty
            "few_nan": [1.0, np.nan, 3.0, 4.0, 5.0],  # 1/5 = 20% NaN -> should NOT be dropped
            "Class": [0, 0, 1, 0, 0],
        })

        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.NONE,
            drop_null_threshold=0.5,
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, report = cleanser.fit_clean(df, time_col="Time", amount_col="Amount", target_col="Class")

        self.assertNotIn("mostly_nan", cleaned_df.columns)
        self.assertNotIn("mostly_empty_str", cleaned_df.columns)
        self.assertIn("few_nan", cleaned_df.columns)
        self.assertIn("Time", cleaned_df.columns)
        self.assertIn("Amount", cleaned_df.columns)
        self.assertIn("Class", cleaned_df.columns)
        self.assertIn("mostly_nan", report["null_dropped_columns"])
        self.assertIn("mostly_empty_str", report["null_dropped_columns"])
        self.assertAlmostEqual(report["null_dropped_columns"]["mostly_nan"], 0.6)

    def test_protected_columns_not_auto_dropped(self):
        # Target/Time/Amount have > 50% null, but must NOT be dropped automatically
        df = pd.DataFrame({
            "Time": [100.0, np.nan, np.nan, np.nan, 500.0],  # 60% null
            "Amount": [np.nan, np.nan, np.nan, 40.0, 50.0],  # 60% null
            "Class": [0, np.nan, np.nan, np.nan, 1],  # 60% null
            "unprotected_high_null": [np.nan, np.nan, np.nan, 4.0, 5.0],  # 60% null -> SHOULD be dropped
        })

        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.NONE,
            drop_null_threshold=0.5,
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, report = cleanser.fit_clean(df, time_col="Time", amount_col="Amount", target_col="Class")

        self.assertIn("Time", cleaned_df.columns)
        self.assertIn("Amount", cleaned_df.columns)
        self.assertIn("Class", cleaned_df.columns)
        self.assertNotIn("unprotected_high_null", cleaned_df.columns)

    def test_explicit_target_drop_raises_error(self):
        df = self.raw_data.copy()
        config = CleansingConfig(drop_columns=["Class"])
        cleanser = StandardDataCleanser(config)
        with self.assertRaises(ValueError):
            cleanser.fit_clean(df, target_col="Class")

    def test_clean_applies_learned_dropped_columns_to_test(self):
        train_df = pd.DataFrame({
            "Time": [1.0, 2.0, 3.0, 4.0],
            "feat_trash": [np.nan, np.nan, np.nan, 1.0],  # 75% null -> dropped
            "feat_good": [1.0, 2.0, 3.0, 4.0],
            "Class": [0, 0, 1, 0],
        })
        # Test set does not have nulls in feat_trash, but feat_trash must still be dropped!
        test_df = pd.DataFrame({
            "Time": [5.0, 6.0],
            "feat_trash": [10.0, 20.0],
            "feat_good": [5.0, 6.0],
            "Class": [0, 1],
        })

        config = CleansingConfig(drop_null_threshold=0.5, missing_value_strategy=MissingValueStrategy.NONE)
        cleanser = StandardDataCleanser(config)
        train_clean, _ = cleanser.fit_clean(train_df, time_col="Time", target_col="Class")
        test_clean = cleanser.clean(test_df, time_col="Time", target_col="Class")

        self.assertNotIn("feat_trash", train_clean.columns)
        self.assertNotIn("feat_trash", test_clean.columns)
        self.assertEqual(list(train_clean.columns), list(test_clean.columns))

    def test_drop_high_null_col_prevents_row_loss(self):
        # A dataset where a bad column has 80% nulls. If not dropped, dropna() would lose 80% of rows!
        df = pd.DataFrame({
            "Time": [1.0, 2.0, 3.0, 4.0, 5.0],
            "Amount": [10.0, 20.0, 30.0, 40.0, 50.0],
            "bad_feature": [np.nan, np.nan, np.nan, np.nan, "only_one"],  # 80% null
            "Class": [0, 0, 1, 0, 0],
        })

        # With drop_null_threshold=0.5 and missing_value_strategy=DROP:
        config = CleansingConfig(
            drop_duplicates=False,
            drop_null_threshold=0.5,
            missing_value_strategy=MissingValueStrategy.DROP,
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, report = cleanser.fit_clean(df, time_col="Time", amount_col="Amount", target_col="Class")

        # All 5 rows must be retained because bad_feature was dropped before dropna()!
        self.assertEqual(len(cleaned_df), 5)
        self.assertNotIn("bad_feature", cleaned_df.columns)
        self.assertEqual(report["final_rows"], 5)

    def test_mixed_type_imputation_constant(self):
        df = pd.DataFrame({
            "Time": [1.0, 2.0, 3.0],
            "Amount": [10.0, np.nan, 30.0],
            "Channel": ["web", np.nan, "mobile"],
            "Class": [0, 1, 0],
        })
        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.IMPUTE,
            num_impute_strategy=NumericalImputationStrategy.CONSTANT,
            num_fill_value=-999.0,
            cat_impute_strategy=CategoricalImputationStrategy.CONSTANT,
            cat_fill_value="missing",
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, report = cleanser.fit_clean(df, time_col="Time", amount_col="Amount", target_col="Class")

        # 0 rows dropped!
        self.assertEqual(len(cleaned_df), 3)
        # Check numerical column filled with -999.0 and preserves numeric dtype
        self.assertEqual(cleaned_df.loc[1, "Amount"], -999.0)
        self.assertTrue(pd.api.types.is_numeric_dtype(cleaned_df["Amount"]))
        # Check categorical column filled with 'missing' and preserves string/object dtype
        self.assertEqual(cleaned_df.loc[1, "Channel"], "missing")
        self.assertFalse(cleaned_df["Channel"].isnull().any())
        self.assertIn("imputation_details", report)
        self.assertEqual(report["imputation_details"]["imputed_columns_count"], 4)

    def test_mixed_type_imputation_median_and_mode(self):
        df = pd.DataFrame({
            "Time": [1.0, 2.0, 3.0, 4.0],
            "Amount": [10.0, 20.0, np.nan, 40.0],  # median of [10, 20, 40] = 20.0
            "Channel": ["web", "web", np.nan, "mobile"],  # mode = 'web'
            "Class": [0, 0, 1, 0],
        })
        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.IMPUTE,
            num_impute_strategy=NumericalImputationStrategy.MEDIAN,
            cat_impute_strategy=CategoricalImputationStrategy.MODE,
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, report = cleanser.fit_clean(df, time_col="Time", amount_col="Amount", target_col="Class")

        self.assertEqual(len(cleaned_df), 4)
        self.assertEqual(cleaned_df.loc[2, "Amount"], 20.0)
        self.assertEqual(cleaned_df.loc[2, "Channel"], "web")

    def test_clean_applies_learned_mixed_imputation(self):
        train_df = pd.DataFrame({
            "Time": [1.0, 2.0, 3.0],
            "Amount": [10.0, 20.0, 30.0],
            "Channel": ["app", "app", "web"],
            "Class": [0, 1, 0],
        })
        test_df = pd.DataFrame({
            "Time": [4.0, 5.0],
            "Amount": [np.nan, 50.0],  # should get train median: 20.0
            "Channel": [np.nan, "web"],  # should get train mode: 'app'
            "Class": [0, 1],
        })
        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.IMPUTE,
            num_impute_strategy=NumericalImputationStrategy.MEDIAN,
            cat_impute_strategy=CategoricalImputationStrategy.MODE,
        )
        cleanser = StandardDataCleanser(config)
        train_clean, _ = cleanser.fit_clean(train_df, time_col="Time", amount_col="Amount", target_col="Class")
        test_clean = cleanser.clean(test_df, time_col="Time", amount_col="Amount", target_col="Class")

        self.assertEqual(len(test_clean), 2)
        self.assertEqual(test_clean.loc[0, "Amount"], 20.0)
        self.assertEqual(test_clean.loc[0, "Channel"], "app")


if __name__ == "__main__":
    unittest.main()
