from enum import StrEnum
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field, ValidationError

from usfds_core.domain.entities.enums import PipelineStage


class ArtifactOutputKey(StrEnum):
    """Canonical dictionary keys for dataset artifact output paths."""
    TRAIN = "train"
    TEST = "test"
    PIPELINE = "pipeline"
    FITTED_ENGINEERS = "fitted_engineers"
    RAW = "raw"
    MAPPED = "mapped"


class RawStageOutputs(BaseModel):
    """Expected outputs for RAW pipeline stage."""
    raw: str = Field(..., description="Path to the original raw dataset file.")

    def to_output_paths(self) -> Dict[str, str]:
        return {ArtifactOutputKey.RAW.value: self.raw}


class MappedStageOutputs(BaseModel):
    """Expected outputs for MAPPED pipeline stage."""
    mapped: str = Field(..., description="Path to the schema-standardized mapped dataset file.")

    def to_output_paths(self) -> Dict[str, str]:
        return {ArtifactOutputKey.MAPPED.value: self.mapped}


class FeatureEngineeredStageOutputs(BaseModel):
    """Expected outputs for FEATURE_ENGINEERED pipeline stage."""
    train: str = Field(..., description="Storage path to the feature-enriched training set.")
    fitted_engineers: str = Field(..., description="Storage path to the persisted feature engineers joblib artifact.")
    test: Optional[str] = Field(None, description="Storage path to the feature-enriched test set, if split.")

    def to_output_paths(self) -> Dict[str, str]:
        paths = {
            ArtifactOutputKey.TRAIN.value: self.train,
            ArtifactOutputKey.FITTED_ENGINEERS.value: self.fitted_engineers,
        }
        if self.test:
            paths[ArtifactOutputKey.TEST.value] = self.test
        return paths


class PreprocessedStageOutputs(BaseModel):
    """Expected outputs for PRE_PROCESSED pipeline stage."""
    train: str = Field(..., description="Storage path to the processed/transformed training parquet.")
    test: str = Field(..., description="Storage path to the processed/transformed testing parquet.")
    pipeline: str = Field(..., description="Storage path to the persisted scikit-learn pipeline joblib artifact.")

    def to_output_paths(self) -> Dict[str, str]:
        return {
            ArtifactOutputKey.TRAIN.value: self.train,
            ArtifactOutputKey.TEST.value: self.test,
            ArtifactOutputKey.PIPELINE.value: self.pipeline,
        }


STAGE_OUTPUT_SCHEMA_MAP: Dict[Union[PipelineStage, str], type[BaseModel]] = {
    PipelineStage.RAW: RawStageOutputs,
    "RAW": RawStageOutputs,
    PipelineStage.MAPPED: MappedStageOutputs,
    "MAPPED": MappedStageOutputs,
    PipelineStage.FEATURE_ENGINEERED: FeatureEngineeredStageOutputs,
    "FEATURE_ENGINEERED": FeatureEngineeredStageOutputs,
    PipelineStage.PRE_PROCESSED: PreprocessedStageOutputs,
    "PRE_PROCESSED": PreprocessedStageOutputs,
}


def validate_stage_outputs(stage: Union[PipelineStage, str], output_paths: Dict[str, str]) -> BaseModel:
    """Validates that output_paths conforms to the mandatory contract of the given pipeline stage.

    Raises:
        ValueError: If stage is unsupported or output_paths does not meet requirements.
    """
    schema_cls = STAGE_OUTPUT_SCHEMA_MAP.get(stage)
    if not schema_cls:
        raise ValueError(f"Unsupported pipeline stage for output validation: {stage}")

    try:
        return schema_cls.model_validate(output_paths)
    except ValidationError as err:
        raise ValueError(f"Invalid output_paths for stage '{stage}': {err}") from err


__all__ = [
    "ArtifactOutputKey",
    "RawStageOutputs",
    "MappedStageOutputs",
    "FeatureEngineeredStageOutputs",
    "PreprocessedStageOutputs",
    "STAGE_OUTPUT_SCHEMA_MAP",
    "validate_stage_outputs",
]
