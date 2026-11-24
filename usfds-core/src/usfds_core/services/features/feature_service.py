"""Domain Application Service for Feature Management, Feature Sets, Validation & Preview."""
from datetime import datetime, timezone
import io
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from uuid import UUID, uuid4

import pandas as pd

from usfds_core.domain.entities.enums import (
	FeatureComputeKind,
	FeatureMegafamily,
	FeatureStatus,
	LogicalDataType,
	ProjectStatus,
	RuleStatus,
)
from usfds_core.domain.entities.feature import Feature, FeatureSet
from usfds_core.domain.schemas.feature_schemas import (
	ExpressionSpec,
	FeatureCompatibilityReport,
	FeaturePreviewResult,
	TargetRateSpec,
	VelocitySpec,
)
from usfds_core.domain.schemas.system_metadata import build_default_system_columns
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_dataset_repo import IDatasetRepository
from usfds_core.repositories.base_feature_repo import IFeatureRepository, IFeatureSetRepository
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_core.repositories.base_system_metadata_repo import ISystemColumnMetadataRepository
from usfds_core.services.features.code_validator import validate_feature_code
from usfds_core.services.features.compatibility import FeatureCompatibilityService
from usfds_core.services.features.compiler import CompiledFeaturePipeline, DAGResolver, FeatureCompiler
from usfds_core.services.features.expression_parser import parse_safe_expression
from usfds_core.services.project_management.schema_validator import ProjectSchemaValidator
from usfds_core.storage.base_storage import IFileStorage


_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,95}$")


