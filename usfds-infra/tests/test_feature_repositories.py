"""M2 acceptance tests for Feature Management ORM tables, repositories, seed, and migration (ISS-040)."""
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import (
	FeatureComputeKind,
	FeatureMegafamily,
	LogicalDataType,
	PipelineStage,
	UserStatus,
)
from usfds_core.domain.entities.feature import DatasetArtifactFeatureLink, Feature, FeatureSet
from usfds_core.domain.entities.system import Project, User
from usfds_infra.database import (
	SqlFeatureRepository,
	SqlFeatureSetRepository,
	SqlUserRepository,
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteProjectRepository,
	create_session_factory,
	create_sqlite_engine,
	init_db,
)
from usfds_infra.database.migrate import head_revisions, schema_drift
from usfds_infra.database.seed_features import seed_feature_catalog


def test_feature_catalog_seed_migration_and_repositories(tmp_path):
	"""Migration creates 6 new tables cleanly, seed is idempotent, FKs & partial unique indexes enforce integrity."""
	engine = create_sqlite_engine(tmp_path / "feat_m2.db")
	init_db(engine)
	assert schema_drift(engine) == []
	assert len(head_revisions()) == 1

	factory = create_session_factory(engine)
	with factory() as session:
		# Seed twice -> 100% idempotent
		seed_feature_catalog(session)
		seed_feature_catalog(session)
		session.commit()

		feat_repo = SqlFeatureRepository(session)
		set_repo = SqlFeatureSetRepository(session)

		builtin_feats = feat_repo.list_by_project(project_id=None, include_builtin=True)
		builtin_sets = set_repo.list_by_project(project_id=None, include_builtin=True)
		assert len(builtin_feats) >= 28
		assert len(builtin_sets) == 5
		assert all(f.is_builtin and f.project_id is None for f in builtin_feats)
		assert any(f.compute_kind == FeatureComputeKind.PYTHON_CODE and f.source_code for f in builtin_feats)

		# Partial unique index rejects duplicate built-in feature_key (project_id IS NULL)
		with pytest.raises(IntegrityError):
			feat_repo.save(
				Feature(
					feature_key=builtin_feats[0].feature_key,
					display_name="Dup Builtin",
					megafamily=FeatureMegafamily.ORDERS,
					compute_kind=FeatureComputeKind.EXPRESSION,
					config_json={"expr": "amount"},
					project_id=None,
					user_id=None,
				)
			)
		session.rollback()

		# Create owner + project + custom features + DAG dependency + FeatureSet
		owner = SqlUserRepository(session).save(
			User(
				username="feat_owner",
				email="feat_owner@usfds.local",
				full_name="Feat Owner",
				password_hash="h",
				status=UserStatus.ACTIVE,
			)
		)
		proj = SqliteProjectRepository(session).save(
			Project(project_id=uuid4(), user_id=owner.user_id, project_name="Feat Repo Proj")
		)
		f1 = feat_repo.save(
			Feature(
				project_id=proj.project_id,
				user_id=owner.user_id,
				feature_key="custom_amt_x2",
				display_name="Amt x2",
				megafamily=FeatureMegafamily.MONETARY,
				compute_kind=FeatureComputeKind.EXPRESSION,
				output_type=LogicalDataType.NUMERIC,
				config_json={"expr": "amount * 2"},
				required_inputs=["amount"],
			)
		)
		f2 = feat_repo.save(
			Feature(
				project_id=proj.project_id,
				user_id=owner.user_id,
				feature_key="custom_amt_x4",
				display_name="Amt x4",
				megafamily=FeatureMegafamily.MONETARY,
				compute_kind=FeatureComputeKind.EXPRESSION,
				output_type=LogicalDataType.NUMERIC,
				config_json={"expr": "custom_amt_x2 * 2"},
				required_inputs=["custom_amt_x2"],
				depends_on_feature_ids=[f1.feature_id],
			)
		)
		fset = set_repo.save(
			FeatureSet(
				project_id=proj.project_id,
				user_id=owner.user_id,
				set_key="custom_bundle",
				name="Custom Bundle",
				feature_ids=[f1.feature_id, f2.feature_id],
			)
		)
		session.commit()

		# Deleting f1 directly in SQL must be blocked by ON DELETE RESTRICT on feature_dependencies/feature_set_items
		with pytest.raises(IntegrityError):
			session.execute(text("DELETE FROM features WHERE feature_id = :fid"), {"fid": str(f1.feature_id)})
			session.flush()
		session.rollback()

		# Record dataset_artifact_feature_sets (M:N) & dataset_artifact_features
		ds = SqliteDatasetRepository(session).save(
			Dataset(project_id=proj.project_id, user_id=owner.user_id, dataset_name="ds_links")
		)
		art = SqliteDatasetArtifactRepository(session).save(
			DatasetArtifact(
				dataset_id=ds.dataset_id,
				pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
				storage_path="datasets/tmp/fe",
			)
		)
		set_repo.record_artifact_feature_sets(art.artifact_id, [fset.feature_set_id])
		feat_repo.record_artifact_features(
			art.artifact_id,
			[
				DatasetArtifactFeatureLink(
					artifact_id=art.artifact_id,
					feature_key=f2.feature_key,
					feature_id=f2.feature_id,
					source_feature_set_id=fset.feature_set_id,
					status="APPLIED",
				)
			],
		)
		session.commit()

		# Delete FeatureSet + dependent f2 -> dataset_artifact_features retains feature_key with SET NULL
		set_repo.delete(fset.feature_set_id)
		feat_repo.delete(f2.feature_id)
		session.commit()

		assert set_repo.list_artifact_feature_sets(art.artifact_id) == []
		links = feat_repo.list_artifact_features(art.artifact_id)
		assert len(links) == 1
		assert links[0].feature_key == "custom_amt_x4"
		assert links[0].feature_id is None
		assert links[0].source_feature_set_id is None

	engine.dispose()
