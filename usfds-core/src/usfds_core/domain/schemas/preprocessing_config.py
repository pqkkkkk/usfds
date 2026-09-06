from enum import StrEnum
from typing import Any, Dict, List, Optional, Set, Union
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


class SystemColumn(StrEnum):
    """Canonical system column names for transactional/fraud detection datasets."""
    EVENT_ID = "event_id"
    TIMESTAMP = "timestamp"
    AMOUNT = "amount"
    USER_ID = "user_id"
    LABEL = "label"


class SupportedTimeFormat(StrEnum):
    """Supported datetime formats for timestamp parsing and normalization."""
    AUTO = "auto"
    EPOCH_SECONDS = "epoch_s"
    EPOCH_MILLIS = "epoch_ms"
    ISO8601 = "iso"
    DATETIME_ISO = "%Y-%m-%d %H:%M:%S"
    DATE_ONLY = "%Y-%m-%d"
    DATETIME_SLASH_DMY = "%d/%m/%Y %H:%M:%S"
    DATETIME_SLASH_MDY = "%m/%d/%Y %H:%M:%S"


# Columns that represent metadata/identifiers/labels and must be excluded from ML mathematical features
NON_ML_COLUMNS: Set[str] = {
    SystemColumn.EVENT_ID.value,
    SystemColumn.TIMESTAMP.value,
    SystemColumn.USER_ID.value,
    SystemColumn.LABEL.value,
    "time",
    "datetime",
    "date_time",
    "tx_time",
    "customer_id",
    "client_id",
    "account_id",
    "class",
    "target",
    "is_fraud",
}


class CleansingConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    drop_duplicates: bool = True
    missing_value_strategy: Union[MissingValueStrategy, str] = MissingValueStrategy.DROP
    fill_value: Optional[Any] = None
    outlier_clipping: bool = False
    outlier_lower_percentile: float = 0.01
    outlier_upper_percentile: float = 0.99
    time_format: Optional[str] = SupportedTimeFormat.AUTO.value


class SplitConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time_column: Optional[str] = SystemColumn.TIMESTAMP.value
    target_column: str = SystemColumn.LABEL.value
    test_size: float = 0.2
    val_size: Optional[float] = None


class DataMappingConfig(BaseModel):
    """Configuration for raw data schema mapping and initial validation (Stage: MAPPED).

    Attributes:
        event_id_column: Raw column name representing transaction/event ID -> maps to system 'event_id'.
        time_column: Raw column name representing transaction timestamp -> maps to system 'timestamp'.
        amount_column: Raw column name representing transaction amount -> maps to system 'amount'.
        user_id_column: Raw column name representing user/account identifier -> maps to system 'user_id'.
        target_column: Raw column name representing fraud label/class -> maps to system 'label'.
        optional_columns: Dictionary mapping optional/domain columns {raw_col_name: target_col_name}.
                         Any column not in core mappings or optional_columns is automatically dropped.
        time_format: Expected datetime format hint (e.g. 'auto', 'epoch_s', 'epoch_ms', 'iso', or custom format).
        max_invalid_ratio_allowed: Error ratio threshold to fail validation instead of issuing warnings.
    """
    model_config = ConfigDict(extra="ignore")

    event_id_column: str = Field(
        default=SystemColumn.EVENT_ID.value,
        description="Raw column name mapping to system 'event_id'"
    )
    time_column: str = Field(
        default=SystemColumn.TIMESTAMP.value,
        description="Raw column name mapping to system 'timestamp'"
    )
    amount_column: str = Field(
        default=SystemColumn.AMOUNT.value,
        description="Raw column name mapping to system 'amount'"
    )
    user_id_column: Optional[str] = Field(
        default=SystemColumn.USER_ID.value,
        description="Raw column name mapping to system 'user_id'"
    )
    target_column: Optional[str] = Field(
        default=SystemColumn.LABEL.value,
        description="Raw column name mapping to system 'label' (None for inference data)"
    )
    optional_columns: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of optional domain columns {raw_col_name: target_col_name}. Unmapped columns are dropped."
    )
    time_format: Union[SupportedTimeFormat, str] = Field(
        default=SupportedTimeFormat.AUTO,
        description="Expected datetime format hint ('auto', 'epoch_s', 'epoch_ms', 'iso', or custom format)"
    )
    max_invalid_ratio_allowed: float = Field(
        default=0.3,
        description="Threshold ratio of corrupted/unparseable values before marking ValidationStatus as FAILED instead of WARNING."
    )

    def get_full_column_mapping(self) -> Dict[str, str]:
        """Returns the full mapping dictionary: {raw_column_name: system_canonical_column_name}."""
        mapping: Dict[str, str] = {}
        if self.event_id_column:
            mapping[self.event_id_column] = SystemColumn.EVENT_ID.value
        if self.time_column:
            mapping[self.time_column] = SystemColumn.TIMESTAMP.value
        if self.amount_column:
            mapping[self.amount_column] = SystemColumn.AMOUNT.value
        if self.user_id_column:
            mapping[self.user_id_column] = SystemColumn.USER_ID.value
        if self.target_column:
            mapping[self.target_column] = SystemColumn.LABEL.value
        mapping.update(self.optional_columns)
        return mapping


