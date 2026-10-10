from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository


@dataclass
class LineageNode:
    id: str
    stage: str
    created_at: str
    parent_id: Optional[str] = None


@dataclass
class LineageEdge:
    source: str
    target: str


@dataclass
class LineageGraph:
    dataset_id: str
    nodes: List[LineageNode] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }


class DataLineageService:
    """Service implementing view data lineage tree/DAG & branching support."""

    def __init__(self, artifact_repo: IDatasetArtifactRepository) -> None:
        self.artifact_repo = artifact_repo

    def get_lineage(self, dataset_id: UUID) -> LineageGraph:
        """Retrieves all artifacts for a dataset and constructs a lightweight lineage tree/DAG."""
        artifacts: List[DatasetArtifact] = self.artifact_repo.list_by_dataset(dataset_id)

        nodes: List[LineageNode] = []
        edges: List[LineageEdge] = []

        # Sort artifacts chronologically
        sorted_artifacts = sorted(artifacts, key=lambda a: a.created_at)

        for art in sorted_artifacts:
            art_id_str = str(art.artifact_id)
            stage_str = (
                art.pipeline_stage.value
                if hasattr(art.pipeline_stage, "value")
                else str(art.pipeline_stage)
            )
            parent_id_str = str(art.parent_artifact_id) if art.parent_artifact_id is not None else None

            node = LineageNode(
                id=art_id_str,
                stage=stage_str,
                created_at=art.created_at.isoformat() if hasattr(art.created_at, "isoformat") else str(art.created_at),
                parent_id=parent_id_str,
            )
            nodes.append(node)

            if parent_id_str is not None:
                edges.append(
                    LineageEdge(
                        source=parent_id_str,
                        target=art_id_str,
                    )
                )

        return LineageGraph(
            dataset_id=str(dataset_id),
            nodes=nodes,
            edges=edges,
        )


__all__ = [
    "LineageNode",
    "LineageEdge",
    "LineageGraph",
    "DataLineageService",
]
