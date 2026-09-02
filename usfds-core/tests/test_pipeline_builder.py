import unittest
from imblearn.pipeline import Pipeline
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import (
    CategoricalEncoderType,
    CleansingConfig,
    DimReductionConfig,
    DimReductionType,
    FeatureEngineeringConfig,
    PreprocessingConfig,
    ResamplingConfig,
    ResamplingStrategy,
    ScalerType,
    SplitConfig,
    TransformationConfig,
)
from usfds_core.services.preprocessing.pipeline_builder import PreprocessingPipelineBuilder


class TestPipelineBuilder(unittest.TestCase):
    def test_build_pipeline_and_fit_resample(self):
        config = PreprocessingConfig(
            cleansing=CleansingConfig(),
            split=SplitConfig(time_column="Time", target_column="Class"),
            feature_engineering=FeatureEngineeringConfig(
                time_col="Time",
                amount_col="Amount",
                enable_amount_ratios=True,
                enable_hour_of_day=True,
            ),
            transformation=TransformationConfig(
                numeric_columns=["Amount", "V1"],
                categorical_columns=[],
                scaler=ScalerType.ROBUST,
            ),
            dim_reduction=DimReductionConfig(method=DimReductionType.NONE),
            resampling=ResamplingConfig(method=ResamplingStrategy.SMOTE, random_state=42),
        )

        pipeline = PreprocessingPipelineBuilder.build(config)
        self.assertIsInstance(pipeline, Pipeline)

        # Verify pipeline execution on small sample dataset
        df = pd.DataFrame({
            "Time": [0, 3600, 7200, 10800, 14400, 18000, 21600, 25200, 28800, 32400, 36000, 39600, 43200, 46800, 50400, 54000],
            "Amount": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0],
            "V1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
        })
        # 10 negative samples, 6 positive samples (enough for SMOTE default k_neighbors=5)
        y = pd.Series([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1])

        # fit_resample will balance class 1 up to class 0
        X_res, y_res = pipeline.fit_resample(df, y)
        self.assertEqual(len(y_res[y_res == 1]), len(y_res[y_res == 0]))


if __name__ == "__main__":
    unittest.main()
