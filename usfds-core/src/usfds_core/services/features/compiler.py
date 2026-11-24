"""Dynamic 2-Tier Feature Compiler: Kahn DAG -> DuckDB Bounded + TargetRate + Batched Subprocess."""
from collections import deque
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from uuid import UUID

import duckdb
import numpy as np
import pandas as pd

from usfds_core.domain.entities.enums import FeatureComputeKind, LogicalDataType
from usfds_core.domain.entities.feature import Feature
from usfds_core.domain.schemas.feature_schemas import TargetRateSpec, VelocitySpec
from usfds_core.services.features.code_validator import compute_code_sha256
from usfds_core.services.features.expression_parser import parse_safe_expression
from usfds_core.services.features.script_runner import BatchedFeatureScriptRunner
from usfds_core.services.warehouse.project_warehouse import create_bounded_duckdb_connection


_WINDOW_TO_INTERVAL: Dict[str, str] = {
	"5m": "5 MINUTES",
	"1h": "1 HOUR",
	"6h": "6 HOURS",
	"24h": "24 HOURS",
	"7d": "7 DAYS",
	"30d": "30 DAYS",
	"90d": "90 DAYS",
}


def _qident(name: str) -> str:
	safe = str(name).replace('"', '""')
	return f'"{safe}"'


def _normalize_timestamp_series(series: pd.Series) -> pd.Series:
	"""Normalizes timestamp column (datetime64, epoch seconds/ms, or ISO string) to datetime64[ns]."""
	if pd.api.types.is_datetime64_any_dtype(series):
		dt = pd.to_datetime(series, errors="coerce", utc=True)
		return dt.dt.tz_localize(None)
	if pd.api.types.is_numeric_dtype(series):
		nums = pd.to_numeric(series, errors="coerce")
		max_val = nums.dropna().abs().max() if len(nums.dropna()) > 0 else 0
		unit = "ms" if max_val > 1e11 else "s"
		dt = pd.to_datetime(nums, unit=unit, errors="coerce", utc=True)
		return dt.dt.tz_localize(None)
	dt = pd.to_datetime(series, errors="coerce", utc=True)
	return dt.dt.tz_localize(None)


def _coerce_column_series(series: pd.Series, output_type: str) -> pd.Series:
	if output_type == LogicalDataType.BOOLEAN.value:
		return series.fillna(False).astype(bool)
	if output_type == LogicalDataType.STRING.value:
		return series.fillna("").astype(str).astype(object)
	return pd.to_numeric(series, errors="coerce").astype("float64")


class DAGResolver:
	"""Resolves feature dependencies via Kahn's algorithm into parallel topological levels."""

	@staticmethod
	def collect_transitive_closure(
		selected_features: Sequence[Feature],
		all_available_features: Optional[Sequence[Feature]] = None,
	) -> List[Feature]:
		"""Includes any transitive dependencies of `selected_features` present in `all_available_features`."""
		pool: Dict[UUID, Feature] = {f.feature_id: f for f in (all_available_features or selected_features)}
		for f in selected_features:
			pool[f.feature_id] = f

		seen: Set[UUID] = set()
		ordered: List[Feature] = []
		queue = deque(selected_features)
		while queue:
			curr = queue.popleft()
			if curr.feature_id in seen:
				continue
			seen.add(curr.feature_id)
			ordered.append(curr)
			for dep_id in (curr.depends_on_feature_ids or []):
				dep = pool.get(dep_id)
				if dep is not None and dep.feature_id not in seen:
					queue.append(dep)
		return ordered

	@staticmethod
	def resolve_levels(features: Sequence[Feature]) -> List[List[Feature]]:
		"""Topologically sorts features into sequential execution levels [Level 0..K]."""
		if not features:
			return []
		by_id: Dict[UUID, Feature] = {f.feature_id: f for f in features}
		in_degree: Dict[UUID, int] = {f.feature_id: 0 for f in features}
		dependents: Dict[UUID, List[UUID]] = {f.feature_id: [] for f in features}

		for feat in features:
			for dep_id in (feat.depends_on_feature_ids or []):
				if dep_id == feat.feature_id:
					raise ValueError(f"Đặc trưng '{feat.feature_key}' không thể tự phụ thuộc vào chính nó (chu trình DAG).")
				if dep_id not in by_id:
					raise ValueError(
						f"Đặc trưng '{feat.feature_key}' phụ thuộc vào feature_id '{dep_id}' không có trong danh sách."
					)
				in_degree[feat.feature_id] += 1
				dependents[dep_id].append(feat.feature_id)

		curr_level_ids = sorted(
			[fid for fid, deg in in_degree.items() if deg == 0],
			key=lambda fid: by_id[fid].feature_key,
		)
		levels: List[List[Feature]] = []
		visited = 0

		while curr_level_ids:
			levels.append([by_id[fid] for fid in curr_level_ids])
			visited += len(curr_level_ids)
			next_level: List[UUID] = []
			for fid in curr_level_ids:
				for child_id in dependents[fid]:
					in_degree[child_id] -= 1
					if in_degree[child_id] == 0:
						next_level.append(child_id)
			curr_level_ids = sorted(next_level, key=lambda cid: by_id[cid].feature_key)

		if visited != len(features):
			raise ValueError("Phát hiện chu trình phụ thuộc (DAG cycle) giữa các đặc trưng.")

		return levels


