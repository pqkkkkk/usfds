from abc import ABC, abstractmethod
from typing import Any, Dict

from usfds_core.services.training.workspace import TrainingRunWorkspace


class BaseTrainer(ABC):
    """Abstract base class for all model trainers adhering to the TrainingRunWorkspace contract."""

    @abstractmethod
    def train(
        self,
        workspace: TrainingRunWorkspace,
        target_column: str,
        hyperparameters: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute model training.

        Parameters
        ----------
        workspace : TrainingRunWorkspace
            Encapsulates the directory layout, input data paths, and output destinations.
        target_column : str
            Name of the binary classification target column (e.g. 'is_fraud').
        hyperparameters : Dict[str, Any]
            Hyperparameters for training the model.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing model performance metrics.
        """
        pass
