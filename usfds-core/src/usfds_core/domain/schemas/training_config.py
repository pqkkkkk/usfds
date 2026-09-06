from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class TrainingRunConfig(BaseModel):
    """Configuration for initiating a model training run."""
    model_config = ConfigDict(extra="forbid")

    model_id: UUID = Field(..., description="ID of the model registered in the Model Registry")
    dataset_artifact_id: UUID = Field(..., description="ID of the PRE_PROCESSED dataset artifact to train on")
    hyperparameters: Optional[Dict[str, Any]] = Field(default=None, description="Optional hyperparameter overrides")
    compute_target: str = Field(default="local", description="Target compute environment (e.g. 'local', 'worker')")
    run_name: Optional[str] = Field(default=None, description="Optional custom name for the training run")
