"""Idempotent seeding of Built-in Features (including source_code) and 5 Domain FeatureSets."""
from sqlalchemy.orm import Session

from usfds_core.services.features.builtin_catalog import build_builtin_features_and_sets
from usfds_infra.database.repos.feature import SqlFeatureRepository, SqlFeatureSetRepository


def seed_feature_catalog(session: Session) -> None:
	"""Idempotently seeds built-in Features (project_id=None) and 5 Domain FeatureSets."""
	feat_repo = SqlFeatureRepository(session)
	set_repo = SqlFeatureSetRepository(session)
	features, feature_sets = build_builtin_features_and_sets()

	# Save base features without dependencies first so FK targets exist before dependent features save
	base_feats = [f for f in features if not f.depends_on_feature_ids]
	dep_feats = [f for f in features if f.depends_on_feature_ids]

	for feat in base_feats + dep_feats:
		existing = feat_repo.get_by_key(None, feat.feature_key)
		if existing is None:
			feat_repo.save(feat)
		else:
			# Sync built-in catalog definitions idempotently
			feat.feature_id = existing.feature_id
			feat_repo.save(feat)

	for fset in feature_sets:
		existing_set = set_repo.get_by_key(None, fset.set_key)
		# Resolve canonical built-in feature_ids in case existing IDs differed
		resolved_fids = []
		for fid in fset.feature_ids:
			target_feat = next((f for f in features if f.feature_id == fid), None)
			if target_feat is not None:
				db_feat = feat_repo.get_by_key(None, target_feat.feature_key)
				if db_feat is not None:
					resolved_fids.append(db_feat.feature_id)
		fset.feature_ids = resolved_fids
		if existing_set is not None:
			fset.feature_set_id = existing_set.feature_set_id
		set_repo.save(fset)

	session.flush()


__all__ = ["seed_feature_catalog"]
