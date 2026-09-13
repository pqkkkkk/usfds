import unittest
from usfds_core.domain.schemas.preprocessing_config import (
    CleansingConfig,
    DataMappingConfig,
    FeatureEngineeringConfig,
    MissingValueStrategy,
    PreprocessingConfig,
    SplitConfig,
    SupportedTimeFormat,
    SystemColumn,
)


class TestPreprocessingConfigContracts(unittest.TestCase):
    def test_system_column_constants(self):
        self.assertEqual(SystemColumn.EVENT_ID, "event_id")
        self.assertEqual(SystemColumn.TIMESTAMP, "timestamp")
        self.assertEqual(SystemColumn.AMOUNT, "amount")
        self.assertEqual(SystemColumn.USER_ID, "user_id")
        self.assertEqual(SystemColumn.LABEL, "label")

    def test_data_mapping_config_defaults(self):
        config = DataMappingConfig()
        self.assertEqual(config.event_id_column, "event_id")
        self.assertEqual(config.time_column, "timestamp")
        self.assertEqual(config.amount_column, "amount")
        self.assertEqual(config.user_id_column, "user_id")
        self.assertEqual(config.target_column, "label")
        self.assertEqual(config.optional_columns, {})
        self.assertEqual(config.time_format, SupportedTimeFormat.AUTO)
        self.assertAlmostEqual(config.max_invalid_ratio_allowed, 0.3)

        full_map = config.get_full_column_mapping()
        self.assertEqual(full_map["event_id"], "event_id")
        self.assertEqual(full_map["timestamp"], "timestamp")
        self.assertEqual(full_map["amount"], "amount")
        self.assertEqual(full_map["user_id"], "user_id")
        self.assertEqual(full_map["label"], "label")

    def test_data_mapping_config_custom_and_full_mapping(self):
        config = DataMappingConfig(
            event_id_column="trans_id",
            time_column="tx_time",
            amount_column="tx_amt",
            user_id_column="cust_no",
            target_column="is_fraud",
            optional_columns={"ip_addr": "ip", "card_brand": "card_type"},
            time_format=SupportedTimeFormat.DATETIME_ISO,
            max_invalid_ratio_allowed=0.1,
        )
        self.assertEqual(config.event_id_column, "trans_id")
        self.assertEqual(config.time_column, "tx_time")
        self.assertEqual(config.amount_column, "tx_amt")
        self.assertEqual(config.user_id_column, "cust_no")
        self.assertEqual(config.target_column, "is_fraud")
        self.assertEqual(config.time_format, "%Y-%m-%d %H:%M:%S")

        full_map = config.get_full_column_mapping()
        self.assertEqual(full_map["trans_id"], SystemColumn.EVENT_ID.value)
        self.assertEqual(full_map["tx_time"], SystemColumn.TIMESTAMP.value)
        self.assertEqual(full_map["tx_amt"], SystemColumn.AMOUNT.value)
        self.assertEqual(full_map["cust_no"], SystemColumn.USER_ID.value)
        self.assertEqual(full_map["is_fraud"], SystemColumn.LABEL.value)
        self.assertEqual(full_map["ip_addr"], "ip")
        self.assertEqual(full_map["card_brand"], "card_type")

    def test_cleansing_config_defaults_and_drop_options(self):
        default_cfg = CleansingConfig()
        self.assertEqual(default_cfg.drop_columns, [])
        self.assertIsNone(default_cfg.drop_null_threshold)

        custom_cfg = CleansingConfig(
            drop_columns=["id", "notes"],
            drop_null_threshold=0.6,
        )
        self.assertEqual(custom_cfg.drop_columns, ["id", "notes"])
        self.assertEqual(custom_cfg.drop_null_threshold, 0.6)

    def test_feature_engineering_config_defaults(self):
        config = FeatureEngineeringConfig()
        self.assertIsInstance(config.split, SplitConfig)
        self.assertIsInstance(config.cleansing, CleansingConfig)
        self.assertEqual(config.time_col, SystemColumn.TIMESTAMP.value)
        self.assertEqual(config.amount_col, SystemColumn.AMOUNT.value)
        self.assertEqual(config.user_id_col, SystemColumn.USER_ID.value)
        self.assertEqual(config.customer_id_col, SystemColumn.USER_ID.value)  # backward compatible
        self.assertEqual(config.split.time_column, SystemColumn.TIMESTAMP.value)
        self.assertEqual(config.split.target_column, SystemColumn.LABEL.value)
        self.assertAlmostEqual(config.split.test_size, 0.2)
        self.assertTrue(config.cleansing.drop_duplicates)
        self.assertEqual(config.cleansing.missing_value_strategy, MissingValueStrategy.DROP)
        self.assertTrue(config.enable_amount_ratios)
        self.assertTrue(config.enable_hour_of_day)
        self.assertFalse(config.enable_velocity_features)
        self.assertEqual(config.velocity_windows, [1, 24, 168])

    def test_feature_engineering_config_custom(self):
        split_cfg = SplitConfig(time_column="timestamp", target_column="label", test_size=0.3)
        cleansing_cfg = CleansingConfig(missing_value_strategy=MissingValueStrategy.MEAN, outlier_clipping=True)
        fe_cfg = FeatureEngineeringConfig(
            split=split_cfg,
            cleansing=cleansing_cfg,
            user_id_col="user_id",
            enable_velocity_features=True,
            velocity_windows=[2, 12, 48],
        )
        self.assertEqual(fe_cfg.split.test_size, 0.3)
        self.assertEqual(fe_cfg.cleansing.missing_value_strategy, MissingValueStrategy.MEAN)
        self.assertTrue(fe_cfg.cleansing.outlier_clipping)
        self.assertTrue(fe_cfg.enable_velocity_features)
        self.assertEqual(fe_cfg.user_id_col, "user_id")
        self.assertEqual(fe_cfg.customer_id_col, "user_id")
        self.assertEqual(fe_cfg.velocity_windows, [2, 12, 48])

    def test_preprocessing_config_sync(self):
        prep_config = PreprocessingConfig(
            cleansing=CleansingConfig(missing_value_strategy=MissingValueStrategy.MEDIAN),
            split=SplitConfig(test_size=0.25),
        )
        self.assertEqual(prep_config.feature_engineering.cleansing.missing_value_strategy, MissingValueStrategy.MEDIAN)
        self.assertEqual(prep_config.feature_engineering.split.test_size, 0.25)


if __name__ == "__main__":
    unittest.main()
