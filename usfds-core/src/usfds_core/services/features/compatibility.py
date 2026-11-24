"""Compatibility evaluator matching Features & dependencies against Dataset/Project schemas."""
import importlib.util
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from usfds_core.domain.entities.feature import Feature
from usfds_core.domain.entities.system_metadata import SystemColumnMetadata
from usfds_core.domain.schemas.feature_schemas import (
	FeatureCompatibilityItem,
	FeatureCompatibilityReport,
)
from usfds_core.domain.schemas.system_metadata import (
	DEFAULT_SYSTEM_COLUMN_ALIASES,
	build_default_system_columns,
	resolve_canonical_column,
)
from usfds_core.services.features.code_validator import get_allowed_imports


def _topo_order(features: Sequence[Feature]) -> List[Feature]:
	"""Orders features so dependencies appear before dependents (falls back gracefully on cycles)."""
	by_id = {f.feature_id: f for f in features}
	visited: Set[Any] = set()
	ordered: List[Feature] = []

	def _visit(feat: Feature, stack: Set[Any]) -> None:
		if feat.feature_id in visited or feat.feature_id in stack:
			return
		stack.add(feat.feature_id)
		for dep_id in (feat.depends_on_feature_ids or []):
			dep = by_id.get(dep_id)
			if dep is not None:
				_visit(dep, stack)
		stack.discard(feat.feature_id)
		visited.add(feat.feature_id)
		ordered.append(feat)

	for f in features:
		_visit(f, set())
	return ordered


class FeatureCompatibilityService:
	"""Evaluates which features are AVAILABLE, MISSING_INPUTS, or MISSING_DEPENDENCY for a column set."""

	def __init__(
		self,
		system_metadata: Optional[Iterable[SystemColumnMetadata]] = None,
		allowed_imports: Optional[Iterable[str]] = None,
	) -> None:
		self._metadata_list = list(system_metadata) if system_metadata is not None else build_default_system_columns()
		self._meta_by_key: Dict[str, SystemColumnMetadata] = {m.column_key: m for m in self._metadata_list}
		self._allowed_imports = get_allowed_imports(allowed_imports)

	def _column_is_present(self, required_key: str, available_columns: Sequence[str], semantic_map: Dict[str, str]) -> bool:
		req_lower = str(required_key).strip().lower()
		avail_lower = {str(c).strip().lower() for c in available_columns}
		if req_lower in avail_lower:
			return True
		# Check mapped semantic_type hints (e.g. {"col_x": "EMAIL"} -> satisfies "email")
		if req_lower in semantic_map.values():
			return True
		# Check SystemColumnMetadata aliases & DEFAULT_SYSTEM_COLUMN_ALIASES
		meta = self._meta_by_key.get(req_lower)
		extra_aliases = list(meta.aliases) if meta is not None else DEFAULT_SYSTEM_COLUMN_ALIASES.get(req_lower, [])
		matched = resolve_canonical_column(available_columns, req_lower, extra_aliases=extra_aliases)
		return matched is not None

	@staticmethod
	def _package_available(pkg: str) -> bool:
		top = str(pkg).strip().split(".")[0]
		if not top:
			return True
		try:
			return importlib.util.find_spec(top) is not None
		except Exception:
			return False

	def evaluate(
		self,
		features: Sequence[Feature],
		available_columns: Sequence[str],
		column_semantic_types: Optional[Dict[str, str]] = None,
	) -> FeatureCompatibilityReport:
		"""Evaluates compatibility for all features, propagating unavailability along DAG edges."""
		cols = [str(c) for c in available_columns]
		sem_map = {str(k).strip().lower(): str(v).strip().lower() for k, v in (column_semantic_types or {}).items() if v}

		ordered = _topo_order(features)
		by_id = {f.feature_id: f for f in ordered}
		result_by_id: Dict[Any, FeatureCompatibilityItem] = {}

		for feat in ordered:
			missing_inputs: List[str] = []
			missing_pkgs: List[str] = []
			missing_deps: List[str] = []

			for req in (feat.required_inputs or []):
				if not self._column_is_present(req, cols, sem_map):
					missing_inputs.append(req)

			req_pkgs = (feat.config_json or {}).get("required_packages") or []
			for pkg in req_pkgs:
				top = str(pkg).strip().split(".")[0]
				if not top:
					continue
				if top not in self._allowed_imports or not self._package_available(top):
					missing_pkgs.append(str(pkg))

			for dep_id in (feat.depends_on_feature_ids or []):
				dep_item = result_by_id.get(dep_id)
				if dep_item is None:
					dep_feat = by_id.get(dep_id)
					missing_deps.append(dep_feat.feature_key if dep_feat else str(dep_id))
				elif dep_item.status != "AVAILABLE":
					missing_deps.append(dep_item.feature_key)
					for mi in dep_item.missing_inputs:
						if mi not in missing_inputs:
							missing_inputs.append(mi)
					for mp in dep_item.missing_packages:
						if mp not in missing_pkgs:
							missing_pkgs.append(mp)

			if missing_pkgs:
				status = "MISSING_DEPENDENCY"
			elif missing_inputs or missing_deps:
				status = "MISSING_INPUTS"
			else:
				status = "AVAILABLE"

			item = FeatureCompatibilityItem(
				feature_id=feat.feature_id,
				feature_key=feat.feature_key,
				display_name=feat.display_name,
				megafamily=feat.megafamily.value if hasattr(feat.megafamily, "value") else str(feat.megafamily),
				compute_kind=feat.compute_kind.value if hasattr(feat.compute_kind, "value") else str(feat.compute_kind),
				output_type=feat.output_type.value if hasattr(feat.output_type, "value") else str(feat.output_type),
				is_builtin=feat.is_builtin,
				requires_label=bool(feat.requires_label),
				status=status,
				missing_inputs=missing_inputs,
				missing_dependencies=missing_deps,
				missing_packages=missing_pkgs,
			)
			result_by_id[feat.feature_id] = item

		# Return in the caller's original order
		items = [result_by_id[f.feature_id] for f in features]
		avail_cnt = sum(1 for i in items if i.status == "AVAILABLE")
		return FeatureCompatibilityReport(
			available_columns=cols,
			items=items,
			available_count=avail_cnt,
			unavailable_count=len(items) - avail_cnt,
		)


__all__ = ["FeatureCompatibilityService"]