class FeatureEngineeringConfig(BaseModel):
    """Configuration for data splitting, cleansing, and domain feature generation in Stage FEATURE_ENGINEERED."""
    model_config = ConfigDict(extra="ignore")

    # 1. Temporal Split Configuration (executed first to prevent data leakage)
    split: SplitConfig = Field(default_factory=SplitConfig)

    # 2. Cleansing Configuration (fitted on train, applied to test)
    cleansing: CleansingConfig = Field(default_factory=CleansingConfig)

    # 3. Domain Feature Engineering Parameters (referencing system canonical columns)
    time_col: Optional[str] = SystemColumn.TIMESTAMP.value
    amount_col: Optional[str] = SystemColumn.AMOUNT.value
    user_id_col: Optional[str] = SystemColumn.USER_ID.value
    enable_amount_ratios: bool = True
    enable_hour_of_day: bool = True
    enable_velocity_features: bool = False
    velocity_windows: List[int] = Field(default_factory=lambda: [1, 24, 168])

    @property
    def customer_id_col(self) -> Optional[str]:
        """Backward-compatible property for customer_id_col."""
        return self.user_id_col

    def model_post_init(self, __context: Any) -> None:
        extra = getattr(self, "__pydantic_extra__", None) or {}
        if "customer_id_col" in extra and extra["customer_id_col"]:
            self.user_id_col = extra["customer_id_col"]


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
    """End-to-end preprocessing configuration covering all stages (MAPPED, FEATURE_ENGINEERED, PRE_PROCESSED)."""
    model_config = ConfigDict(extra="ignore")

    data_mapping: DataMappingConfig = Field(default_factory=DataMappingConfig)
    cleansing: CleansingConfig = Field(default_factory=CleansingConfig)
    split: SplitConfig = Field(default_factory=SplitConfig)
    feature_engineering: FeatureEngineeringConfig = Field(default_factory=FeatureEngineeringConfig)
    transformation: TransformationConfig = Field(default_factory=TransformationConfig)
    dim_reduction: DimReductionConfig = Field(default_factory=DimReductionConfig)
    resampling: ResamplingConfig = Field(default_factory=ResamplingConfig)

    def model_post_init(self, __context: Any) -> None:
        # Synchronize top-level cleansing and split to feature_engineering if customized
        if self.cleansing != CleansingConfig() and self.feature_engineering.cleansing == CleansingConfig():
            self.feature_engineering.cleansing = self.cleansing
        if self.split != SplitConfig() and self.feature_engineering.split == SplitConfig():
            self.feature_engineering.split = self.split
