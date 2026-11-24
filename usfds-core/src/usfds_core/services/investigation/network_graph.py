"""Embedded LadybugDB (:memory:) Network Graph Link Analysis service (ISS-041 / SUC-19)."""

from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import threading
import time
from typing import Any, Optional, Sequence
from uuid import UUID

import duckdb
import ladybug
import pandas as pd

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.schemas.preprocessing_config import SystemColumn
from usfds_core.domain.schemas.system_metadata import resolve_canonical_column
from usfds_core.services.warehouse.project_warehouse import (
	OPTIONAL_ENTITY_COLUMNS,
	ProjectWarehouse,
	create_bounded_duckdb_connection,
	resolve_optional_entity_column,
)
from usfds_core.storage.base_storage import IFileStorage

MAX_EXPAND_NEIGHBORS = 50
MAX_CANVAS_NODES = 200
DEFAULT_SUPER_NODE_DEGREE = 50

SUPPORTED_ENTITY_TYPES: tuple[str, ...] = (
	"USER_ID",
	"DEVICE_ID",
	"IP_ADDRESS",
	"CARD_ID",
	"MERCHANT_ID",
)

# entity_type -> (warehouse column, Ladybug node table, Ladybug rel table)
SECONDARY_ENTITY_SPECS: dict[str, tuple[str, str, str]] = {
	"DEVICE_ID": ("device_id", "Device", "USED_DEVICE"),
	"IP_ADDRESS": ("ip_address", "IpAddress", "USED_IP"),
	"CARD_ID": ("card_id", "Card", "USED_CARD"),
	"MERCHANT_ID": ("merchant_id", "Merchant", "TRANSACTED_AT"),
}

MISSING_ENTITY_MESSAGE = (
	"Tập dữ liệu hiện tại chỉ chứa định danh chủ thể đơn lẻ (user_id), "
	"chưa có các trường thực thể liên kết (như device_id, ip_address, card_id, merchant_id) "
	"để dựng đồ thị đa thực thể."
)


def make_node_id(entity_type: str, entity_value: str) -> str:
	return f"{entity_type}:{entity_value}"


def split_node_id(node_id: str) -> tuple[str, str]:
	if ":" not in node_id:
		raise ValueError(f"Invalid node_id '{node_id}'")
	entity_type, entity_value = node_id.split(":", 1)
	if entity_type not in SUPPORTED_ENTITY_TYPES or not entity_value:
		raise ValueError(f"Invalid node_id '{node_id}'")
	return entity_type, entity_value


def _ident(name: str) -> str:
	return '"' + name.replace('"', '""') + '"'


def _literal(value: str) -> str:
	return "'" + str(value).replace("'", "''") + "'"


def _format_utc_iso(value: Any) -> str:
	if value is None:
		return ""
	if isinstance(value, datetime):
		dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
		return dt.astimezone(timezone.utc).isoformat()
	ts = pd.Timestamp(value)
	if pd.isna(ts):
		return ""
	ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
	return ts.isoformat()


def _parse_rule_codes_cell(value: Any) -> list[str]:
	if value is None:
		return []
	if isinstance(value, (list, tuple)):
		return [str(v) for v in value if str(v).strip()]
	if isinstance(value, str):
		text = value.strip()
		if not text:
			return []
		try:
			parsed = json.loads(text)
			if isinstance(parsed, list):
				return [str(v) for v in parsed if str(v).strip()]
		except json.JSONDecodeError:
			pass
		return [text]
	return []


@dataclass
class LiveRiskOverlay:
	"""Live Case and Blacklist risk signals overlaid on cached LadybugDB subgraphs."""

	blacklisted: set[tuple[str, str]] = field(default_factory=set)
	open_case_counts: dict[str, int] = field(default_factory=dict)
	resolved_fraud_counts: dict[str, int] = field(default_factory=dict)
	user_case_ids: dict[str, list[str]] = field(default_factory=dict)
	event_case_ids: dict[str, str] = field(default_factory=dict)


@dataclass
class _GraphCacheEntry:
	db: Optional[ladybug.Database]
	available: bool
	message: Optional[str]
	total_nodes: int
	total_edges: int
	built_at: float
	source_fingerprint: tuple[Any, ...]


class INetworkGraphService(ABC):
	"""Port for fraud network link analysis and edge inspection."""

	@abstractmethod
	def list_hubs(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		overlay: Optional[LiveRiskOverlay] = None,
		days: int = 90,
		limit: int = 20,
		artifact_path: Optional[str] = None,
	) -> dict[str, Any]:
		raise NotImplementedError

	@abstractmethod
	def get_subgraph(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		seed_type: str,
		seed_value: str,
		overlay: Optional[LiveRiskOverlay] = None,
		hops: int = 2,
		days: int = 90,
		entity_types: Optional[Sequence[str]] = None,
		hide_super_nodes: bool = False,
		artifact_path: Optional[str] = None,
	) -> dict[str, Any]:
		raise NotImplementedError

	@abstractmethod
	def expand_node(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		entity_type: str,
		entity_value: str,
		existing_node_ids: Sequence[str],
		overlay: Optional[LiveRiskOverlay] = None,
		days: int = 90,
		entity_types: Optional[Sequence[str]] = None,
		hide_super_nodes: bool = False,
		artifact_path: Optional[str] = None,
	) -> dict[str, Any]:
		raise NotImplementedError

	@abstractmethod
	def get_edge_transactions(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		user_id: str,
		entity_type: str,
		entity_value: str,
		overlay: Optional[LiveRiskOverlay] = None,
		days: int = 90,
		limit: int = 100,
		artifact_path: Optional[str] = None,
	) -> dict[str, Any]:
		raise NotImplementedError


