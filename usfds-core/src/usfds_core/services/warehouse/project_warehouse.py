"""Project Fact Warehouse (ISS-012).

Every COMPLETED DetectionJob gets ONE normalized, append-only fact file:
`warehouse/{project_id}/fact_transactions/job_{job_id}.parquet`. Readers (Insight & Report) load the files of the
jobs they need with DuckDB and keep, per `event_id`, the row of the latest scan (`scanned_at DESC, job_id DESC`).
No pandas full-file load and no per-request re-normalization of `predictions.parquet`.
"""

from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import tempfile
from typing import Any, Iterator, Optional, Sequence

import duckdb
import pandas as pd

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.schemas.preprocessing_config import SystemColumn
from usfds_core.domain.schemas.system_metadata import resolve_canonical_column
from usfds_core.services.warehouse.normalization import (
	extract_hour_utc,
	parse_rule_codes,
	parse_tx_timestamp,
	safe_float,
)
from usfds_core.storage.base_storage import IFileStorage

logger = logging.getLogger(__name__)

BATCH_SIZE = 20_000

OPTIONAL_ENTITY_COLUMNS: tuple[str, ...] = (
	"device_id",
	"ip_address",
	"card_id",
	"merchant_id",
	"merchant_category",
)

FACT_COLUMNS_DDL = """
	job_id VARCHAR, job_name VARCHAR, job_created_at VARCHAR, scanned_at TIMESTAMP,
	model_version_id VARCHAR, score_threshold DOUBLE, event_id VARCHAR, user_id VARCHAR,
	tx_timestamp TIMESTAMP, hour_utc INTEGER, amount DOUBLE, model_score DOUBLE,
	rule_action VARCHAR, final_action VARCHAR, is_flagged INTEGER, has_rule_hit INTEGER,
	has_ai_hit INTEGER, rule_codes VARCHAR[], dataset_label INTEGER, has_label_col BOOLEAN,
	device_id VARCHAR, ip_address VARCHAR, card_id VARCHAR, merchant_id VARCHAR, merchant_category VARCHAR
"""

# Pandas batch -> typed fact columns (rule codes travel as JSON text, timestamps as ISO text).
_INSERT_SELECT = """
	SELECT job_id, job_name, job_created_at, CAST(scanned_at AS TIMESTAMP),
		model_version_id, score_threshold, event_id, user_id,
		CAST(tx_timestamp AS TIMESTAMP), hour_utc, amount, model_score,
		rule_action, final_action, is_flagged, has_rule_hit,
		has_ai_hit, CAST(from_json(rule_codes_json, '["VARCHAR"]') AS VARCHAR[]), dataset_label, has_label_col,
		CAST(device_id AS VARCHAR), CAST(ip_address AS VARCHAR), CAST(card_id AS VARCHAR),
		CAST(merchant_id AS VARCHAR), CAST(merchant_category AS VARCHAR)
	FROM batch_df
"""

_BATCH_COLUMNS = [
	"job_id", "job_name", "job_created_at", "scanned_at", "model_version_id", "score_threshold", "event_id",
	"user_id", "tx_timestamp", "hour_utc", "amount", "model_score", "rule_action", "final_action", "is_flagged",
	"has_rule_hit", "has_ai_hit", "rule_codes_json", "dataset_label", "has_label_col",
	*OPTIONAL_ENTITY_COLUMNS,
]


def create_bounded_duckdb_connection(
	threads: int = 2,
	memory_limit: str = "512MB",
	temp_directory: Optional[str] = None,
) -> duckdb.DuckDBPyConnection:
	"""In-memory DuckDB with a RAM/CPU cap (default DuckDB takes ~80% RAM and every core). Spills to `temp_directory`."""
	return duckdb.connect(
		":memory:",
		config={
			"threads": threads,
			"memory_limit": memory_limit,
			"temp_directory": temp_directory or str(Path(tempfile.gettempdir()) / "usfds_duckdb_tmp"),
		},
	)