class TargetRateEncoder:
	"""Train-only Laplace / m-estimate smoothed historical target rate encoder."""

	@staticmethod
	def fit(train_df: pd.DataFrame, group_col: str, label_col: str = "label", smoothing_m: float = 10.0) -> Dict[str, Any]:
		if label_col not in train_df.columns or group_col not in train_df.columns or len(train_df) == 0:
			return {"prior": 0.0, "rates": {}, "smoothing_m": float(smoothing_m)}

		labels = pd.to_numeric(train_df[label_col], errors="coerce").fillna(0.0)
		prior = float(labels.mean()) if len(labels) > 0 else 0.0
		grouped = (
			pd.DataFrame({"grp": train_df[group_col].fillna("__MISSING__").astype(str), "y": labels})
			.groupby("grp")["y"]
			.agg(["count", "sum"])
		)
		m = float(smoothing_m)
		rates: Dict[str, float] = {}
		for grp_val, row in grouped.iterrows():
			cnt = float(row["count"])
			fsum = float(row["sum"])
			rates[str(grp_val)] = round((fsum + m * prior) / (cnt + m), 6) if (cnt + m) > 0 else round(prior, 6)
		return {"prior": round(prior, 6), "rates": rates, "smoothing_m": m}

	@staticmethod
	def transform(df: pd.DataFrame, group_col: str, state: Dict[str, Any]) -> pd.Series:
		prior = float((state or {}).get("prior", 0.0))
		rates: Dict[str, float] = dict((state or {}).get("rates") or {})
		if group_col not in df.columns:
			return pd.Series(prior, index=df.index, dtype="float64")
		mapped = df[group_col].fillna("__MISSING__").astype(str).map(rates).fillna(prior)
		return pd.to_numeric(mapped, errors="coerce").fillna(prior).astype("float64")


