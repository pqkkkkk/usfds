"""SQLAlchemy repositories for Features, FeatureSets, and Artifact lineage links (ISS-040)."""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from usfds_core.domain.entities.enums import (
	FeatureComputeKind,
	FeatureMegafamily,
	FeatureStatus,
	LogicalDataType,
)
from usfds_core.domain.entities.feature import (
	DatasetArtifactFeatureLink,
	Feature,
	FeatureSet,
)
from usfds_core.repositories.base_feature_repo import IFeatureRepository, IFeatureSetRepository
from usfds_infra.database.models import (
	DatasetArtifactFeatureModel,
	DatasetArtifactFeatureSetModel,
	FeatureDependencyModel,
	FeatureModel,
	FeatureSetItemModel,
	FeatureSetModel,
)


class SqlFeatureRepository(IFeatureRepository):
	"""SQLAlchemy implementation of IFeatureRepository."""

	def __init__(self, session: Session) -> None:
		self.session = session

	@staticmethod
	def _to_entity(model: FeatureModel) -> Feature:
		dep_ids = [UUID(d.depends_on_feature_id) for d in (model.dependencies or [])]
		return Feature(
			feature_id=UUID(model.feature_id),
			project_id=UUID(model.project_id) if model.project_id else None,
			user_id=UUID(model.user_id) if model.user_id else None,
			feature_key=model.feature_key,
			display_name=model.display_name,
			description=model.description,
			megafamily=FeatureMegafamily(model.megafamily),
			compute_kind=FeatureComputeKind(model.compute_kind),
			output_type=LogicalDataType(model.output_type),
			is_stateful=bool(model.is_stateful),
			requires_label=bool(model.requires_label),
			config_json=dict(model.config_json or {}),
			source_code=model.source_code,
			required_inputs=list(model.required_inputs or []),
			depends_on_feature_ids=dep_ids,
			status=FeatureStatus(model.status),
			created_by=model.created_by,
			created_at=model.created_at,
			updated_at=model.updated_at,
		)

	def save(self, feature: Feature) -> Feature:
		fid_str = str(feature.feature_id)
		model = self.session.get(FeatureModel, fid_str)
		mf_str = feature.megafamily.value if hasattr(feature.megafamily, "value") else str(feature.megafamily)
		ck_str = feature.compute_kind.value if hasattr(feature.compute_kind, "value") else str(feature.compute_kind)
		ot_str = feature.output_type.value if hasattr(feature.output_type, "value") else str(feature.output_type)
		st_str = feature.status.value if hasattr(feature.status, "value") else str(feature.status)

		if model is None:
			model = FeatureModel(
				feature_id=fid_str,
				project_id=str(feature.project_id) if feature.project_id else None,
				user_id=str(feature.user_id) if feature.user_id else None,
				feature_key=feature.feature_key,
				display_name=feature.display_name,
				description=feature.description,
				megafamily=mf_str,
				compute_kind=ck_str,
				output_type=ot_str,
				is_stateful=bool(feature.is_stateful),
				requires_label=bool(feature.requires_label),
				config_json=dict(feature.config_json or {}),
				source_code=feature.source_code,
				required_inputs=list(feature.required_inputs or []),
				status=st_str,
				created_by=feature.created_by,
				created_at=feature.created_at or datetime.now(timezone.utc),
				updated_at=feature.updated_at or datetime.now(timezone.utc),
			)
			self.session.add(model)
		else:
			model.display_name = feature.display_name
			model.description = feature.description
			model.megafamily = mf_str
			model.compute_kind = ck_str
			model.output_type = ot_str
			model.is_stateful = bool(feature.is_stateful)
			model.requires_label = bool(feature.requires_label)
			model.config_json = dict(feature.config_json or {})
			model.source_code = feature.source_code
			model.required_inputs = list(feature.required_inputs or [])
			model.status = st_str
			model.updated_at = datetime.now(timezone.utc)

		self.session.flush()
		# Sync normalized dependencies table cleanly
		self.session.execute(delete(FeatureDependencyModel).where(FeatureDependencyModel.feature_id == fid_str))
		seen_deps = set()
		for dep_id in (feature.depends_on_feature_ids or []):
			dep_str = str(dep_id)
			if dep_str not in seen_deps:
				seen_deps.add(dep_str)
				self.session.add(
					FeatureDependencyModel(feature_id=fid_str, depends_on_feature_id=dep_str)
				)
		self.session.flush()
		self.session.refresh(model)
		return self._to_entity(model)

	def get_by_id(self, feature_id: UUID) -> Optional[Feature]:
		model = self.session.get(FeatureModel, str(feature_id))
		return self._to_entity(model) if model else None

	def get_by_key(self, project_id: Optional[UUID], feature_key: str) -> Optional[Feature]:
		if project_id is None:
			stmt = select(FeatureModel).where(
				FeatureModel.project_id.is_(None),
				FeatureModel.feature_key == feature_key,
			)
		else:
			stmt = select(FeatureModel).where(
				FeatureModel.project_id == str(project_id),
				FeatureModel.feature_key == feature_key,
			)
		model = self.session.execute(stmt).scalar_one_or_none()
		return self._to_entity(model) if model else None

	def list_by_project(
		self,
		project_id: Optional[UUID],
		include_builtin: bool = True,
		megafamily: Optional[str] = None,
		status: Optional[str] = None,
	) -> List[Feature]:
		stmt = select(FeatureModel)
		if project_id is None:
			stmt = stmt.where(FeatureModel.project_id.is_(None))
		elif include_builtin:
			stmt = stmt.where(
				or_(
					FeatureModel.project_id == str(project_id),
					FeatureModel.project_id.is_(None),
				)
			)
		else:
			stmt = stmt.where(FeatureModel.project_id == str(project_id))

		if megafamily:
			stmt = stmt.where(FeatureModel.megafamily == str(megafamily))
		if status:
			stmt = stmt.where(FeatureModel.status == str(status))

		rows = self.session.execute(stmt.order_by(FeatureModel.feature_key.asc())).scalars().all()
		entities = [self._to_entity(r) for r in rows]
		return sorted(entities, key=lambda x: (0 if x.project_id is None else 1, x.feature_key))

	def list_by_ids(self, feature_ids: List[UUID]) -> List[Feature]:
		if not feature_ids:
			return []
		id_strs = [str(fid) for fid in feature_ids]
		rows = self.session.execute(
			select(FeatureModel).where(FeatureModel.feature_id.in_(id_strs))
		).scalars().all()
		return [self._to_entity(r) for r in rows]

	def list_dependents(self, feature_id: UUID) -> List[Feature]:
		dep_rows = self.session.execute(
			select(FeatureDependencyModel.feature_id).where(
				FeatureDependencyModel.depends_on_feature_id == str(feature_id)
			)
		).scalars().all()
		if not dep_rows:
			return []
		models = self.session.execute(
			select(FeatureModel).where(FeatureModel.feature_id.in_(dep_rows))
		).scalars().all()
		return [self._to_entity(m) for m in models]

	def delete(self, feature_id: UUID) -> bool:
		fid_str = str(feature_id)
		model = self.session.get(FeatureModel, fid_str)
		if model is None:
			return False
		self.session.delete(model)
		self.session.flush()
		return True

	def record_artifact_features(
		self,
		artifact_id: UUID,
		links: List[DatasetArtifactFeatureLink],
	) -> None:
		art_str = str(artifact_id)
		self.session.execute(
			delete(DatasetArtifactFeatureModel).where(DatasetArtifactFeatureModel.artifact_id == art_str)
		)
		seen_keys = set()
		for link in links:
			if link.feature_key in seen_keys:
				continue
			seen_keys.add(link.feature_key)
			self.session.add(
				DatasetArtifactFeatureModel(
					artifact_id=art_str,
					feature_key=link.feature_key,
					feature_id=str(link.feature_id) if link.feature_id else None,
					source_feature_set_id=str(link.source_feature_set_id) if link.source_feature_set_id else None,
					status=link.status,
				)
			)
		self.session.flush()

	def list_artifact_features(self, artifact_id: UUID) -> List[DatasetArtifactFeatureLink]:
		rows = self.session.execute(
			select(DatasetArtifactFeatureModel).where(
				DatasetArtifactFeatureModel.artifact_id == str(artifact_id)
			)
		).scalars().all()
		return [
			DatasetArtifactFeatureLink(
				artifact_id=UUID(r.artifact_id),
				feature_key=r.feature_key,
				feature_id=UUID(r.feature_id) if r.feature_id else None,
				source_feature_set_id=UUID(r.source_feature_set_id) if r.source_feature_set_id else None,
				status=r.status,
			)
			for r in rows
		]


