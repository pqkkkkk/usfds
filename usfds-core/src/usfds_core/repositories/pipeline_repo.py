from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from usfds_core.domain.entities.detection import Pipeline


class IPipelineRepository(ABC):
    """Repository interface to retrieve pipeline lineage for a deployment."""

    @abstractmethod
    def get_by_deployment_id(
        self,
        deployment_id: UUID
    ) -> Optional[Pipeline]:
        """Trace back the pipeline lineage from deployment.

        lineage: deployment => model version => preprocessed dataset artifact =>
        feature engineered dataset artifact => mapped dataset artifact => raw dataset artifact.
        """
        pass