class FeatureCompiler:
	"""Stateless compilation helper building DuckDB SQL for Tier 1 features and validating DAGs."""

	@staticmethod
	def build_duckdb_select_expr(feat: Feature) -> str:
		kind = feat.compute_kind.value if hasattr(feat.compute_kind, "value") else str(feat.compute_kind)
		alias = _qident(feat.feature_key)

		if kind == FeatureComputeKind.EXPRESSION.value:
			expr = str((feat.config_json or {}).get("expr", "")).strip()
			sql_expr, _ = parse_safe_expression(expr)
			out_type = feat.output_type.value if hasattr(feat.output_type, "value") else str(feat.output_type)
			if out_type == LogicalDataType.BOOLEAN.value:
				return f"CAST(({sql_expr}) AS BOOLEAN) AS {alias}"
			if out_type == LogicalDataType.STRING.value:
				return f"CAST(({sql_expr}) AS VARCHAR) AS {alias}"
			return f"CAST(({sql_expr}) AS DOUBLE) AS {alias}"

		if kind == FeatureComputeKind.VELOCITY.value:
			spec = VelocitySpec.model_validate(feat.config_json or {})
			part_cols = [f"CAST({_qident(spec.entity_key)} AS VARCHAR)"]
			if spec.secondary_group_by:
				part_cols.append(f"CAST({_qident(spec.secondary_group_by)} AS VARCHAR)")

			if spec.window == "same_day":
				part_cols.append("DATE_TRUNC('day', _ts)")
			partition_sql = ", ".join(part_cols)

			if spec.agg_fn == "LAG_SECONDS":
				return (
					f"COALESCE(EXTRACT(EPOCH FROM (_ts - LAG(_ts) OVER (PARTITION BY {partition_sql} ORDER BY _ts ASC, _row_idx ASC))), 0.0) AS {alias}"
				)
			if spec.agg_fn == "SEQ_NUM":
				return (
					f"CAST(ROW_NUMBER() OVER (PARTITION BY {partition_sql} ORDER BY _ts ASC, _row_idx ASC) AS DOUBLE) AS {alias}"
				)
			if spec.agg_fn == "IS_FIRST":
				return (
					f"(ROW_NUMBER() OVER (PARTITION BY {partition_sql} ORDER BY _ts ASC, _row_idx ASC) = 1) AS {alias}"
				)

			# Frame boundary
			if spec.window in _WINDOW_TO_INTERVAL:
				interval_lit = _WINDOW_TO_INTERVAL[spec.window]
				frame_sql = (
					f"ORDER BY _ts ASC RANGE BETWEEN INTERVAL '{interval_lit}' PRECEDING AND CURRENT ROW"
				)
			else:
				end_bound = "CURRENT ROW" if spec.include_current else "1 PRECEDING"
				frame_sql = f"ORDER BY _ts ASC, _row_idx ASC ROWS BETWEEN UNBOUNDED PRECEDING AND {end_bound}"

			metric = _qident(spec.metric_col or "amount")
			if spec.agg_fn == "COUNT":
				val_sql = f"CAST(COUNT(*) OVER (PARTITION BY {partition_sql} {frame_sql}) AS DOUBLE)"
			elif spec.agg_fn == "SUM":
				val_sql = f"COALESCE(CAST(SUM(CAST({metric} AS DOUBLE)) OVER (PARTITION BY {partition_sql} {frame_sql}) AS DOUBLE), 0.0)"
			elif spec.agg_fn == "AVG":
				val_sql = f"CAST(AVG(CAST({metric} AS DOUBLE)) OVER (PARTITION BY {partition_sql} {frame_sql}) AS DOUBLE)"
			elif spec.agg_fn == "STD":
				val_sql = f"COALESCE(CAST(STDDEV_SAMP(CAST({metric} AS DOUBLE)) OVER (PARTITION BY {partition_sql} {frame_sql}) AS DOUBLE), 0.0)"
			elif spec.agg_fn == "MIN":
				val_sql = f"CAST(MIN(CAST({metric} AS DOUBLE)) OVER (PARTITION BY {partition_sql} {frame_sql}) AS DOUBLE)"
			elif spec.agg_fn == "MAX":
				val_sql = f"CAST(MAX(CAST({metric} AS DOUBLE)) OVER (PARTITION BY {partition_sql} {frame_sql}) AS DOUBLE)"
			elif spec.agg_fn == "NUNIQUE":
				val_sql = (
					f"CAST(len(list_distinct(list_filter(list({metric}) OVER (PARTITION BY {partition_sql} {frame_sql}), __v -> __v IS NOT NULL))) AS DOUBLE)"
				)
			else:
				raise ValueError(f"Hàm tổng hợp velocity không hỗ trợ: '{spec.agg_fn}'.")

			return f"{val_sql} AS {alias}"

		raise ValueError(f"FeatureCompiler không hỗ trợ SQL cho compute_kind '{kind}'.")

	@staticmethod
	def execute_duckdb_level(
		df: pd.DataFrame,
		duckdb_features: Sequence[Feature],
		time_col: str = "timestamp",
		duckdb_memory_mb: int = 512,
		target_mask_col: Optional[str] = None,
	) -> pd.DataFrame:
		"""Executes one DAG level of VELOCITY / EXPRESSION features in bounded DuckDB."""
		if not duckdb_features:
			if target_mask_col and target_mask_col in df.columns:
				return df.loc[df[target_mask_col] == 1].copy()
			return pd.DataFrame({"_row_idx": df["_row_idx"]}, index=df.index)

		select_parts = ["_row_idx"]
		if target_mask_col and target_mask_col in df.columns:
			select_parts.append(target_mask_col)
		for feat in duckdb_features:
			select_parts.append(FeatureCompiler.build_duckdb_select_expr(feat))

		where_clause = f"WHERE {target_mask_col} = 1 " if target_mask_col and target_mask_col in df.columns else ""
		sql = f"SELECT {', '.join(select_parts)} FROM _feat_input {where_clause}ORDER BY _row_idx ASC"

		work = df.copy()
		if time_col in work.columns:
			work["_ts"] = _normalize_timestamp_series(work[time_col])
		else:
			work["_ts"] = pd.Timestamp("1970-01-01")

		conn: Optional[duckdb.DuckDBPyConnection] = None
		try:
			conn = create_bounded_duckdb_connection(
				threads=2,
				memory_limit=f"{int(duckdb_memory_mb)}MB",
			)
			conn.register("_feat_input", work)
			res_df = conn.execute(sql).df()
			return res_df
		finally:
			if conn is not None:
				conn.close()

	@staticmethod
	def preview_sql_for_feature(feat: Feature) -> Optional[str]:
		"""Returns readable DuckDB SQL preview for Tier 1 EXPRESSION / VELOCITY features."""
		kind = feat.compute_kind.value if hasattr(feat.compute_kind, "value") else str(feat.compute_kind)
		if kind in (FeatureComputeKind.EXPRESSION.value, FeatureComputeKind.VELOCITY.value):
			return FeatureCompiler.build_duckdb_select_expr(feat)
		return None


