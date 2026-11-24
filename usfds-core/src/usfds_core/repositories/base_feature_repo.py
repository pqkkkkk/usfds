"""Abstract repository ports for Features, FeatureSets, and Artifact lineage links (ISS-040)."""
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.feature import (
	DatasetArtifactFeatureLink,
	Feature,
	FeatureSet,
)


class IFeatureRepository(ABC):
	"""Repository interface for registry Features and materialized artifact feature links."""

	@abstractmethod
	def save(self, feature: Feature) -> Feature:
		...

	@abstractmethod
	def get_by_id(self, feature_id: UUID) -> Optional[Feature]:
		...

	@abstractmethod
	def get_by_key(self, project_id: Optional[UUID], feature_key: str) -> Optional[Feature]:
		...

	@abstractmethod
	def list_by_project(
		self,
		project_id: Optional[UUID],
		include_builtin: bool = True,
		megafamily: Optional[str] = None,
		status: Optional[str] = None,
	) -> List[Feature]:
		...

	@abstractmethod
	def list_by_ids(self, feature_ids: List[UUID]) -> List[Feature]:
		...

	@abstractmethod
	def list_dependents(self, feature_id: UUID) -> List[Feature]:
		"""Returns features that directly depend on `feature_id`."""
		...

	@abstractmethod
	def delete(self, feature_id: UUID) -> bool:
		...

	@abstractmethod
	def record_artifact_features(
		self,
		artifact_id: UUID,
		links: List[DatasetArtifactFeatureLink],
	) -> None:
		...

	@abstractmethod
	def list_artifact_features(self, artifact_id: UUID) -> List[DatasetArtifactFeatureLink]:
		...


class IFeatureSetRepository(ABC):
	"""Repository interface for FeatureSets and artifact <-> feature_set M:N links."""

	@abstractmethod
	def save(self, feature_set: FeatureSet) -> FeatureSet:
		...

	@abstractmethod
	def get_by_id(self, feature_set_id: UUID) -> Optional[FeatureSet]:
		...

	@abstractmethod
	def get_by_key(self, project_id: Optional[UUID], set_key: str) -> Optional[FeatureSet]:
		...

	@abstractmethod
	def list_by_project(
		self,
		project_id: Optional[UUID],
		include_builtin: bool = True,
	) -> List[FeatureSet]:
		...

	@abstractmethod
	def list_by_ids(self, feature_set_ids: List[UUID]) -> List[FeatureSet]:
		...

	@abstractmethod
	def list_sets_containing_feature(self, feature_id: UUID) -> List[FeatureSet]:
		...

	@abstractmethod
	def delete(self, feature_set_id: UUID) -> bool:
		...

	@abstractmethod
	def record_artifact_feature_sets(
		self,
		artifact_id: UUID,
		feature_set_ids: List[UUID],
	) -> None:
		...

	@abstractmethod
	def list_artifact_feature_sets(self, artifact_id: UUID) -> List[UUID]:
		...


__all__ = ["IFeatureRepository", "IFeatureSetRepository"]