class FeatureManagementService:
	"""Coordinates Feature & FeatureSet lifecycle, AST/DAG security, clone, compatibility, and preview."""

	def __init__(
		self,
		feature_repo: IFeatureRepository,
		feature_set_repo: IFeatureSetRepository,
		project_repo: Optional[IProjectRepository] = None,
		dataset_repo: Optional[IDatasetRepository] = None,
		artifact_repo: Optional[IDatasetArtifactRepository] = None,
		metadata_repo: Optional[ISystemColumnMetadataRepository] = None,
		rule_manager: Optional[Any] = None,
		file_storage: Optional[IFileStorage] = None,
		duckdb_memory_mb: int = 512,
		preview_max_rows: int = 200,
		preview_timeout_seconds: int = 15,
		script_max_bytes: int = 65536,
		allowed_imports: Optional[Iterable[str]] = None,
	) -> None:
		self.feature_repo = feature_repo
		self.feature_set_repo = feature_set_repo
		self.project_repo = project_repo
		self.dataset_repo = dataset_repo
		self.artifact_repo = artifact_repo
		self.metadata_repo = metadata_repo
		self.rule_manager = rule_manager
		self.file_storage = file_storage
		self.duckdb_memory_mb = int(duckdb_memory_mb)
		self.preview_max_rows = int(preview_max_rows)
		self.preview_timeout_seconds = int(preview_timeout_seconds)
		self.script_max_bytes = int(script_max_bytes)
		self.allowed_imports = list(allowed_imports) if allowed_imports is not None else None

	def _require_writable_project(self, project_id: UUID) -> None:
		if self.project_repo is None:
			return
		project = self.project_repo.get_by_id(project_id)
		if project is None:
			raise LookupError(f"Không tìm thấy dự án '{project_id}'.")
		status_val = project.status.value if hasattr(project.status, "value") else str(project.status)
		if status_val == ProjectStatus.ARCHIVED.value:
			raise ValueError(
				f"Dự án '{project.project_name}' đang ở trạng thái ARCHIVED, không thể tạo hoặc chỉnh sửa đặc trưng."
			)

	def _validate_key(self, key: str, label: str = "feature_key") -> str:
		cleaned = str(key or "").strip()
		if not _KEY_PATTERN.match(cleaned):
			raise ValueError(
				f"{label} '{cleaned}' phải bắt đầu bằng chữ thường a-z và chỉ gồm a-z, 0-9, '_' (2–96 ký tự)."
			)
		return cleaned

	def _validate_feature_logic(
		self,
		feature: Feature,
		project_id: UUID,
		allowed_imports_override: Optional[Iterable[str]] = None,
	) -> None:
		kind = feature.compute_kind.value if hasattr(feature.compute_kind, "value") else str(feature.compute_kind)
		cfg = dict(feature.config_json or {})
		allow = allowed_imports_override if allowed_imports_override is not None else self.allowed_imports

		if kind == FeatureComputeKind.VELOCITY.value:
			spec = VelocitySpec.model_validate(cfg)
			if spec.agg_fn in ("SUM", "AVG", "STD", "MIN", "MAX", "NUNIQUE") and not spec.metric_col:
				raise ValueError(f"Đặc trưng VELOCITY với '{spec.agg_fn}' cần chỉ định 'metric_col'.")
		elif kind == FeatureComputeKind.EXPRESSION.value:
			spec = ExpressionSpec.model_validate(cfg)
			parse_safe_expression(spec.expr)
		elif kind == FeatureComputeKind.TARGET_RATE.value:
			TargetRateSpec.model_validate(cfg)
		elif kind == FeatureComputeKind.PYTHON_CODE.value:
			validate_feature_code(
				feature.source_code,
				is_stateful=bool(feature.is_stateful),
				allowed_imports=allow,
				max_bytes=self.script_max_bytes,
				required_packages=cfg.get("required_packages"),
			)
		else:
			raise ValueError(f"Loại tính toán '{kind}' không được hỗ trợ.")

		# Validate dependencies exist in project or built-in catalog, are ACTIVE, and form no cycles
		catalog = self.feature_repo.list_by_project(project_id, include_builtin=True)
		catalog_by_id = {f.feature_id: f for f in catalog}
		catalog_by_id[feature.feature_id] = feature

		for dep_id in (feature.depends_on_feature_ids or []):
			if dep_id == feature.feature_id:
				raise ValueError(f"Đặc trưng '{feature.feature_key}' không thể tự phụ thuộc vào chính nó.")
			dep = catalog_by_id.get(dep_id)
			if dep is None:
				raise ValueError(f"Đặc trưng phụ thuộc '{dep_id}' không tồn tại trong dự án hoặc hệ thống.")
			dep_status = dep.status.value if hasattr(dep.status, "value") else str(dep.status)
			if dep_status != FeatureStatus.ACTIVE.value:
				raise ValueError(f"Đặc trưng phụ thuộc '{dep.feature_key}' đang không ở trạng thái ACTIVE.")

		subset = DAGResolver.collect_transitive_closure([feature], list(catalog_by_id.values()))
		DAGResolver.resolve_levels(subset)

	def list_features(
		self,
		project_id: Optional[UUID],
		include_builtin: bool = True,
		megafamily: Optional[str] = None,
		status: Optional[str] = None,
	) -> List[Feature]:
		return self.feature_repo.list_by_project(
			project_id=project_id,
			include_builtin=include_builtin,
			megafamily=megafamily,
			status=status,
		)

	def get_feature(self, feature_id: UUID, project_id: Optional[UUID] = None) -> Feature:
		feat = self.feature_repo.get_by_id(feature_id)
		if feat is None:
			raise LookupError(f"Không tìm thấy đặc trưng '{feature_id}'.")
		if project_id is not None and feat.project_id is not None and feat.project_id != project_id:
			raise LookupError(f"Không tìm thấy đặc trưng '{feature_id}' trong dự án.")
		return feat

	def create_feature(
		self,
		project_id: UUID,
		user_id: Optional[UUID],
		feature_key: str,
		display_name: str,
		megafamily: Union[FeatureMegafamily, str],
		compute_kind: Union[FeatureComputeKind, str],
		output_type: Union[LogicalDataType, str] = LogicalDataType.NUMERIC,
		description: Optional[str] = None,
		is_stateful: bool = False,
		requires_label: bool = False,
		config_json: Optional[Dict[str, Any]] = None,
		source_code: Optional[str] = None,
		required_inputs: Optional[List[str]] = None,
		depends_on_feature_ids: Optional[List[UUID]] = None,
		status: Union[FeatureStatus, str] = FeatureStatus.ACTIVE,
		created_by: Optional[str] = None,
		allowed_imports: Optional[Iterable[str]] = None,
	) -> Feature:
		self._require_writable_project(project_id)
		cleaned_key = self._validate_key(feature_key, "feature_key")

		if self.feature_repo.get_by_key(project_id, cleaned_key) is not None:
			raise ValueError(f"Đặc trưng với mã '{cleaned_key}' đã tồn tại trong dự án.")

		mf_enum = megafamily if isinstance(megafamily, FeatureMegafamily) else FeatureMegafamily(str(megafamily))
		ck_enum = compute_kind if isinstance(compute_kind, FeatureComputeKind) else FeatureComputeKind(str(compute_kind))
		ot_enum = output_type if isinstance(output_type, LogicalDataType) else LogicalDataType(str(output_type))
		st_enum = status if isinstance(status, FeatureStatus) else FeatureStatus(str(status))

		effective_requires_label = bool(requires_label or ck_enum == FeatureComputeKind.TARGET_RATE)
		effective_is_stateful = bool(is_stateful or ck_enum == FeatureComputeKind.TARGET_RATE)

		now = datetime.now(timezone.utc)
		entity = Feature(
			feature_id=uuid4(),
			project_id=project_id,
			user_id=user_id,
			feature_key=cleaned_key,
			display_name=str(display_name or cleaned_key).strip(),
			description=description.strip() if isinstance(description, str) and description.strip() else None,
			megafamily=mf_enum,
			compute_kind=ck_enum,
			output_type=ot_enum,
			is_stateful=effective_is_stateful,
			requires_label=effective_requires_label,
			config_json=dict(config_json or {}),
			source_code=source_code,
			required_inputs=[str(x).strip() for x in (required_inputs or []) if str(x).strip()],
			depends_on_feature_ids=list(depends_on_feature_ids or []),
			status=st_enum,
			created_by=created_by,
			created_at=now,
			updated_at=now,
		)
		self._validate_feature_logic(entity, project_id, allowed_imports_override=allowed_imports)
		return self.feature_repo.save(entity)

	def update_feature(
		self,
		feature_id: UUID,
		project_id: UUID,
		display_name: Optional[str] = None,
		description: Optional[str] = None,
		megafamily: Optional[Union[FeatureMegafamily, str]] = None,
		output_type: Optional[Union[LogicalDataType, str]] = None,
		is_stateful: Optional[bool] = None,
		requires_label: Optional[bool] = None,
		config_json: Optional[Dict[str, Any]] = None,
		source_code: Optional[str] = None,
		required_inputs: Optional[List[str]] = None,
		depends_on_feature_ids: Optional[List[UUID]] = None,
		status: Optional[Union[FeatureStatus, str]] = None,
	) -> Feature:
		existing = self.get_feature(feature_id, project_id=project_id)
		if existing.is_builtin:
			raise ValueError(
				f"Không thể chỉnh sửa trực tiếp đặc trưng mặc định (Built-in) '{existing.feature_key}'. Hãy Clone về dự án."
			)
		self._require_writable_project(project_id)

		if display_name is not None:
			existing.display_name = str(display_name).strip() or existing.display_name
		if description is not None:
			existing.description = description.strip() if description.strip() else None
		if megafamily is not None:
			existing.megafamily = megafamily if isinstance(megafamily, FeatureMegafamily) else FeatureMegafamily(str(megafamily))
		if output_type is not None:
			existing.output_type = output_type if isinstance(output_type, LogicalDataType) else LogicalDataType(str(output_type))
		if is_stateful is not None:
			existing.is_stateful = bool(is_stateful)
		if requires_label is not None:
			existing.requires_label = bool(requires_label)
		if config_json is not None:
			existing.config_json = dict(config_json)
		if source_code is not None:
			existing.source_code = source_code
		if required_inputs is not None:
			existing.required_inputs = [str(x).strip() for x in required_inputs if str(x).strip()]
		if depends_on_feature_ids is not None:
			existing.depends_on_feature_ids = list(depends_on_feature_ids)
		if status is not None:
			existing.status = status if isinstance(status, FeatureStatus) else FeatureStatus(str(status))
		existing.updated_at = datetime.now(timezone.utc)

		self._validate_feature_logic(existing, project_id)
		return self.feature_repo.save(existing)

	def clone_feature(
		self,
		feature_id: UUID,
		target_project_id: UUID,
		user_id: Optional[UUID],
		new_feature_key: Optional[str] = None,
		new_display_name: Optional[str] = None,
		created_by: Optional[str] = None,
	) -> Feature:
		src = self.get_feature(feature_id)
		if src.project_id is not None and src.project_id != target_project_id:
			raise LookupError(f"Không tìm thấy đặc trưng '{feature_id}' trong dự án.")
		self._require_writable_project(target_project_id)

		base_key = new_feature_key or f"{src.feature_key}_custom"
		candidate = self._validate_key(base_key, "feature_key")
		suffix = 2
		while self.feature_repo.get_by_key(target_project_id, candidate) is not None:
			if new_feature_key:
				raise ValueError(f"Đặc trưng '{candidate}' đã tồn tại trong dự án.")
			candidate = f"{base_key}_{suffix}"
			suffix += 1

		return self.create_feature(
			project_id=target_project_id,
			user_id=user_id,
			feature_key=candidate,
			display_name=new_display_name or f"{src.display_name} (Tùy chỉnh)",
			megafamily=src.megafamily,
			compute_kind=src.compute_kind,
			output_type=src.output_type,
			description=src.description,
			is_stateful=src.is_stateful,
			requires_label=src.requires_label,
			config_json=dict(src.config_json or {}),
			source_code=src.source_code,
			required_inputs=list(src.required_inputs or []),
			depends_on_feature_ids=list(src.depends_on_feature_ids or []),
			status=FeatureStatus.ACTIVE,
			created_by=created_by,
		)

	def delete_feature(self, feature_id: UUID, project_id: UUID) -> bool:
		existing = self.get_feature(feature_id, project_id=project_id)
		if existing.is_builtin:
			raise ValueError(f"Không thể xóa đặc trưng mặc định (Built-in) '{existing.feature_key}'.")
		self._require_writable_project(project_id)

		dependents = self.feature_repo.list_dependents(feature_id)
		if dependents:
			names = ", ".join(d.feature_key for d in dependents)
			raise ValueError(
				f"Không thể xóa đặc trưng '{existing.feature_key}' vì đang được đặc trưng khác phụ thuộc: {names}."
			)

		sets = self.feature_set_repo.list_sets_containing_feature(feature_id)
		if sets:
			set_names = ", ".join(s.name for s in sets)
			raise ValueError(
				f"Không thể xóa đặc trưng '{existing.feature_key}' vì đang nằm trong gói đặc trưng: {set_names}."
			)

		if self.rule_manager is not None:
			active_rules = self.rule_manager.list_active_rules_referencing_feature(project_id, existing.feature_key)
			if active_rules:
				codes = ", ".join(r.rule_code for r in active_rules)
				raise ValueError(
					f"Không thể xóa đặc trưng '{existing.feature_key}' vì đang được Rule ACTIVE tham chiếu: {codes}."
				)

		return self.feature_repo.delete(feature_id)

	# --- FeatureSet CRUD ---------------------------------------------------------------

	def list_feature_sets(self, project_id: Optional[UUID], include_builtin: bool = True) -> List[FeatureSet]:
		return self.feature_set_repo.list_by_project(project_id=project_id, include_builtin=include_builtin)

	def get_feature_set(self, feature_set_id: UUID, project_id: Optional[UUID] = None) -> FeatureSet:
		fs = self.feature_set_repo.get_by_id(feature_set_id)
		if fs is None:
			raise LookupError(f"Không tìm thấy gói đặc trưng '{feature_set_id}'.")
		if project_id is not None and fs.project_id is not None and fs.project_id != project_id:
			raise LookupError(f"Không tìm thấy gói đặc trưng '{feature_set_id}' trong dự án.")
		return fs

	def _validate_feature_set_items(self, project_id: UUID, feature_ids: List[UUID]) -> List[UUID]:
		if not feature_ids:
			raise ValueError("Gói đặc trưng phải chứa ít nhất 1 đặc trưng.")
		catalog = self.feature_repo.list_by_project(project_id, include_builtin=True)
		catalog_by_id = {f.feature_id: f for f in catalog}
		deduped: List[UUID] = []
		seen = set()
		for fid in feature_ids:
			if fid not in catalog_by_id:
				raise ValueError(f"Đặc trưng '{fid}' không tồn tại hoặc không thuộc phạm vi dự án.")
			if fid not in seen:
				seen.add(fid)
				deduped.append(fid)
		return deduped

	def create_feature_set(
		self,
		project_id: UUID,
		user_id: Optional[UUID],
		set_key: str,
		name: str,
		feature_ids: List[UUID],
		description: Optional[str] = None,
		domain_tag: str = "CUSTOM",
		default_config: Optional[Dict[str, Any]] = None,
		created_by: Optional[str] = None,
	) -> FeatureSet:
		self._require_writable_project(project_id)
		cleaned_key = self._validate_key(set_key, "set_key")
		if self.feature_set_repo.get_by_key(project_id, cleaned_key) is not None:
			raise ValueError(f"Gói đặc trưng '{cleaned_key}' đã tồn tại trong dự án.")
		validated_ids = self._validate_feature_set_items(project_id, feature_ids)
		now = datetime.now(timezone.utc)
		fs = FeatureSet(
			feature_set_id=uuid4(),
			project_id=project_id,
			user_id=user_id,
			set_key=cleaned_key,
			name=str(name or cleaned_key).strip(),
			description=description.strip() if isinstance(description, str) and description.strip() else None,
			domain_tag=str(domain_tag or "CUSTOM").strip().upper(),
			default_config=dict(default_config or {}),
			feature_ids=validated_ids,
			created_by=created_by,
			created_at=now,
			updated_at=now,
		)
		return self.feature_set_repo.save(fs)

	def update_feature_set(
		self,
		feature_set_id: UUID,
		project_id: UUID,
		name: Optional[str] = None,
		description: Optional[str] = None,
		domain_tag: Optional[str] = None,
		default_config: Optional[Dict[str, Any]] = None,
		feature_ids: Optional[List[UUID]] = None,
	) -> FeatureSet:
		existing = self.get_feature_set(feature_set_id, project_id=project_id)
		if existing.is_builtin:
			raise ValueError(f"Không thể chỉnh sửa gói đặc trưng mặc định (Built-in) '{existing.set_key}'.")
		self._require_writable_project(project_id)

		if name is not None:
			existing.name = str(name).strip() or existing.name
		if description is not None:
			existing.description = description.strip() if description.strip() else None
		if domain_tag is not None:
			existing.domain_tag = str(domain_tag).strip().upper() or existing.domain_tag
		if default_config is not None:
			existing.default_config = dict(default_config)
		if feature_ids is not None:
			existing.feature_ids = self._validate_feature_set_items(project_id, feature_ids)
		existing.updated_at = datetime.now(timezone.utc)
		return self.feature_set_repo.save(existing)

	def delete_feature_set(self, feature_set_id: UUID, project_id: UUID) -> bool:
		existing = self.get_feature_set(feature_set_id, project_id=project_id)
		if existing.is_builtin:
			raise ValueError(f"Không thể xóa gói đặc trưng mặc định (Built-in) '{existing.set_key}'.")
		self._require_writable_project(project_id)
		return self.feature_set_repo.delete(feature_set_id)

	# --- Compatibility & Preview -------------------------------------------------------

	def check_compatibility(
		self,
		project_id: UUID,
		dataset_id: Optional[UUID] = None,
		artifact_id: Optional[UUID] = None,
	) -> FeatureCompatibilityReport:
		available_cols: List[str] = []
		semantic_types: Dict[str, str] = {}

		if artifact_id is not None and self.artifact_repo is not None:
			art = self.artifact_repo.get_by_id(artifact_id)
			if art is not None:
				if art.schema_snapshot:
					available_cols = [str(k) for k in art.schema_snapshot.keys()]
				vr = art.validation_report or {}
				if isinstance(vr, dict) and isinstance(vr.get("column_semantic_types"), dict):
					semantic_types = {str(k): str(v) for k, v in vr["column_semantic_types"].items()}
		elif dataset_id is not None and self.artifact_repo is not None:
			arts = self.artifact_repo.list_by_dataset(dataset_id)
			mapped = next((a for a in arts if str(a.pipeline_stage) == "MAPPED"), None)
			raw = next((a for a in arts if str(a.pipeline_stage) == "RAW"), None)
			target_art = mapped or raw
			if target_art is not None:
				if target_art.schema_snapshot:
					available_cols = [str(k) for k in target_art.schema_snapshot.keys()]
				vr = target_art.validation_report or {}
				if isinstance(vr, dict) and isinstance(vr.get("column_semantic_types"), dict):
					semantic_types = {str(k): str(v) for k, v in vr["column_semantic_types"].items()}

		if not available_cols and self.project_repo is not None:
			proj = self.project_repo.get_by_id(project_id)
			if proj is not None and proj.raw_schema:
				cols_dict = proj.raw_schema.columns if hasattr(proj.raw_schema, "columns") else proj.raw_schema.get("columns", {})
				available_cols = [str(k) for k in cols_dict.keys()]

		meta_list = (
			self.metadata_repo.list_all(include_inactive=False)
			if self.metadata_repo is not None
			else build_default_system_columns()
		)
		features = self.feature_repo.list_by_project(project_id, include_builtin=True)
		compat = FeatureCompatibilityService(system_metadata=meta_list, allowed_imports=self.allowed_imports)
		return compat.evaluate(features, available_cols, column_semantic_types=semantic_types)

	def preview_feature(
		self,
		project_id: UUID,
		artifact_id: UUID,
		feature_id: Optional[UUID] = None,
		feature_spec: Optional[Dict[str, Any]] = None,
	) -> FeaturePreviewResult:
		t0 = time.perf_counter()
		if self.artifact_repo is None or self.file_storage is None:
			raise RuntimeError("Thiếu ArtifactRepository hoặc FileStorage để chạy thử đặc trưng.")

		art = self.artifact_repo.get_by_id(artifact_id)
		if art is None:
			raise LookupError(f"Không tìm thấy DatasetArtifact '{artifact_id}'.")

		if feature_id is not None:
			target_feat = self.get_feature(feature_id, project_id=project_id)
		elif feature_spec is not None:
			target_feat = Feature.from_dict({**feature_spec, "project_id": str(project_id)})
			self._validate_feature_logic(target_feat, project_id)
		else:
			raise ValueError("Cần cung cấp feature_id hoặc feature_spec để chạy thử.")

		path = (art.output_paths or {}).get("mapped") or (art.output_paths or {}).get("raw") or art.storage_path
		raw_bytes = self.file_storage.read_bytes(path)
		if path.lower().endswith(".csv"):
			df = pd.read_csv(io.BytesIO(raw_bytes), nrows=self.preview_max_rows)
		else:
			df = pd.read_parquet(io.BytesIO(raw_bytes)).head(self.preview_max_rows)

		catalog = self.feature_repo.list_by_project(project_id, include_builtin=True)
		subset = DAGResolver.collect_transitive_closure([target_feat], catalog)
		pipeline = CompiledFeaturePipeline(
			specs=subset,
			duckdb_memory_mb=self.duckdb_memory_mb,
			script_timeout_seconds=self.preview_timeout_seconds,
			script_max_bytes=self.script_max_bytes,
			allowed_imports=self.allowed_imports,
		)
		enriched = pipeline.fit_transform(df)
		col = enriched[target_feat.feature_key]

		sample_rows: List[Dict[str, Any]] = []
		preview_cols = [c for c in ("event_id", "timestamp", "user_id", "amount", target_feat.feature_key) if c in enriched.columns]
		for row in enriched[preview_cols].head(20).to_dict(orient="records"):
			clean = {}
			for k, v in row.items():
				if hasattr(v, "item"):
					v = v.item()
				clean[str(k)] = None if (isinstance(v, float) and pd.isna(v)) else v
			sample_rows.append(clean)

		stats: Dict[str, Any] = {
			"row_count": int(len(col)),
			"null_count": int(col.isna().sum()),
		}
		if target_feat.output_type == LogicalDataType.NUMERIC:
			num = pd.to_numeric(col, errors="coerce").dropna()
			if len(num) > 0:
				stats.update({
					"min": round(float(num.min()), 6),
					"max": round(float(num.max()), 6),
					"mean": round(float(num.mean()), 6),
				})
		else:
			stats["distinct_count"] = int(col.nunique(dropna=True))

		elapsed = round((time.perf_counter() - t0) * 1000.0, 2)
		return FeaturePreviewResult(
			feature_key=target_feat.feature_key,
			output_type=target_feat.output_type.value if hasattr(target_feat.output_type, "value") else str(target_feat.output_type),
			sample_rows=sample_rows,
			stats=stats,
			warnings=[],
			execution_time_ms=elapsed,
		)


__all__ = ["FeatureManagementService"]
