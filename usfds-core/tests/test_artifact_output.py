import unittest

from usfds_core.domain.entities.enums import PipelineStage
from usfds_core.domain.schemas.artifact_output import (
    ArtifactOutputKey,
    FeatureEngineeredStageOutputs,
    MappedStageOutputs,
    PreprocessedStageOutputs,
    RawStageOutputs,
    validate_stage_outputs,
)


class TestArtifactOutputSchemas(unittest.TestCase):
    def test_raw_stage_outputs(self):
        raw = RawStageOutputs(raw="datasets/raw/data.csv")
        paths = raw.to_output_paths()
        self.assertEqual(paths, {"raw": "datasets/raw/data.csv"})

        validated = validate_stage_outputs(PipelineStage.RAW, paths)
        self.assertIsInstance(validated, RawStageOutputs)
        self.assertEqual(validated.raw, "datasets/raw/data.csv")

    def test_mapped_stage_outputs(self):
        mapped = MappedStageOutputs(mapped="datasets/mapped/data.parquet")
        paths = mapped.to_output_paths()
        self.assertEqual(paths, {"mapped": "datasets/mapped/data.parquet"})

        validated = validate_stage_outputs(PipelineStage.MAPPED, paths)
        self.assertIsInstance(validated, MappedStageOutputs)
        self.assertEqual(validated.mapped, "datasets/mapped/data.parquet")

    def test_feature_engineered_stage_outputs(self):
        fe = FeatureEngineeredStageOutputs(
            train="datasets/fe/train.parquet",
            test="datasets/fe/test.parquet",
            fitted_engineers="datasets/fe/fe.joblib",
        )
        paths = fe.to_output_paths()
        self.assertEqual(paths["train"], "datasets/fe/train.parquet")
        self.assertEqual(paths["test"], "datasets/fe/test.parquet")
        self.assertEqual(paths["fitted_engineers"], "datasets/fe/fe.joblib")

        validated = validate_stage_outputs(PipelineStage.FEATURE_ENGINEERED, paths)
        self.assertIsInstance(validated, FeatureEngineeredStageOutputs)
        self.assertEqual(validated.train, "datasets/fe/train.parquet")

    def test_preprocessed_stage_outputs(self):
        prep = PreprocessedStageOutputs(
            train="datasets/prep/train.parquet",
            test="datasets/prep/test.parquet",
            pipeline="datasets/prep/pipeline.joblib",
        )
        paths = prep.to_output_paths()
        self.assertEqual(paths["train"], "datasets/prep/train.parquet")
        self.assertEqual(paths["test"], "datasets/prep/test.parquet")
        self.assertEqual(paths["pipeline"], "datasets/prep/pipeline.joblib")

        validated = validate_stage_outputs(PipelineStage.PRE_PROCESSED, paths)
        self.assertIsInstance(validated, PreprocessedStageOutputs)
        self.assertEqual(validated.pipeline, "datasets/prep/pipeline.joblib")

    def test_validation_fails_on_missing_required_key(self):
        # Missing 'pipeline' key for PRE_PROCESSED stage
        invalid_prep_paths = {
            "train": "datasets/prep/train.parquet",
            "test": "datasets/prep/test.parquet",
        }
        with self.assertRaises(ValueError) as ctx:
            validate_stage_outputs(PipelineStage.PRE_PROCESSED, invalid_prep_paths)
        self.assertIn("Invalid output_paths for stage 'PRE_PROCESSED'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