def _is_completed(job: DetectionJob) -> bool:
	status = job.status.value if hasattr(job.status, "value") else str(job.status)
	return status == "COMPLETED" and bool(job.output_path)


def _naive_utc_iso(value: datetime) -> str:
	value = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
	return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")


class ProjectWarehouse:
	def __init__(self, file_storage: IFileStorage):
		self.file_storage = file_storage

	@staticmethod
	def fact_key(job: DetectionJob) -> str:
		return f"warehouse/{job.project_id}/fact_transactions/job_{job.job_id}.parquet"

	def write_job_facts(self, job: DetectionJob) -> Optional[str]:
		"""Normalize the job's `predictions.parquet` into its fact file. Returns the key, or None if unreadable."""
		if not _is_completed(job) or not self.file_storage.exists(job.output_path):
			return None
		key = self.fact_key(job)
		conn = create_bounded_duckdb_connection()
		try:
			conn.execute(f"CREATE TABLE facts_out ({FACT_COLUMNS_DDL})")
			with self.file_storage.open_local_path(job.output_path) as source_path:
				reader = conn.cursor()  # streams the source while `conn` receives the inserts
				result = reader.execute("SELECT * FROM read_parquet(?)", [str(source_path)])
				columns = [d[0] for d in result.description]
				self._copy_normalized(conn, result, columns, job)
			with tempfile.TemporaryDirectory() as tmp_dir:
				tmp_file = Path(tmp_dir) / "fact.parquet"
				conn.execute(f"COPY facts_out TO '{tmp_file.as_posix()}' (FORMAT PARQUET)")
				self.file_storage.upload_file(tmp_file, key)
			return key
		except Exception as exc:
			logger.warning(f"Could not write warehouse facts for job {job.job_id}: {exc}")
			return None
		finally:
			conn.close()

	def sync_missing_jobs(self, jobs: Sequence[DetectionJob]) -> int:
		"""Write the fact file of every COMPLETED job that has none (legacy jobs, or a failed write). Returns count written."""
		written = 0
		for job in jobs:
			if _is_completed(job) and not self.file_storage.exists(self.fact_key(job)):
				if self.write_job_facts(job):
					written += 1
		return written

	def load_fact_table(
		self,
		conn: duckdb.DuckDBPyConnection,
		jobs: Sequence[DetectionJob],
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
		table: str = "facts",
	) -> None:
		"""Materialize `table` in `conn`: facts of `jobs`, filtered by `tx_timestamp`, latest scan per `event_id`."""
		with ExitStack() as stack:
			paths = [
				str(stack.enter_context(self.file_storage.open_local_path(self.fact_key(job))))
				for job in jobs
				if _is_completed(job) and self.file_storage.exists(self.fact_key(job))
			]
			if not paths:
				conn.execute(f"CREATE OR REPLACE TABLE {table} ({FACT_COLUMNS_DDL})")
				return
			dt_from = _naive_utc_iso(date_from) if date_from else None
			dt_to = _naive_utc_iso(date_to) if date_to else None
			conn.execute(
				f"""
				CREATE OR REPLACE TABLE {table} AS
				SELECT * FROM read_parquet(?, union_by_name = true)
				WHERE (CAST(? AS TIMESTAMP) IS NULL OR tx_timestamp >= CAST(? AS TIMESTAMP))
				  AND (CAST(? AS TIMESTAMP) IS NULL OR tx_timestamp <= CAST(? AS TIMESTAMP))
				QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY scanned_at DESC, job_id DESC) = 1
				""",
				[paths, dt_from, dt_from, dt_to, dt_to],
			)
			existing_cols = {row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()}
			for col in OPTIONAL_ENTITY_COLUMNS:
				if col not in existing_cols:
					conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR")

	@staticmethod
	def _clean_optional_str(value: Any) -> Optional[str]:
		if value is None:
			return None
		try:
			if pd.isna(value):
				return None
		except (TypeError, ValueError):
			pass
		text = str(value).strip()
		return text or None

	def _copy_normalized(self, conn: duckdb.DuckDBPyConnection, result: Any, columns: list[str], job: DetectionJob) -> None:
		id_col = resolve_canonical_column(columns, SystemColumn.EVENT_ID)
		user_col = resolve_canonical_column(columns, SystemColumn.USER_ID)
		ts_col = resolve_canonical_column(columns, SystemColumn.TIMESTAMP)
		amt_col = resolve_canonical_column(columns, SystemColumn.AMOUNT)
		lbl_col = resolve_canonical_column(columns, SystemColumn.LABEL)
		entity_cols = {col: resolve_canonical_column(columns, col) for col in OPTIONAL_ENTITY_COLUMNS}

		threshold = safe_float(job.score_threshold, 0.5)
		has_model = bool(job.model_version_id is not None or (job.summary_metrics or {}).get("has_model", True))
		job_id = str(job.job_id)
		created = job.created_at or datetime.now(timezone.utc)
		common = {
			"job_id": job_id,
			"job_name": job.job_name or f"Job-{job_id[:8]}",
			"job_created_at": created.isoformat(),
			"scanned_at": _naive_utc_iso(created),
			"model_version_id": str(job.model_version_id) if job.model_version_id else "",
			"score_threshold": threshold,
			"has_label_col": lbl_col is not None,
		}

		row_index = 0
		while True:
			batch = result.fetchmany(BATCH_SIZE)
			if not batch:
				break
			rows = []
			for values in batch:
				row_index += 1
				rec = dict(zip(columns, values))
				ev_raw = rec.get(id_col) if id_col and rec.get(id_col) is not None else f"{job_id}:{row_index}"
				m_score = min(1.0, max(0.0, safe_float(rec.get("model_score", rec.get("fraud_probability", 0.0)), 0.0)))
				final_action = str(rec.get("final_action") or ("REVIEW" if rec.get("prediction") == 1 else "ALLOW")).upper()
				rule_action = str(rec.get("rule_action") or "ALLOW").upper()
				rule_codes = parse_rule_codes(rec.get("triggered_rules"))
				raw_ts = rec.get(ts_col) if ts_col else None
				tx_ts = parse_tx_timestamp(raw_ts)
				ds_label = -1
				if lbl_col and rec.get(lbl_col) is not None:
					try:
						lbl_val = int(float(rec[lbl_col]))
						ds_label = lbl_val if lbl_val in (0, 1) else -1
					except (ValueError, TypeError):
						ds_label = -1
				row = {
					**common,
					"event_id": str(ev_raw),
					"user_id": str(rec.get(user_col) if user_col and rec.get(user_col) is not None else "unknown"),
					"tx_timestamp": tx_ts.isoformat(sep=" ") if tx_ts else None,
					"hour_utc": extract_hour_utc(raw_ts),
					"amount": max(0.0, safe_float(rec.get(amt_col) if amt_col else 0.0, 0.0)),
					"model_score": m_score,
					"rule_action": rule_action,
					"final_action": final_action,
					"is_flagged": 1 if final_action in ("REJECT", "REVIEW") else 0,
					"has_rule_hit": 1 if (rule_codes or rule_action in ("REJECT", "REVIEW")) else 0,
					"has_ai_hit": 1 if (has_model and m_score >= common["score_threshold"]) else 0,
					"rule_codes_json": json.dumps(rule_codes),
					"dataset_label": ds_label,
				}
				for col, src_col in entity_cols.items():
					row[col] = self._clean_optional_str(rec.get(src_col)) if src_col else None
				rows.append(row)
			batch_df = pd.DataFrame(rows, columns=_BATCH_COLUMNS)  # noqa: F841  (referenced by name in the SQL below)
			conn.register("batch_df", batch_df)
			try:
				conn.execute(f"INSERT INTO facts_out {_INSERT_SELECT}")
			finally:
				conn.unregister("batch_df")
