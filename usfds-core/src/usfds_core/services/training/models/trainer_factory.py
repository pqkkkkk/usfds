from typing import Optional, Union

from usfds_core.domain.entities.enums import ExecutionType
from usfds_core.services.training.models.base_trainer import BaseTrainer
from usfds_core.services.training.models.builtin_trainer import RandomForestTrainer, XGBoostTrainer
from usfds_core.services.training.models.script_trainer import ScriptPluginTrainer


class ModelTrainerFactory:
    """Factory to instantiate the appropriate BaseTrainer based on Model configuration."""

    @staticmethod
    def create_trainer(
        execution_type: Union[ExecutionType, str] = ExecutionType.BUILTIN,
        model_name: str = "random_forest",
        entrypoint_uri: Optional[str] = None,
    ) -> BaseTrainer:
        """Create a BaseTrainer instance according to execution type and model specification."""
        exec_type_str = str(execution_type).upper()

        if exec_type_str == ExecutionType.BUILTIN.value:
            name_normalized = model_name.lower().strip()
            if name_normalized in ["random_forest", "rf", "randomforest"]:
                return RandomForestTrainer()
            elif name_normalized in ["xgboost", "xgb"]:
                return XGBoostTrainer()
            else:
                raise ValueError(
                    f"Unsupported builtin model: '{model_name}'. Supported algorithms: 'random_forest', 'xgboost'."
                )

        elif exec_type_str == ExecutionType.SCRIPT.value:
            if not entrypoint_uri:
                raise ValueError("entrypoint_uri must be provided when execution_type is SCRIPT.")
            return ScriptPluginTrainer(entrypoint_uri=entrypoint_uri)

        elif exec_type_str == ExecutionType.DOCKER_IMAGE.value:
            raise NotImplementedError(
                "DOCKER_IMAGE execution type is planned for Cloud/Kubernetes orchestration."
            )

        else:
            raise ValueError(f"Unsupported execution type: '{execution_type}'.")