class CompiledFeaturePipeline:
	"""Pure-data, Train<->Test<->Inference parity feature pipeline (zero pickled user code).

	Stores pinned feature definitions (including source_code + snapshot_sha256),
	JSON-serializable fitted_states, bounded train_history_tail, and optional cleanser.
	"""

	def __init__(
		self,
		specs: Sequence[Any],
		*,
		cleanser: Optional[Any] = None,
		time_col: str = "timestamp",
		label_col: str = "label",
		duckdb_memory_mb: int = 512,
		history_tail_rows: int = 200000,
		script_timeout_seconds: int = 60,
		script_max_bytes: int = 65536,
		allowed_imports: Optional[Iterable[str]] = None,
	) -> None:
		hydrated = [s if isinstance(s, Feature) else Feature.from_dict(s) for s in specs]
		# Validate DAG early and keep pinned pure-data dicts with snapshot sha256
		full_specs = DAGResolver.collect_transitive_closure(hydrated)
		DAGResolver.resolve_levels(full_specs)

		self.pinned_specs: List[Dict[str, Any]] = []
		for f in full_specs:
			d = f.to_dict()
			d["snapshot_sha256"] = compute_code_sha256(f.source_code)
			self.pinned_specs.append(d)

		self.cleanser = cleanser
		self.time_col = time_col or "timestamp"
		self.label_col = label_col or "label"
		self.duckdb_memory_mb = int(duckdb_memory_mb)
		self.history_tail_rows = int(history_tail_rows)
		self.script_timeout_seconds = int(script_timeout_seconds)
		self.script_max_bytes = int(script_max_bytes)
		self.allowed_imports = list(allowed_imports) if allowed_imports is not None else None

		self.fitted_states: Dict[str, Dict[str, Any]] = {}
		self.train_history_tail: Optional[pd.DataFrame] = None
		self.engineered_features: List[str] = []
		self.skipped_features: List[Dict[str, Any]] = []

	def _features(self) -> List[Feature]:
		return [Feature.from_dict(d) for d in self.pinned_specs]

	def _capture_history_tail(self, enriched_train: pd.DataFrame) -> Optional[pd.DataFrame]:
		if len(enriched_train) == 0 or self.history_tail_rows <= 0:
			return None
		feats = self._features()
		has_velocity = any(
			(f.compute_kind.value if hasattr(f.compute_kind, "value") else str(f.compute_kind)) == FeatureComputeKind.VELOCITY.value
			for f in feats
		)
		if not has_velocity:
			return None

		keep_cols: Set[str] = {self.time_col, "event_id", "user_id"}
		for f in feats:
			for req in (f.required_inputs or []):
				keep_cols.add(req)
			cfg = f.config_json or {}
			for k in ("entity_key", "secondary_group_by", "metric_col", "time_col"):
				if cfg.get(k):
					keep_cols.add(str(cfg[k]))
		# Exclude target label and computed outputs so transform recomputes cleanly
		computed_keys = {f.feature_key for f in feats}
		cols = [
			c for c in enriched_train.columns
			if c in keep_cols and c != self.label_col and c not in computed_keys
		]
		if not cols:
			return None
		tail = enriched_train[cols].copy()
		if self.time_col in tail.columns:
			tail["_sort_ts"] = _normalize_timestamp_series(tail[self.time_col])
			tail = tail.sort_values("_sort_ts", kind="mergesort").drop(columns=["_sort_ts"])
		if len(tail) > self.history_tail_rows:
			tail = tail.iloc[-self.history_tail_rows :]
		return tail.reset_index(drop=True)

	def fit_transform(self, train_df: pd.DataFrame) -> pd.DataFrame:
		"""Fits stateful encoders/scripts strictly on train_df and computes all DAG levels."""
		features = self._features()
		levels = DAGResolver.resolve_levels(features)

		work = train_df.copy().reset_index(drop=True)
		work["_row_idx"] = np.arange(len(work), dtype=np.int64)
		runner = BatchedFeatureScriptRunner(
			timeout_seconds=self.script_timeout_seconds,
			max_bytes=self.script_max_bytes,
			allowed_imports=self.allowed_imports,
		)

		self.fitted_states = {}
		produced: List[str] = []

		for level_feats in levels:
			duckdb_feats = [
				f for f in level_feats
				if f.compute_kind in (FeatureComputeKind.VELOCITY, FeatureComputeKind.EXPRESSION)
			]
			target_feats = [f for f in level_feats if f.compute_kind == FeatureComputeKind.TARGET_RATE]
			python_feats = [f for f in level_feats if f.compute_kind == FeatureComputeKind.PYTHON_CODE]

			if duckdb_feats:
				duck_res = FeatureCompiler.execute_duckdb_level(
					work,
					duckdb_feats,
					time_col=self.time_col,
					duckdb_memory_mb=self.duckdb_memory_mb,
				)
				duck_indexed = duck_res.set_index("_row_idx").loc[work["_row_idx"]].reset_index(drop=True)
				for f in duckdb_feats:
					work[f.feature_key] = _coerce_column_series(duck_indexed[f.feature_key], f.output_type.value)
					produced.append(f.feature_key)

			for f in target_feats:
				spec = TargetRateSpec.model_validate(f.config_json or {})
				state = TargetRateEncoder.fit(
					work,
					group_col=spec.group_col,
					label_col=self.label_col,
					smoothing_m=spec.smoothing_m,
				)
				self.fitted_states[f.feature_key] = state
				work[f.feature_key] = TargetRateEncoder.transform(work, spec.group_col, state)
				produced.append(f.feature_key)

			if python_feats:
				py_res, level_states = runner.run_level(work, python_feats, mode="fit_transform")
				self.fitted_states.update(level_states)
				py_indexed = py_res.set_index("_row_idx").loc[work["_row_idx"]].reset_index(drop=True)
				for f in python_feats:
					work[f.feature_key] = _coerce_column_series(py_indexed[f.feature_key], f.output_type.value)
					produced.append(f.feature_key)

		self.engineered_features = produced
		self.train_history_tail = self._capture_history_tail(work)
		return work.drop(columns=["_row_idx"], errors="ignore")

	def transform(self, df: pd.DataFrame) -> pd.DataFrame:
		"""Transforms test or unlabeled batch inference data without calling fit()."""
		if len(df) == 0:
			return df.copy()

		features = self._features()
		levels = DAGResolver.resolve_levels(features)
		runner = BatchedFeatureScriptRunner(
			timeout_seconds=self.script_timeout_seconds,
			max_bytes=self.script_max_bytes,
			allowed_imports=self.allowed_imports,
		)

		target_df = df.copy().reset_index(drop=True)
		target_df["_row_idx"] = np.arange(len(target_df), dtype=np.int64)
		target_df["_is_target"] = 1

		# Combined frame for causal DuckDB velocity continuity across train->test boundary
		if self.train_history_tail is not None and len(self.train_history_tail) > 0:
			tail = self.train_history_tail.copy().reset_index(drop=True)
			# Align missing columns in tail with target columns safely
			for c in target_df.columns:
				if c not in tail.columns and c not in ("_row_idx", "_is_target"):
					tail[c] = np.nan
			tail = tail[[c for c in target_df.columns if c not in ("_row_idx", "_is_target")]].copy()
			tail["_row_idx"] = np.arange(-len(tail), 0, dtype=np.int64)
			tail["_is_target"] = 0
			# Unify timestamp column dtypes before concat
			if self.time_col in tail.columns and self.time_col in target_df.columns:
				tail[self.time_col] = _normalize_timestamp_series(tail[self.time_col])
				target_df[self.time_col] = _normalize_timestamp_series(target_df[self.time_col])
			combined_work = pd.concat([tail, target_df], ignore_index=True)
		else:
			combined_work = target_df.copy()

		for level_feats in levels:
			duckdb_feats = [
				f for f in level_feats
				if f.compute_kind in (FeatureComputeKind.VELOCITY, FeatureComputeKind.EXPRESSION)
			]
			target_feats = [f for f in level_feats if f.compute_kind == FeatureComputeKind.TARGET_RATE]
			python_feats = [f for f in level_feats if f.compute_kind == FeatureComputeKind.PYTHON_CODE]

			if duckdb_feats:
				has_velocity = any(f.compute_kind == FeatureComputeKind.VELOCITY for f in duckdb_feats)
				if has_velocity and self.train_history_tail is not None and len(self.train_history_tail) > 0:
					# Execute DuckDB across [history_tail + target] and filter _is_target == 1
					duck_all = FeatureCompiler.execute_duckdb_level(
						combined_work,
						duckdb_feats,
						time_col=self.time_col,
						duckdb_memory_mb=self.duckdb_memory_mb,
					)
					duck_indexed = duck_all.set_index("_row_idx")
					target_slice = duck_indexed.loc[target_df["_row_idx"]].reset_index(drop=True)
					for f in duckdb_feats:
						series = _coerce_column_series(target_slice[f.feature_key], f.output_type.value)
						target_df[f.feature_key] = series
						# Propagate into combined_work so stacked velocity/expressions on next level see values
						combined_work[f.feature_key] = _coerce_column_series(
							duck_indexed.loc[combined_work["_row_idx"], f.feature_key].reset_index(drop=True),
							f.output_type.value,
						)
				else:
					duck_res = FeatureCompiler.execute_duckdb_level(
						target_df,
						duckdb_feats,
						time_col=self.time_col,
						duckdb_memory_mb=self.duckdb_memory_mb,
					)
					duck_indexed = duck_res.set_index("_row_idx").loc[target_df["_row_idx"]].reset_index(drop=True)
					for f in duckdb_feats:
						series = _coerce_column_series(duck_indexed[f.feature_key], f.output_type.value)
						target_df[f.feature_key] = series
						if f.feature_key not in combined_work.columns:
							combined_work[f.feature_key] = np.nan
						mask = combined_work["_is_target"] == 1
						combined_work.loc[mask, f.feature_key] = series.to_numpy()

			for f in target_feats:
				spec = TargetRateSpec.model_validate(f.config_json or {})
				state = self.fitted_states.get(f.feature_key, {})
				series = TargetRateEncoder.transform(target_df, spec.group_col, state)
				target_df[f.feature_key] = series
				if f.feature_key not in combined_work.columns:
					combined_work[f.feature_key] = np.nan
				mask = combined_work["_is_target"] == 1
				combined_work.loc[mask, f.feature_key] = series.to_numpy()

			if python_feats:
				py_res, _ = runner.run_level(
					target_df.drop(columns=["_is_target"], errors="ignore"),
					python_feats,
					mode="transform",
					states_in=self.fitted_states,
				)
				py_indexed = py_res.set_index("_row_idx").loc[target_df["_row_idx"]].reset_index(drop=True)
				for f in python_feats:
					series = _coerce_column_series(py_indexed[f.feature_key], f.output_type.value)
					target_df[f.feature_key] = series
					if f.feature_key not in combined_work.columns:
						combined_work[f.feature_key] = np.nan
					mask = combined_work["_is_target"] == 1
					combined_work.loc[mask, f.feature_key] = series.to_numpy()

		return target_df.drop(columns=["_row_idx", "_is_target"], errors="ignore")


