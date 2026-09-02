from enum import StrEnum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class MissingValueStrategy(StrEnum):
    DROP = "drop"
    MEAN = "mean"
    MEDIAN = "median"
    CONSTANT = "constant"
    NONE = "none"


class ScalerType(StrEnum):
    NONE = "none"
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"
    LOG1P = "log1p"


class CategoricalEncoderType(StrEnum):
    NONE = "none"
    ONE_HOT = "one_hot"
    BINARY = "binary"
    ORDINAL = "ordinal"


class DimReductionType(StrEnum):
    NONE = "none"
    PCA = "pca"
    SELECT_K_BEST_MI = "select_k_best_mi"
    SELECT_K_BEST_F2 = "select_k_best_f2"
    RFE = "rfe"
    UMAP = "umap"


class ResamplingStrategy(StrEnum):
    NONE = "none"
    SMOTE = "smote"
    ADASYN = "adasyn"
    RANDOM_UNDERSAMPLING = "random_undersampling"
    TOMEK_LINKS = "tomek_links"
    SMOTE_TOMEK = "smote_tomek"
    SMOTE_ENN = "smote_enn"


class CleansingConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    drop_duplicates: bool = True
    missing_value_strategy: Union[MissingValueStrategy, str] = MissingValueStrategy.DROP
    fill_value: Optional[Any] = None
    outlier_clipping: bool = False
    outlier_lower_percentile: float = 0.01
    outlier_upper_percentile: float = 0.99


class SplitConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time_column: Optional[str] = "Time"
    target_column: str = "Class"
    test_size: float = 0.2
    val_size: Optional[float] = None


class FeatureEngineeringConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time_col: Optional[str] = "Time"
    amount_col: Optional[str] = "Amount"
    enable_amount_ratios: bool = True
    enable_hour_of_day: bool = True
    enable_velocity_features: bool = False
    customer_id_col: Optional[str] = None
    velocity_windows: List[int] = Field(default_factory=lambda: [1, 24, 168])


class TransformationConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    numeric_columns: List[str] = Field(default_factory=list)
    categorical_columns: List[str] = Field(default_factory=list)
    scaler: Union[ScalerType, str] = ScalerType.ROBUST
    categorical_encoder: Union[CategoricalEncoderType, str] = CategoricalEncoderType.ONE_HOT


class DimReductionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    method: Union[DimReductionType, str] = DimReductionType.NONE
    n_components: Optional[int] = 10
    k_features: Optional[int] = 15


class ResamplingConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    method: Union[ResamplingStrategy, str] = ResamplingStrategy.NONE
    sampling_strategy: Union[float, str, Dict[str, Any]] = "auto"
    random_state: Optional[int] = 42


class PreprocessingConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cleansing: CleansingConfig = Field(default_factory=CleansingConfig)
    split: SplitConfig = Field(default_factory=SplitConfig)
    feature_engineering: FeatureEngineeringConfig = Field(default_factory=FeatureEngineeringConfig)
    transformation: TransformationConfig = Field(default_factory=TransformationConfig)
    dim_reduction: DimReductionConfig = Field(default_factory=DimReductionConfig)
    resampling: ResamplingConfig = Field(default_factory=ResamplingConfig)