class SqlFeatureSetRepository(IFeatureSetRepository):
	"""SQLAlchemy implementation of IFeatureSetRepository."""

	def __init__(self, session: Session) -> None:
		self.session = session

	@staticmethod
	def _to_entity(model: FeatureSetModel) -> FeatureSet:
		ordered_items = sorted(model.items or [], key=lambda x: x.display_order)
		return FeatureSet(
			feature_set_id=UUID(model.feature_set_id),
			project_id=UUID(model.project_id) if model.project_id else None,
			user_id=UUID(model.user_id) if model.user_id else None,
			set_key=model.set_key,
			name=model.name,
			description=model.description,
			domain_tag=model.domain_tag,
			default_config=dict(model.default_config or {}),
			feature_ids=[UUID(it.feature_id) for it in ordered_items],
			created_by=model.created_by,
			created_at=model.created_at,
			updated_at=model.updated_at,
		)

	def save(self, feature_set: FeatureSet) -> FeatureSet:
		fsid_str = str(feature_set.feature_set_id)
		model = self.session.get(FeatureSetModel, fsid_str)
		if model is None:
			model = FeatureSetModel(
				feature_set_id=fsid_str,
				project_id=str(feature_set.project_id) if feature_set.project_id else None,
				user_id=str(feature_set.user_id) if feature_set.user_id else None,
				set_key=feature_set.set_key,
				name=feature_set.name,
				description=feature_set.description,
				domain_tag=feature_set.domain_tag,
				default_config=dict(feature_set.default_config or {}),
				created_by=feature_set.created_by,
				created_at=feature_set.created_at or datetime.now(timezone.utc),
				updated_at=feature_set.updated_at or datetime.now(timezone.utc),
			)
			self.session.add(model)
		else:
			model.name = feature_set.name
			model.description = feature_set.description
			model.domain_tag = feature_set.domain_tag
			model.default_config = dict(feature_set.default_config or {})
			model.updated_at = datetime.now(timezone.utc)

		self.session.flush()
		self.session.execute(
			delete(FeatureSetItemModel).where(FeatureSetItemModel.feature_set_id == fsid_str)
		)
		seen_fids = set()
		for order_idx, fid in enumerate(feature_set.feature_ids or []):
			fid_str = str(fid)
			if fid_str not in seen_fids:
				seen_fids.add(fid_str)
				self.session.add(
					FeatureSetItemModel(
						feature_set_id=fsid_str,
						feature_id=fid_str,
						display_order=order_idx,
					)
				)
		self.session.flush()
		self.session.refresh(model)
		return self._to_entity(model)

	def get_by_id(self, feature_set_id: UUID) -> Optional[FeatureSet]:
		model = self.session.get(FeatureSetModel, str(feature_set_id))
		return self._to_entity(model) if model else None

	def get_by_key(self, project_id: Optional[UUID], set_key: str) -> Optional[FeatureSet]:
		if project_id is None:
			stmt = select(FeatureSetModel).where(
				FeatureSetModel.project_id.is_(None),
				FeatureSetModel.set_key == set_key,
			)
		else:
			stmt = select(FeatureSetModel).where(
				FeatureSetModel.project_id == str(project_id),
				FeatureSetModel.set_key == set_key,
			)
		model = self.session.execute(stmt).scalar_one_or_none()
		return self._to_entity(model) if model else None

	def list_by_project(
		self,
		project_id: Optional[UUID],
		include_builtin: bool = True,
	) -> List[FeatureSet]:
		stmt = select(FeatureSetModel)
		if project_id is None:
			stmt = stmt.where(FeatureSetModel.project_id.is_(None))
		elif include_builtin:
			stmt = stmt.where(
				or_(
					FeatureSetModel.project_id == str(project_id),
					FeatureSetModel.project_id.is_(None),
				)
			)
		else:
			stmt = stmt.where(FeatureSetModel.project_id == str(project_id))

		rows = self.session.execute(stmt.order_by(FeatureSetModel.set_key.asc())).scalars().all()
		entities = [self._to_entity(r) for r in rows]
		return sorted(entities, key=lambda x: (0 if x.project_id is None else 1, x.set_key))

	def list_by_ids(self, feature_set_ids: List[UUID]) -> List[FeatureSet]:
		if not feature_set_ids:
			return []
		rows = self.session.execute(
			select(FeatureSetModel).where(
				FeatureSetModel.feature_set_id.in_([str(x) for x in feature_set_ids])
			)
		).scalars().all()
		return [self._to_entity(r) for r in rows]

	def list_sets_containing_feature(self, feature_id: UUID) -> List[FeatureSet]:
		set_ids = self.session.execute(
			select(FeatureSetItemModel.feature_set_id).where(
				FeatureSetItemModel.feature_id == str(feature_id)
			)
		).scalars().all()
		if not set_ids:
			return []
		rows = self.session.execute(
			select(FeatureSetModel).where(FeatureSetModel.feature_set_id.in_(set_ids))
		).scalars().all()
		return [self._to_entity(r) for r in rows]

	def delete(self, feature_set_id: UUID) -> bool:
		model = self.session.get(FeatureSetModel, str(feature_set_id))
		if model is None:
			return False
		self.session.delete(model)
		self.session.flush()
		return True

	def record_artifact_feature_sets(
		self,
		artifact_id: UUID,
		feature_set_ids: List[UUID],
	) -> None:
		art_str = str(artifact_id)
		self.session.execute(
			delete(DatasetArtifactFeatureSetModel).where(
				DatasetArtifactFeatureSetModel.artifact_id == art_str
			)
		)
		seen = set()
		for sid in feature_set_ids:
			sid_str = str(sid)
			if sid_str not in seen:
				seen.add(sid_str)
				self.session.add(
					DatasetArtifactFeatureSetModel(artifact_id=art_str, feature_set_id=sid_str)
				)
		self.session.flush()

	def list_artifact_feature_sets(self, artifact_id: UUID) -> List[UUID]:
		rows = self.session.execute(
			select(DatasetArtifactFeatureSetModel.feature_set_id).where(
				DatasetArtifactFeatureSetModel.artifact_id == str(artifact_id)
			)
		).scalars().all()
		return [UUID(r) for r in rows]


__all__ = ["SqlFeatureRepository", "SqlFeatureSetRepository"]
