"""Pydantic schemas for Model Plugin Manifest and Validation Results."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ModelPluginManifest(BaseModel):
    """Metadata and contract specification for a user-imported model plugin."""

    model_config = ConfigDict(extra="allow")

    model_name: str = Field(..., description="Unique technical identifier for the model plugin")
    display_name: Optional[str] = Field(default=None, description="Human-readable display name")
    description: Optional[str] = Field(default=None, description="Description of the algorithm and preprocessing")
    framework: Literal["scikit-learn", "xgboost", "lightgbm", "pytorch", "pyg", "onnx"] = Field(
        default="scikit-learn",
        description="Primary ML/DL framework used by the plugin",
    )
    data_modality: Literal["tabular", "sequence", "matrix_2d", "graph"] = Field(
        default="tabular",
        description="Data representation constructed internally by the model",
    )
    data_format: Literal["parquet", "csv"] = Field(
        default="parquet",
        description="Preferred input file format ('parquet' or 'csv') injected by the runner wrapper",
    )
    entrypoint: str = Field(
        default="main.py",
        description="Entrypoint Python file at the root of the plugin package",
    )
    required_columns: List[str] = Field(
        default_factory=list,
        description="Required semantic or feature columns from the FEATURE_ENGINEERED dataset",
    )
    default_hyperparameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Default hyperparameters passed to run_training()",
    )
    dry_run_hyperparameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Lightweight hyperparameter overrides used during upload dry-run validation",
    )
    hyperparameter_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="Schema definition of hyperparameters for UI form rendering and validation",
    )


class PluginValidationResult(BaseModel):
    """Structured result of the 2-stage Model Plugin validation pipeline (Static AST + Dynamic Dry-Run)."""

    is_valid: bool = Field(..., description="True only if both static check and dynamic dry-run succeed")
    static_check_passed: bool = Field(default=False, description="Whether AST security and signature checks passed")
    dry_run_train_passed: bool = Field(default=False, description="Whether dry-run training succeeded")
    dry_run_inference_passed: bool = Field(default=False, description="Whether dry-run inference succeeded")
    manifest: Optional[ModelPluginManifest] = Field(default=None, description="Resolved plugin manifest")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Metrics produced during dry-run training")
    detected_artifacts: List[str] = Field(
        default_factory=list,
        description="List of model and preprocessor artifact filenames produced in artifact_dir",
    )
    errors: List[str] = Field(default_factory=list, description="Validation or runtime error messages")