class LadybugNetworkGraphService(INetworkGraphService):
	"""On-demand in-memory LadybugDB (:memory:) graph engine backed by DuckDB & ProjectWarehouse."""

	def __init__(
		self,
		file_storage: IFileStorage,
		cache_max_entries: int = 4,
		cache_ttl_seconds: int = 600,
		buffer_pool_mb: int = 256,
		super_node_degree_threshold: int = DEFAULT_SUPER_NODE_DEGREE,
	):
		self.file_storage = file_storage
		self.cache_max_entries = max(1, int(cache_max_entries))
		self.cache_ttl_seconds = max(1, int(cache_ttl_seconds))
		self.buffer_pool_mb = max(32, int(buffer_pool_mb))
		self.super_node_degree_threshold = max(1, int(super_node_degree_threshold))
		self._lock = threading.RLock()
		self._cache: OrderedDict[tuple[str, tuple[Any, ...], int], _GraphCacheEntry] = OrderedDict()
		self.cache_hits = 0
		self.cache_builds = 0

	@staticmethod
	def _validate_entity_type(entity_type: str, secondary_only: bool = False) -> str:
		normalized = entity_type.strip().upper()
		allowed = tuple(SECONDARY_ENTITY_SPECS) if secondary_only else SUPPORTED_ENTITY_TYPES
		if normalized not in allowed:
			raise ValueError(f"Unsupported entity type: {entity_type}")
		return normalized

	@staticmethod
	def _normalize_secondary_filter(entity_types: Optional[Sequence[str]]) -> list[str]:
		if not entity_types:
			return list(SECONDARY_ENTITY_SPECS)
		selected = [et.strip().upper() for et in entity_types if et.strip().upper() in SECONDARY_ENTITY_SPECS]
		return list(dict.fromkeys(selected))

	@staticmethod
	def _completed_jobs(jobs: Sequence[DetectionJob]) -> list[DetectionJob]:
		completed = []
		for job in jobs:
			status = job.status.value if hasattr(job.status, "value") else str(job.status)
			if status == "COMPLETED" and job.output_path:
				completed.append(job)
		return completed

	@classmethod
	def _source_fingerprint(cls, jobs: Sequence[DetectionJob], artifact_path: Optional[str]) -> tuple[Any, ...]:
		completed = cls._completed_jobs(jobs)
		if completed:
			return (
				"warehouse",
				tuple(
					sorted(
						(
							str(j.job_id),
							str(j.output_path),
							ts.isoformat() if (ts := getattr(j, "completed_at", None) or getattr(j, "created_at", None)) else "",
						)
						for j in completed
					)
				),
			)
		if artifact_path:
			return ("artifact", artifact_path)
		return ("empty",)

	def _load_window_facts(
		self,
		conn: duckdb.DuckDBPyConnection,
		jobs: Sequence[DetectionJob],
		days: int,
		artifact_path: Optional[str],
	) -> bool:
		"""Materialize `window_facts` inside `conn`. Returns False if no source data exists."""
		completed = self._completed_jobs(jobs)
		if completed:
			ProjectWarehouse(self.file_storage).load_fact_table(conn, completed, table="raw_facts")
		elif artifact_path:
			if not self.file_storage.exists(artifact_path):
				return False
			with self.file_storage.open_local_path(artifact_path) as local_path:
				reader = (
					f"read_csv_auto({_literal(local_path.as_posix())})"
					if artifact_path.lower().endswith(".csv")
					else f"read_parquet({_literal(local_path.as_posix())})"
				)
				cols = [row[0] for row in conn.execute(f"DESCRIBE SELECT * FROM {reader}").fetchall()]
				ev_col = resolve_canonical_column(cols, SystemColumn.EVENT_ID)
				user_col = resolve_canonical_column(cols, SystemColumn.USER_ID)
				ts_col = resolve_canonical_column(cols, SystemColumn.TIMESTAMP)
				amt_col = resolve_canonical_column(cols, SystemColumn.AMOUNT)
				if not all((ev_col, user_col, ts_col, amt_col)):
					raise ValueError("Artifact lacks canonical event_id/user_id/timestamp/amount columns")

				ts_ident = _ident(ts_col)  # type: ignore[arg-type]
				score_col = resolve_canonical_column(cols, "model_score") or resolve_canonical_column(cols, "fraud_probability")
				action_col = resolve_canonical_column(cols, "final_action")
				rules_col = resolve_canonical_column(cols, "triggered_rules")

				projections = [
					"'' AS job_id",
					f"CAST({_ident(ev_col)} AS VARCHAR) AS event_id",  # type: ignore[arg-type]
					f"CAST({_ident(user_col)} AS VARCHAR) AS user_id",  # type: ignore[arg-type]
					f"COALESCE(TRY_CAST({ts_ident} AS TIMESTAMPTZ) AT TIME ZONE 'UTC', TRY_CAST({ts_ident} AS TIMESTAMP)) AS tx_timestamp",
					f"COALESCE(TRY_CAST({_ident(amt_col)} AS DOUBLE), 0.0) AS amount",  # type: ignore[arg-type]
					(
						f"COALESCE(TRY_CAST({_ident(score_col)} AS DOUBLE), 0.0) AS model_score"
						if score_col
						else "0.0 AS model_score"
					),
					(
						f"UPPER(COALESCE(CAST({_ident(action_col)} AS VARCHAR), 'ALLOW')) AS final_action"
						if action_col
						else "'ALLOW' AS final_action"
					),
					(
						f"CASE WHEN UPPER(COALESCE(CAST({_ident(action_col)} AS VARCHAR), '')) IN ('REJECT', 'REVIEW') THEN 1 ELSE 0 END AS is_flagged"
						if action_col
						else "0 AS is_flagged"
					),
					(
						f"CAST({_ident(rules_col)} AS VARCHAR) AS rule_codes"
						if rules_col
						else "CAST([] AS VARCHAR[]) AS rule_codes"
					),
				]
				for col in OPTIONAL_ENTITY_COLUMNS:
					resolved = resolve_optional_entity_column(cols, col)
					if resolved:
						projections.append(f"CAST({_ident(resolved)} AS VARCHAR) AS {col}")
					else:
						projections.append(f"CAST(NULL AS VARCHAR) AS {col}")

				conn.execute(
					f"""
					CREATE OR REPLACE TABLE raw_facts AS
					SELECT {', '.join(projections)}
					FROM {reader}
					QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY tx_timestamp DESC NULLS LAST) = 1
					"""
				)
		else:
			return False

		total_rows = int(conn.execute("SELECT COUNT(*) FROM raw_facts").fetchone()[0])
		if total_rows == 0:
			return False

		max_ts = conn.execute("SELECT MAX(tx_timestamp) FROM raw_facts WHERE tx_timestamp IS NOT NULL").fetchone()[0]
		if days > 0 and max_ts is not None:
			if isinstance(max_ts, datetime):
				cutoff = (max_ts - timedelta(days=days)).replace(tzinfo=None).isoformat(sep=" ")
			else:
				cutoff = (pd.Timestamp(max_ts) - pd.Timedelta(days=days)).to_pydatetime().replace(tzinfo=None).isoformat(sep=" ")
			conn.execute(
				f"""
				CREATE OR REPLACE TEMP VIEW window_facts AS
				SELECT *
				FROM raw_facts
				WHERE user_id IS NOT NULL
				  AND TRIM(CAST(user_id AS VARCHAR)) <> ''
				  AND (tx_timestamp IS NULL OR tx_timestamp >= CAST({_literal(cutoff)} AS TIMESTAMP))
				"""
			)
		else:
			conn.execute(
				"""
				CREATE OR REPLACE TEMP VIEW window_facts AS
				SELECT *
				FROM raw_facts
				WHERE user_id IS NOT NULL
				  AND TRIM(CAST(user_id AS VARCHAR)) <> ''
				"""
			)
		return True

	def _build_graph_entry(
		self,
		jobs: Sequence[DetectionJob],
		days: int,
		artifact_path: Optional[str],
		fingerprint: tuple[Any, ...],
	) -> _GraphCacheEntry:
		duck = create_bounded_duckdb_connection()
		try:
			has_rows = self._load_window_facts(duck, jobs, days, artifact_path)
			if not has_rows:
				return _GraphCacheEntry(
					db=None,
					available=False,
					message="Chưa có dữ liệu giao dịch đã hoàn tất để dựng đồ thị mạng lưới.",
					total_nodes=0,
					total_edges=0,
					built_at=time.monotonic(),
					source_fingerprint=fingerprint,
				)

			secondary_count = int(
				duck.execute(
					"""
					SELECT COUNT(*) FROM window_facts
					WHERE (device_id IS NOT NULL AND TRIM(device_id) <> '')
					   OR (ip_address IS NOT NULL AND TRIM(ip_address) <> '')
					   OR (card_id IS NOT NULL AND TRIM(card_id) <> '')
					   OR (merchant_id IS NOT NULL AND TRIM(merchant_id) <> '')
					"""
				).fetchone()[0]
			)
			if secondary_count == 0:
				return _GraphCacheEntry(
					db=None,
					available=False,
					message=MISSING_ENTITY_MESSAGE,
					total_nodes=0,
					total_edges=0,
					built_at=time.monotonic(),
					source_fingerprint=fingerprint,
				)

			user_df = duck.execute(
				"""
				SELECT
					TRIM(CAST(user_id AS VARCHAR)) AS id,
					CAST(COUNT(*) AS BIGINT) AS tx_count,
					CAST(COALESCE(SUM(is_flagged), 0) AS BIGINT) AS flagged_tx_count,
					CAST(COALESCE(SUM(amount), 0.0) AS DOUBLE) AS total_amount,
					CAST(COALESCE(MAX(model_score), 0.0) AS DOUBLE) AS max_model_score,
					COALESCE(CAST(MIN(tx_timestamp) AS VARCHAR), '') AS first_tx_at,
					COALESCE(CAST(MAX(tx_timestamp) AS VARCHAR), '') AS last_tx_at
				FROM window_facts
				GROUP BY 1
				"""
			).fetchdf()

			sec_dfs: dict[str, pd.DataFrame] = {}
			rel_dfs: dict[str, pd.DataFrame] = {}
			for etype, (col, _node_table, rel_table) in SECONDARY_ENTITY_SPECS.items():
				if etype == "MERCHANT_ID":
					sec_df = duck.execute(
						f"""
						SELECT
							TRIM(CAST({col} AS VARCHAR)) AS id,
							COALESCE(
								ARG_MAX(NULLIF(TRIM(CAST(merchant_category AS VARCHAR)), ''), CASE WHEN merchant_category IS NOT NULL AND TRIM(CAST(merchant_category AS VARCHAR)) <> '' THEN 1 ELSE 0 END),
								''
							) AS merchant_category,
							CAST(COUNT(*) AS BIGINT) AS tx_count,
							CAST(COALESCE(SUM(is_flagged), 0) AS BIGINT) AS flagged_tx_count,
							CAST(COUNT(DISTINCT TRIM(CAST(user_id AS VARCHAR))) AS BIGINT) AS distinct_users,
							CAST(COALESCE(MAX(model_score), 0.0) AS DOUBLE) AS max_model_score
						FROM window_facts
						WHERE {col} IS NOT NULL AND TRIM(CAST({col} AS VARCHAR)) <> ''
						GROUP BY 1
						"""
					).fetchdf()
				else:
					sec_df = duck.execute(
						f"""
						SELECT
							TRIM(CAST({col} AS VARCHAR)) AS id,
							CAST(COUNT(*) AS BIGINT) AS tx_count,
							CAST(COALESCE(SUM(is_flagged), 0) AS BIGINT) AS flagged_tx_count,
							CAST(COUNT(DISTINCT TRIM(CAST(user_id AS VARCHAR))) AS BIGINT) AS distinct_users,
							CAST(COALESCE(MAX(model_score), 0.0) AS DOUBLE) AS max_model_score
						FROM window_facts
						WHERE {col} IS NOT NULL AND TRIM(CAST({col} AS VARCHAR)) <> ''
						GROUP BY 1
						"""
					).fetchdf()

				rel_df = duck.execute(
					f"""
					SELECT
						TRIM(CAST(user_id AS VARCHAR)) AS "from",
						TRIM(CAST({col} AS VARCHAR)) AS "to",
						CAST(COUNT(*) AS BIGINT) AS tx_count,
						CAST(COALESCE(SUM(is_flagged), 0) AS BIGINT) AS flagged_tx_count,
						CAST(COALESCE(SUM(amount), 0.0) AS DOUBLE) AS total_amount,
						CAST(COALESCE(MAX(model_score), 0.0) AS DOUBLE) AS max_model_score,
						COALESCE(CAST(MIN(tx_timestamp) AS VARCHAR), '') AS first_tx_at,
						COALESCE(CAST(MAX(tx_timestamp) AS VARCHAR), '') AS last_tx_at
					FROM window_facts
					WHERE {col} IS NOT NULL AND TRIM(CAST({col} AS VARCHAR)) <> ''
					GROUP BY 1, 2
					"""
				).fetchdf()
				sec_dfs[etype] = sec_df
				rel_dfs[rel_table] = rel_df
		finally:
			duck.close()

		db = ladybug.Database(":memory:", buffer_pool_size=self.buffer_pool_mb * 1024 * 1024)
		lconn = ladybug.Connection(db)
		try:
			lconn.execute(
				"CREATE NODE TABLE User("
				"id STRING, tx_count INT64, flagged_tx_count INT64, "
				"total_amount DOUBLE, max_model_score DOUBLE, first_tx_at STRING, last_tx_at STRING, "
				"PRIMARY KEY (id))"
			)
			lconn.execute(
				"CREATE NODE TABLE Device("
				"id STRING, tx_count INT64, flagged_tx_count INT64, distinct_users INT64, max_model_score DOUBLE, "
				"PRIMARY KEY (id))"
			)
			lconn.execute(
				"CREATE NODE TABLE IpAddress("
				"id STRING, tx_count INT64, flagged_tx_count INT64, distinct_users INT64, max_model_score DOUBLE, "
				"PRIMARY KEY (id))"
			)
			lconn.execute(
				"CREATE NODE TABLE Card("
				"id STRING, tx_count INT64, flagged_tx_count INT64, distinct_users INT64, max_model_score DOUBLE, "
				"PRIMARY KEY (id))"
			)
			lconn.execute(
				"CREATE NODE TABLE Merchant("
				"id STRING, merchant_category STRING, tx_count INT64, flagged_tx_count INT64, distinct_users INT64, max_model_score DOUBLE, "
				"PRIMARY KEY (id))"
			)
			for _col, node_table, rel_table in SECONDARY_ENTITY_SPECS.values():
				lconn.execute(
					f"CREATE REL TABLE {rel_table}("
					f"FROM User TO {node_table}, "
					"tx_count INT64, flagged_tx_count INT64, total_amount DOUBLE, "
					"max_model_score DOUBLE, first_tx_at STRING, last_tx_at STRING)"
				)

			if not user_df.empty:
				user_df["id"] = user_df["id"].astype(str)
				user_df["first_tx_at"] = user_df["first_tx_at"].fillna("").astype(str)
				user_df["last_tx_at"] = user_df["last_tx_at"].fillna("").astype(str)
				lconn.execute("COPY User FROM user_df")

			total_nodes = len(user_df)
			total_edges = 0
			for etype, (_col, node_table, rel_table) in SECONDARY_ENTITY_SPECS.items():
				sdf = sec_dfs[etype]
				if not sdf.empty:
					sdf["id"] = sdf["id"].astype(str)
					if "merchant_category" in sdf.columns:
						sdf["merchant_category"] = sdf["merchant_category"].fillna("").astype(str)
					lconn.execute(f"COPY {node_table} FROM sdf")
					total_nodes += len(sdf)
				rdf = rel_dfs[rel_table]
				if not rdf.empty:
					rdf["from"] = rdf["from"].astype(str)
					rdf["to"] = rdf["to"].astype(str)
					rdf["first_tx_at"] = rdf["first_tx_at"].fillna("").astype(str)
					rdf["last_tx_at"] = rdf["last_tx_at"].fillna("").astype(str)
					lconn.execute(f"COPY {rel_table} FROM rdf")
					total_edges += len(rdf)
		finally:
			lconn.close()

		return _GraphCacheEntry(
			db=db,
			available=True,
			message=None,
			total_nodes=total_nodes,
			total_edges=total_edges,
			built_at=time.monotonic(),
			source_fingerprint=fingerprint,
		)

	def _get_or_build_entry(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		days: int,
		artifact_path: Optional[str],
	) -> _GraphCacheEntry:
		fingerprint = self._source_fingerprint(jobs, artifact_path)
		key = (str(project_id), fingerprint, int(days))
		now = time.monotonic()
		with self._lock:
			existing = self._cache.get(key)
			if existing is not None:
				if (now - existing.built_at) <= self.cache_ttl_seconds:
					self._cache.move_to_end(key)
					self.cache_hits += 1
					return existing
				self._cache.pop(key, None)

			entry = self._build_graph_entry(jobs, days, artifact_path, fingerprint)
			self.cache_builds += 1
			if len(self._cache) >= self.cache_max_entries:
				self._cache.popitem(last=False)
			self._cache[key] = entry
			return entry

	def _build_node_dict(
		self,
		entity_type: str,
		entity_value: str,
		*,
		tx_count: int,
		flagged_tx_count: int,
		total_amount: float = 0.0,
		max_model_score: float = 0.0,
		distinct_users: int = 0,
		merchant_category: Optional[str] = None,
		is_seed: bool = False,
		overlay: LiveRiskOverlay,
	) -> dict[str, Any]:
		is_blacklisted = (entity_type, entity_value) in overlay.blacklisted
		open_cases = overlay.open_case_counts.get(entity_value, 0) if entity_type == "USER_ID" else 0
		resolved_fraud = overlay.resolved_fraud_counts.get(entity_value, 0) if entity_type == "USER_ID" else 0
		case_ids = list(overlay.user_case_ids.get(entity_value, [])) if entity_type == "USER_ID" else []

		if is_blacklisted or resolved_fraud > 0:
			risk_status = "CRITICAL"
		elif open_cases > 0 or flagged_tx_count > 0:
			risk_status = "WARNING"
		else:
			risk_status = "NORMAL"

		is_super = entity_type != "USER_ID" and distinct_users > self.super_node_degree_threshold
		return {
			"id": make_node_id(entity_type, entity_value),
			"entity_type": entity_type,
			"entity_value": entity_value,
			"label": entity_value,
			"tx_count": int(tx_count),
			"flagged_tx_count": int(flagged_tx_count),
			"total_amount": float(total_amount),
			"max_model_score": float(max_model_score),
			"distinct_users": int(distinct_users),
			"merchant_category": merchant_category or None,
			"risk_status": risk_status,
			"is_blacklisted": is_blacklisted,
			"open_case_count": open_cases,
			"resolved_fraud_count": resolved_fraud,
			"case_ids": case_ids,
			"is_super_node": is_super,
			"is_seed": is_seed,
			"pattern_tags": [],
		}

	@staticmethod
	def _build_edge_dict(
		user_id: str,
		entity_type: str,
		entity_value: str,
		rel_type: str,
		*,
		tx_count: int,
		flagged_tx_count: int,
		total_amount: float,
		max_model_score: float,
		first_tx_at: str,
		last_tx_at: str,
	) -> dict[str, Any]:
		source = make_node_id("USER_ID", user_id)
		target = make_node_id(entity_type, entity_value)
		return {
			"id": f"{source}->{target}",
			"source": source,
			"target": target,
			"rel_type": rel_type,
			"entity_type": entity_type,
			"entity_value": entity_value,
			"user_id": user_id,
			"tx_count": int(tx_count),
			"flagged_tx_count": int(flagged_tx_count),
			"total_amount": float(total_amount),
			"max_model_score": float(max_model_score),
			"first_tx_at": first_tx_at,
			"last_tx_at": last_tx_at,
		}

	@staticmethod
	def _rank_sort_key(node: dict[str, Any]) -> tuple[Any, ...]:
		return (
			0 if node["risk_status"] == "CRITICAL" else 1,
			0 if node["open_case_count"] > 0 else 1,
			-int(node["flagged_tx_count"]),
			-float(node["max_model_score"]),
			-int(node["tx_count"]),
			str(node["id"]),
		)

	@staticmethod
	def _row_to_user_node(row: Sequence[Any], overlay: LiveRiskOverlay, is_seed: bool = False, service: Optional["LadybugNetworkGraphService"] = None) -> dict[str, Any]:
		uid, tx_c, flg_c, amt, m_score = row[0], row[1], row[2], row[3], row[4]
		assert service is not None
		return service._build_node_dict(
			"USER_ID",
			str(uid),
			tx_count=int(tx_c),
			flagged_tx_count=int(flg_c),
			total_amount=float(amt),
			max_model_score=float(m_score),
			is_seed=is_seed,
			overlay=overlay,
		)

	def _row_to_secondary_node(
		self,
		entity_type: str,
		row: Sequence[Any],
		overlay: LiveRiskOverlay,
		is_seed: bool = False,
	) -> dict[str, Any]:
		if entity_type == "MERCHANT_ID":
			eid, category, tx_c, flg_c, dist_u, m_score = row[0], row[1], row[2], row[3], row[4], row[5]
		else:
			eid, tx_c, flg_c, dist_u, m_score = row[0], row[1], row[2], row[3], row[4]
			category = None
		return self._build_node_dict(
			entity_type,
			str(eid),
			tx_count=int(tx_c),
			flagged_tx_count=int(flg_c),
			max_model_score=float(m_score),
			distinct_users=int(dist_u),
			merchant_category=str(category) if category else None,
			is_seed=is_seed,
			overlay=overlay,
		)

	def _fetch_node_record(self, lconn: ladybug.Connection, entity_type: str, entity_value: str, overlay: LiveRiskOverlay, is_seed: bool = False) -> Optional[dict[str, Any]]:
		if entity_type == "USER_ID":
			rows = lconn.execute(
				"MATCH (u:User {id: $id}) "
				"RETURN u.id, u.tx_count, u.flagged_tx_count, u.total_amount, u.max_model_score",
				{"id": entity_value},
			).get_all()
			if not rows:
				return None
			return self._row_to_user_node(rows[0], overlay, is_seed=is_seed, service=self)
		_col, table, _rel = SECONDARY_ENTITY_SPECS[entity_type]
		extra = ", e.merchant_category" if entity_type == "MERCHANT_ID" else ""
		if entity_type == "MERCHANT_ID":
			cypher = (
				f"MATCH (e:{table} {{id: $id}}) "
				"RETURN e.id, e.merchant_category, e.tx_count, e.flagged_tx_count, e.distinct_users, e.max_model_score"
			)
		else:
			cypher = (
				f"MATCH (e:{table} {{id: $id}}) "
				"RETURN e.id, e.tx_count, e.flagged_tx_count, e.distinct_users, e.max_model_score"
			)
		rows = lconn.execute(cypher, {"id": entity_value}).get_all()
		if not rows:
			return None
		return self._row_to_secondary_node(entity_type, rows[0], overlay, is_seed=is_seed)

	def _detect_patterns(
		self,
		lconn: ladybug.Connection,
		nodes_by_id: dict[str, dict[str, Any]],
		edges_by_id: dict[str, dict[str, Any]],
		overlay: LiveRiskOverlay,
	) -> list[dict[str, Any]]:
		"""Detect DEVICE_IP_CARD_HUB and MERCHANT_RING patterns on secondary nodes in the graph."""
		patterns: list[dict[str, Any]] = []
		secondary_nodes = [n for n in nodes_by_id.values() if n["entity_type"] != "USER_ID"]
		for sec_node in secondary_nodes:
			etype = sec_node["entity_type"]
			evalue = sec_node["entity_value"]
			_col, table, rel = SECONDARY_ENTITY_SPECS[etype]
			rows = lconn.execute(
				f"MATCH (u:User)-[r:{rel}]->(e:{table} {{id: $id}}) "
				"RETURN u.id, u.flagged_tx_count, r.flagged_tx_count",
				{"id": evalue},
			).get_all()
			distinct_users = int(sec_node["distinct_users"])
			flagged_user_ids = []
			for uid, u_flg, r_flg in rows:
				uid_str = str(uid)
				is_risky_user = (
					int(u_flg) > 0
					or int(r_flg) > 0
					or ("USER_ID", uid_str) in overlay.blacklisted
					or overlay.open_case_counts.get(uid_str, 0) > 0
					or overlay.resolved_fraud_counts.get(uid_str, 0) > 0
				)
				if is_risky_user:
					flagged_user_ids.append(uid_str)
			flagged_users = len(flagged_user_ids)
			tx_count = max(1, int(sec_node["tx_count"]))
			flagged_tx_count = int(sec_node["flagged_tx_count"])
			flagged_rate = round(flagged_tx_count / tx_count, 4)

			pattern_type: Optional[str] = None
			if etype in ("DEVICE_ID", "IP_ADDRESS", "CARD_ID"):
				if (distinct_users >= 2 and flagged_users >= 1) or (
					distinct_users >= 3 and float(sec_node["max_model_score"]) >= 0.7
				):
					pattern_type = "DEVICE_IP_CARD_HUB"
			elif etype == "MERCHANT_ID":
				if flagged_users >= 3 or (flagged_tx_count >= 3 and flagged_rate >= 0.30):
					pattern_type = "MERCHANT_RING"

			if pattern_type:
				if pattern_type not in sec_node["pattern_tags"]:
					sec_node["pattern_tags"].append(pattern_type)
				involved = [sec_node["id"]] + [
					make_node_id("USER_ID", uid_str)
					for uid_str in flagged_user_ids
					if make_node_id("USER_ID", uid_str) in nodes_by_id
				]
				summary = (
					f"Cụm chia sẻ {etype}: {distinct_users} tài khoản liên kết ({flagged_users} tài khoản rủi ro)"
					if pattern_type == "DEVICE_IP_CARD_HUB"
					else f"Vòng thông đồng Merchant: {flagged_users} tài khoản gắn cờ ({flagged_tx_count}/{sec_node['tx_count']} GD nghi vấn)"
				)
				patterns.append({
					"pattern_type": pattern_type,
					"node_id": sec_node["id"],
					"entity_type": etype,
					"entity_value": evalue,
					"distinct_users": distinct_users,
					"flagged_users": flagged_users,
					"tx_count": int(sec_node["tx_count"]),
					"flagged_tx_count": flagged_tx_count,
					"flagged_rate": flagged_rate,
					"summary": summary,
					"involved_node_ids": involved,
				})
		patterns.sort(key=lambda p: (-p["flagged_users"], -p["flagged_tx_count"], -p["distinct_users"], p["node_id"]))
		return patterns

	def list_hubs(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		overlay: Optional[LiveRiskOverlay] = None,
		days: int = 90,
		limit: int = 20,
		artifact_path: Optional[str] = None,
	) -> dict[str, Any]:
		overlay = overlay or LiveRiskOverlay()
		entry = self._get_or_build_entry(project_id, jobs, days, artifact_path)
		if not entry.available or entry.db is None:
			return {
				"available": False,
				"message": entry.message,
				"days": days,
				"hubs": [],
				"total_nodes": 0,
				"total_edges": 0,
			}

		lconn = ladybug.Connection(entry.db)
		hubs: list[dict[str, Any]] = []
		try:
			for etype, (_col, table, rel) in SECONDARY_ENTITY_SPECS.items():
				if etype == "MERCHANT_ID":
					rows = lconn.execute(
						f"MATCH (e:{table}) WHERE e.distinct_users >= 2 OR e.flagged_tx_count > 0 "
						"RETURN e.id, e.merchant_category, e.tx_count, e.flagged_tx_count, e.distinct_users, e.max_model_score"
					).get_all()
				else:
					rows = lconn.execute(
						f"MATCH (e:{table}) WHERE e.distinct_users >= 2 OR e.flagged_tx_count > 0 "
						"RETURN e.id, e.tx_count, e.flagged_tx_count, e.distinct_users, e.max_model_score"
					).get_all()
				for row in rows:
					node = self._row_to_secondary_node(etype, row, overlay)
					u_rows = lconn.execute(
						f"MATCH (u:User)-[r:{rel}]->(e:{table} {{id: $id}}) "
						"RETURN u.id, u.flagged_tx_count, r.flagged_tx_count",
						{"id": node["entity_value"]},
					).get_all()
					flagged_users = sum(
						1
						for uid, u_flg, r_flg in u_rows
						if int(u_flg) > 0
						or int(r_flg) > 0
						or ("USER_ID", str(uid)) in overlay.blacklisted
						or overlay.open_case_counts.get(str(uid), 0) > 0
						or overlay.resolved_fraud_counts.get(str(uid), 0) > 0
					)
					flagged_rate = node["flagged_tx_count"] / max(1, node["tx_count"])
					pattern_type: Optional[str] = None
					if etype in ("DEVICE_ID", "IP_ADDRESS", "CARD_ID") and (
						(node["distinct_users"] >= 2 and flagged_users >= 1)
						or (node["distinct_users"] >= 3 and node["max_model_score"] >= 0.7)
					):
						pattern_type = "DEVICE_IP_CARD_HUB"
					elif etype == "MERCHANT_ID" and (
						flagged_users >= 3 or (node["flagged_tx_count"] >= 3 and flagged_rate >= 0.30)
					):
						pattern_type = "MERCHANT_RING"

					hubs.append({
						"id": node["id"],
						"entity_type": etype,
						"entity_value": node["entity_value"],
						"label": node["label"],
						"distinct_users": node["distinct_users"],
						"tx_count": node["tx_count"],
						"flagged_tx_count": node["flagged_tx_count"],
						"flagged_users": flagged_users,
						"max_model_score": node["max_model_score"],
						"risk_status": node["risk_status"],
						"is_blacklisted": node["is_blacklisted"],
						"is_super_node": node["is_super_node"],
						"pattern_type": pattern_type,
						"merchant_category": node["merchant_category"],
					})
		finally:
			lconn.close()

		hubs.sort(
			key=lambda h: (
				0 if h["pattern_type"] is not None else 1,
				0 if h["risk_status"] == "CRITICAL" else 1,
				-int(h["flagged_users"]),
				-int(h["flagged_tx_count"]),
				-int(h["distinct_users"]),
				-float(h["max_model_score"]),
				str(h["id"]),
			)
		)
		return {
			"available": True,
			"message": None,
			"days": days,
			"hubs": hubs[: max(1, int(limit))],
			"total_nodes": entry.total_nodes,
			"total_edges": entry.total_edges,
		}

	def _query_1hop_from_user(
		self,
		lconn: ladybug.Connection,
		user_id: str,
		allowed_secondary: Sequence[str],
		hide_super_nodes: bool,
		overlay: LiveRiskOverlay,
	) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
		nodes: list[dict[str, Any]] = []
		edges: list[dict[str, Any]] = []
		for etype in allowed_secondary:
			_col, table, rel = SECONDARY_ENTITY_SPECS[etype]
			if etype == "MERCHANT_ID":
				cypher = (
					f"MATCH (u:User {{id: $id}})-[r:{rel}]->(e:{table}) "
					"RETURN e.id, e.merchant_category, e.tx_count, e.flagged_tx_count, e.distinct_users, e.max_model_score, "
					"r.tx_count, r.flagged_tx_count, r.total_amount, r.max_model_score, r.first_tx_at, r.last_tx_at"
				)
				rows = lconn.execute(cypher, {"id": user_id}).get_all()
				for row in rows:
					sec_node = self._row_to_secondary_node(etype, row[:6], overlay)
					if hide_super_nodes and sec_node["is_super_node"]:
						continue
					nodes.append(sec_node)
					edges.append(
						self._build_edge_dict(
							user_id,
							etype,
							sec_node["entity_value"],
							rel,
							tx_count=int(row[6]),
							flagged_tx_count=int(row[7]),
							total_amount=float(row[8]),
							max_model_score=float(row[9]),
							first_tx_at=str(row[10]),
							last_tx_at=str(row[11]),
						)
					)
			else:
				cypher = (
					f"MATCH (u:User {{id: $id}})-[r:{rel}]->(e:{table}) "
					"RETURN e.id, e.tx_count, e.flagged_tx_count, e.distinct_users, e.max_model_score, "
					"r.tx_count, r.flagged_tx_count, r.total_amount, r.max_model_score, r.first_tx_at, r.last_tx_at"
				)
				rows = lconn.execute(cypher, {"id": user_id}).get_all()
				for row in rows:
					sec_node = self._row_to_secondary_node(etype, row[:5], overlay)
					if hide_super_nodes and sec_node["is_super_node"]:
						continue
					nodes.append(sec_node)
					edges.append(
						self._build_edge_dict(
							user_id,
							etype,
							sec_node["entity_value"],
							rel,
							tx_count=int(row[5]),
							flagged_tx_count=int(row[6]),
							total_amount=float(row[7]),
							max_model_score=float(row[8]),
							first_tx_at=str(row[9]),
							last_tx_at=str(row[10]),
						)
					)
		return nodes, edges

	def _query_1hop_from_secondary(
		self,
		lconn: ladybug.Connection,
		entity_type: str,
		entity_value: str,
		overlay: LiveRiskOverlay,
	) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
		_col, table, rel = SECONDARY_ENTITY_SPECS[entity_type]
		rows = lconn.execute(
			f"MATCH (u:User)-[r:{rel}]->(e:{table} {{id: $id}}) "
			"RETURN u.id, u.tx_count, u.flagged_tx_count, u.total_amount, u.max_model_score, "
			"r.tx_count, r.flagged_tx_count, r.total_amount, r.max_model_score, r.first_tx_at, r.last_tx_at",
			{"id": entity_value},
		).get_all()
		nodes: list[dict[str, Any]] = []
		edges: list[dict[str, Any]] = []
		for row in rows:
			u_node = self._row_to_user_node(row[:5], overlay, service=self)
			nodes.append(u_node)
			edges.append(
				self._build_edge_dict(
					u_node["entity_value"],
					entity_type,
					entity_value,
					rel,
					tx_count=int(row[5]),
					flagged_tx_count=int(row[6]),
					total_amount=float(row[7]),
					max_model_score=float(row[8]),
					first_tx_at=str(row[9]),
					last_tx_at=str(row[10]),
				)
			)
		return nodes, edges

	def get_subgraph(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		seed_type: str,
		seed_value: str,
		overlay: Optional[LiveRiskOverlay] = None,
		hops: int = 2,
		days: int = 90,
		entity_types: Optional[Sequence[str]] = None,
		hide_super_nodes: bool = False,
		artifact_path: Optional[str] = None,
	) -> dict[str, Any]:
		seed_type = self._validate_entity_type(seed_type)
		seed_value = seed_value.strip()
		if not seed_value:
			raise ValueError("seed_value is required")
		if hops not in (1, 2):
			raise ValueError("hops must be 1 or 2")

		overlay = overlay or LiveRiskOverlay()
		seed_node_id = make_node_id(seed_type, seed_value)
		entry = self._get_or_build_entry(project_id, jobs, days, artifact_path)
		if not entry.available or entry.db is None:
			return {
				"available": False,
				"message": entry.message,
				"seed_node_id": seed_node_id,
				"hops": hops,
				"days": days,
				"nodes": [],
				"edges": [],
				"patterns": [],
				"stats": {"node_count": 0, "edge_count": 0, "pattern_count": 0, "flagged_node_count": 0},
				"truncated_neighbors": False,
				"total_neighbors": 0,
				"canvas_limit_reached": False,
				"notice": entry.message,
			}

		allowed_secondary = self._normalize_secondary_filter(entity_types)
		lconn = ladybug.Connection(entry.db)
		try:
			seed_node = self._fetch_node_record(lconn, seed_type, seed_value, overlay, is_seed=True)
			if seed_node is None:
				return {
					"available": True,
					"message": None,
					"seed_node_id": seed_node_id,
					"hops": hops,
					"days": days,
					"nodes": [],
					"edges": [],
					"patterns": [],
					"stats": {"node_count": 0, "edge_count": 0, "pattern_count": 0, "flagged_node_count": 0},
					"truncated_neighbors": False,
					"total_neighbors": 0,
					"canvas_limit_reached": False,
					"notice": f"Không tìm thấy thực thể hạt giống '{seed_value}' trong cửa sổ {days} ngày.",
				}

			nodes_by_id: dict[str, dict[str, Any]] = {seed_node_id: seed_node}
			edges_by_id: dict[str, dict[str, Any]] = {}
			truncated_neighbors = False
			total_neighbors = 0
			canvas_limit_reached = False

			if seed_type == "USER_ID":
				hop1_nodes, hop1_edges = self._query_1hop_from_user(
					lconn, seed_value, allowed_secondary, hide_super_nodes, overlay
				)
				total_neighbors = len(hop1_nodes)
				hop1_nodes.sort(key=self._rank_sort_key)
				if len(hop1_nodes) > MAX_CANVAS_NODES - 1:
					hop1_nodes = hop1_nodes[: MAX_CANVAS_NODES - 1]
					canvas_limit_reached = True
				for n in hop1_nodes:
					nodes_by_id[n["id"]] = n
				for e in hop1_edges:
					if e["source"] in nodes_by_id and e["target"] in nodes_by_id:
						edges_by_id[e["id"]] = e

				if hops == 2 and len(nodes_by_id) < MAX_CANVAS_NODES:
					hop2_candidates: dict[str, dict[str, Any]] = {}
					hop2_edges: list[dict[str, Any]] = []
					for sec in hop1_nodes:
						u_nodes, u_edges = self._query_1hop_from_secondary(
							lconn, sec["entity_type"], sec["entity_value"], overlay
						)
						if len(u_nodes) > MAX_EXPAND_NEIGHBORS:
							truncated_neighbors = True
						u_nodes.sort(key=self._rank_sort_key)
						for un in u_nodes[:MAX_EXPAND_NEIGHBORS]:
							if un["id"] not in nodes_by_id:
								hop2_candidates[un["id"]] = un
						hop2_edges.extend(u_edges)

					remaining = MAX_CANVAS_NODES - len(nodes_by_id)
					ranked_hop2 = sorted(hop2_candidates.values(), key=self._rank_sort_key)
					if len(ranked_hop2) > remaining:
						ranked_hop2 = ranked_hop2[:remaining]
						canvas_limit_reached = True
					for n in ranked_hop2:
						nodes_by_id[n["id"]] = n
					for e in hop2_edges:
						if e["source"] in nodes_by_id and e["target"] in nodes_by_id:
							edges_by_id[e["id"]] = e
			else:
				hop1_users, hop1_edges = self._query_1hop_from_secondary(lconn, seed_type, seed_value, overlay)
				total_neighbors = len(hop1_users)
				hop1_users.sort(key=self._rank_sort_key)
				if total_neighbors > MAX_EXPAND_NEIGHBORS:
					truncated_neighbors = True
				cap_1 = min(MAX_EXPAND_NEIGHBORS, MAX_CANVAS_NODES - 1)
				selected_users = hop1_users[:cap_1]
				if len(hop1_users) > MAX_CANVAS_NODES - 1:
					canvas_limit_reached = True
				for n in selected_users:
					nodes_by_id[n["id"]] = n
				for e in hop1_edges:
					if e["source"] in nodes_by_id and e["target"] in nodes_by_id:
						edges_by_id[e["id"]] = e

				if hops == 2 and len(nodes_by_id) < MAX_CANVAS_NODES:
					hop2_candidates = {}
					hop2_edges = []
					for u_node in selected_users:
						s_nodes, s_edges = self._query_1hop_from_user(
							lconn, u_node["entity_value"], allowed_secondary, hide_super_nodes, overlay
						)
						for sn in s_nodes:
							if sn["id"] not in nodes_by_id:
								hop2_candidates[sn["id"]] = sn
						hop2_edges.extend(s_edges)
					remaining = MAX_CANVAS_NODES - len(nodes_by_id)
					ranked_hop2 = sorted(hop2_candidates.values(), key=self._rank_sort_key)
					if len(ranked_hop2) > remaining:
						ranked_hop2 = ranked_hop2[:remaining]
						canvas_limit_reached = True
					for n in ranked_hop2:
						nodes_by_id[n["id"]] = n
					for e in hop2_edges:
						if e["source"] in nodes_by_id and e["target"] in nodes_by_id:
							edges_by_id[e["id"]] = e

			patterns = self._detect_patterns(lconn, nodes_by_id, edges_by_id, overlay)
		finally:
			lconn.close()

		notices: list[str] = []
		if truncated_neighbors:
			notices.append(
				f"Thực thể có {total_neighbors} liên kết. Hệ thống đang hiển thị tối đa {MAX_EXPAND_NEIGHBORS} liên kết có điểm rủi ro cao nhất."
			)
		if canvas_limit_reached:
			notices.append(f"Đã chạm giới hạn hiển thị tối đa {MAX_CANVAS_NODES} nút đồng thời trên đồ thị (BR-IV-05).")

		nodes_list = sorted(nodes_by_id.values(), key=lambda n: (0 if n["is_seed"] else 1, self._rank_sort_key(n)))
		edges_list = sorted(edges_by_id.values(), key=lambda e: (-e["flagged_tx_count"], -e["tx_count"], e["id"]))
		flagged_nodes = sum(1 for n in nodes_list if n["risk_status"] in ("CRITICAL", "WARNING"))
		return {
			"available": True,
			"message": None,
			"seed_node_id": seed_node_id,
			"hops": hops,
			"days": days,
			"nodes": nodes_list,
			"edges": edges_list,
			"patterns": patterns,
			"stats": {
				"node_count": len(nodes_list),
				"edge_count": len(edges_list),
				"pattern_count": len(patterns),
				"flagged_node_count": flagged_nodes,
			},
			"truncated_neighbors": truncated_neighbors,
			"total_neighbors": total_neighbors,
			"canvas_limit_reached": canvas_limit_reached,
			"notice": " ".join(notices) if notices else None,
		}

	def expand_node(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		entity_type: str,
		entity_value: str,
		existing_node_ids: Sequence[str],
		overlay: Optional[LiveRiskOverlay] = None,
		days: int = 90,
		entity_types: Optional[Sequence[str]] = None,
		hide_super_nodes: bool = False,
		artifact_path: Optional[str] = None,
	) -> dict[str, Any]:
		entity_type = self._validate_entity_type(entity_type)
		entity_value = entity_value.strip()
		if not entity_value:
			raise ValueError("entity_value is required")

		overlay = overlay or LiveRiskOverlay()
		center_node_id = make_node_id(entity_type, entity_value)
		entry = self._get_or_build_entry(project_id, jobs, days, artifact_path)
		if not entry.available or entry.db is None:
			return {
				"available": False,
				"message": entry.message,
				"center_node_id": center_node_id,
				"added_nodes": [],
				"added_edges": [],
				"patterns": [],
				"truncated_neighbors": False,
				"total_neighbors": 0,
				"canvas_limit_reached": False,
				"notice": entry.message,
			}

		existing_set = set(existing_node_ids)
		existing_set.add(center_node_id)
		allowed_secondary = self._normalize_secondary_filter(entity_types)

		lconn = ladybug.Connection(entry.db)
		try:
			center_node = self._fetch_node_record(lconn, entity_type, entity_value, overlay)
			if center_node is None:
				return {
					"available": True,
					"message": None,
					"center_node_id": center_node_id,
					"added_nodes": [],
					"added_edges": [],
					"patterns": [],
					"truncated_neighbors": False,
					"total_neighbors": 0,
					"canvas_limit_reached": False,
					"notice": "Không tìm thấy nút cần mở rộng trong dữ liệu hiện tại.",
				}

			if entity_type == "USER_ID":
				neighbors, raw_edges = self._query_1hop_from_user(
					lconn, entity_value, allowed_secondary, hide_super_nodes, overlay
				)
			else:
				neighbors, raw_edges = self._query_1hop_from_secondary(
					lconn, entity_type, entity_value, overlay
				)

			total_neighbors = len(neighbors)
			candidates = [n for n in neighbors if n["id"] not in existing_set]
			candidates.sort(key=self._rank_sort_key)

			remaining_canvas = max(0, MAX_CANVAS_NODES - len(existing_set))
			truncated_neighbors = len(candidates) > MAX_EXPAND_NEIGHBORS
			cap = min(MAX_EXPAND_NEIGHBORS, remaining_canvas)
			added_nodes = candidates[:cap]
			canvas_limit_reached = remaining_canvas == 0 or (
				len(candidates) > remaining_canvas and remaining_canvas <= MAX_EXPAND_NEIGHBORS
			)

			known_ids = existing_set | {n["id"] for n in added_nodes}
			added_edges = [
				e for e in raw_edges if e["source"] in known_ids and e["target"] in known_ids
			]

			pattern_scope = {center_node_id: center_node, **{n["id"]: n for n in added_nodes}}
			patterns = self._detect_patterns(
				lconn, pattern_scope, {e["id"]: e for e in added_edges}, overlay
			)
		finally:
			lconn.close()

		notices: list[str] = []
		if truncated_neighbors:
			notices.append(
				f"Thực thể này có {total_neighbors} liên kết. Hệ thống đang hiển thị {MAX_EXPAND_NEIGHBORS} liên kết có điểm rủi ro cao nhất để đảm bảo hiệu năng trực quan."
			)
		if canvas_limit_reached:
			notices.append(f"Đã đạt giới hạn tối đa {MAX_CANVAS_NODES} nút trên Canvas (BR-IV-05).")

		return {
			"available": True,
			"message": None,
			"center_node_id": center_node_id,
			"added_nodes": added_nodes,
			"added_edges": added_edges,
			"patterns": patterns,
			"truncated_neighbors": truncated_neighbors,
			"total_neighbors": total_neighbors,
			"canvas_limit_reached": canvas_limit_reached,
			"notice": " ".join(notices) if notices else None,
		}

	def get_edge_transactions(
		self,
		project_id: UUID,
		jobs: Sequence[DetectionJob],
		user_id: str,
		entity_type: str,
		entity_value: str,
		overlay: Optional[LiveRiskOverlay] = None,
		days: int = 90,
		limit: int = 100,
		artifact_path: Optional[str] = None,
	) -> dict[str, Any]:
		user_id = user_id.strip()
		if not user_id or not entity_value.strip():
			raise ValueError("user_id and entity_value are required")
		normalized_type = self._validate_entity_type(entity_type, secondary_only=True)
		col_name, _table, _rel = SECONDARY_ENTITY_SPECS[normalized_type]
		overlay = overlay or LiveRiskOverlay()

		duck = create_bounded_duckdb_connection()
		try:
			has_rows = self._load_window_facts(duck, jobs, days, artifact_path)
			if not has_rows:
				return {
					"available": False,
					"message": "Chưa có dữ liệu giao dịch cho cạnh liên kết này.",
					"user_id": user_id,
					"entity_type": normalized_type,
					"entity_value": entity_value.strip(),
					"total": 0,
					"transactions": [],
				}

			where_sql = (
				f"TRIM(CAST(user_id AS VARCHAR)) = ? "
				f"AND {col_name} IS NOT NULL "
				f"AND TRIM(CAST({col_name} AS VARCHAR)) = ?"
			)
			params = [user_id, entity_value.strip()]
			total = int(duck.execute(f"SELECT COUNT(*) FROM window_facts WHERE {where_sql}", params).fetchone()[0])
			rows = duck.execute(
				f"""
				SELECT
					CAST(event_id AS VARCHAR) AS event_id,
					CAST(job_id AS VARCHAR) AS job_id,
					TRIM(CAST(user_id AS VARCHAR)) AS user_id,
					tx_timestamp,
					CAST(amount AS DOUBLE) AS amount,
					CAST(model_score AS DOUBLE) AS model_score,
					CAST(final_action AS VARCHAR) AS final_action,
					CAST(is_flagged AS INTEGER) AS is_flagged,
					rule_codes
				FROM window_facts
				WHERE {where_sql}
				ORDER BY is_flagged DESC, tx_timestamp DESC NULLS LAST, event_id ASC
				LIMIT ?
				""",
				[*params, max(1, int(limit))],
			).fetchall()
		finally:
			duck.close()

		transactions = []
		for ev_id, j_id, uid, ts_val, amt, m_score, action, is_flg, r_codes in rows:
			ev_str = str(ev_id)
			transactions.append({
				"event_id": ev_str,
				"job_id": str(j_id) if j_id else "",
				"user_id": str(uid),
				"tx_timestamp": _format_utc_iso(ts_val),
				"amount": float(amt),
				"model_score": float(m_score),
				"final_action": str(action),
				"is_flagged": bool(is_flg),
				"rule_codes": _parse_rule_codes_cell(r_codes),
				"case_id": overlay.event_case_ids.get(ev_str),
			})

		return {
			"available": True,
			"message": None,
			"user_id": user_id,
			"entity_type": normalized_type,
			"entity_value": entity_value.strip(),
			"total": total,
			"transactions": transactions,
		}