def materialize_rule_enriched_features(
	df: pd.DataFrame,
	referenced_keys: Iterable[str],
	feature_definitions: Sequence[Any],
	duckdb_memory_mb: int = 512,
	script_timeout_seconds: int = 60,
) -> Tuple[pd.DataFrame, List[str]]:
	"""Auto-compiles missing non-label enriched.* features for Rule backtest or Rule-only inference.

	Features already present in `df` are reused. Missing features with `requires_label=True` evaluate to None
	with an actionable warning rather than crashing.
	"""
	from usfds_core.services.features.compatibility import FeatureCompatibilityService

	missing_keys = [str(k).strip() for k in referenced_keys if str(k).strip() and str(k).strip() not in df.columns]
	if not missing_keys or not feature_definitions:
		return df, []

	pool_feats = [s if isinstance(s, Feature) else Feature.from_dict(s) for s in feature_definitions]
	by_key: Dict[str, Feature] = {f.feature_key: f for f in pool_feats}
	by_id: Dict[UUID, Feature] = {f.feature_id: f for f in pool_feats}

	def _has_label_dependency(feat: Feature, visited: Optional[Set[UUID]] = None) -> bool:
		seen = visited or set()
		if feat.requires_label:
			return True
		seen.add(feat.feature_id)
		for dep_id in (feat.depends_on_feature_ids or []):
			if dep_id in seen:
				continue
			dep = by_id.get(dep_id)
			if dep is not None and _has_label_dependency(dep, seen):
				return True
		return False

	warnings: List[str] = []
	to_compile: List[Feature] = []
	work = df.copy()

	for key in missing_keys:
		feat = by_key.get(key)
		if feat is None:
			continue
		if _has_label_dependency(feat):
			warnings.append(
				f"Đặc trưng '{key}' yêu cầu nhãn huấn luyện (`requires_label=True`) và chưa có sẵn trong dữ liệu/model bundle; "
				"giá trị được gán rỗng (null) khi chạy Rule."
			)
			work[key] = None
		else:
			to_compile.append(feat)

	if not to_compile:
		return work, warnings

	closure = DAGResolver.collect_transitive_closure(to_compile, pool_feats)
	compat = FeatureCompatibilityService().evaluate(closure, [str(c) for c in work.columns])
	avail_ids = {item.feature_id for item in compat.items if item.status == "AVAILABLE"}
	runnable = [f for f in closure if f.feature_id in avail_ids]

	for item in compat.items:
		if item.status != "AVAILABLE" and item.feature_key in missing_keys:
			missing_desc = ", ".join(item.missing_inputs or item.missing_packages or item.missing_dependencies)
			warnings.append(
				f"Không thể biên dịch on-the-fly đặc trưng '{item.feature_key}' vì thiếu đầu vào ({missing_desc})."
			)

	if runnable:
		pipeline = CompiledFeaturePipeline(
			specs=runnable,
			duckdb_memory_mb=duckdb_memory_mb,
			script_timeout_seconds=script_timeout_seconds,
		)
		work = pipeline.fit_transform(work)

	return work, warnings


__all__ = [
	"CompiledFeaturePipeline",
	"DAGResolver",
	"FeatureCompiler",
	"TargetRateEncoder",
	"materialize_rule_enriched_features",
]
