"""DuckDB queries over a DetectionJob's `predictions.parquet` (ISS-012).

Filtering, ordering and paging run inside DuckDB; only the rows of the requested page / events / export are
materialized. Replaces loading the whole file into pandas for Results, Export and Send to Investigation.
"""

from pathlib import Path
from typing import Any, Optional, Sequence

import duckdb
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import SystemColumn
from usfds_core.domain.schemas.system_metadata import resolve_canonical_column
from usfds_core.services.warehouse.project_warehouse import create_bounded_duckdb_connection
from usfds_core.storage.base_storage import IFileStorage

_ACTION_RANK_SQL = "CASE action WHEN 'REJECT' THEN 0 WHEN 'REVIEW' THEN 1 WHEN 'ALLOW' THEN 2 ELSE 3 END"


def _ident(name: str) -> str:
	return '"' + name.replace('"', '""') + '"'


def _literal(value: str) -> str:
	return "'" + str(value).replace("'", "''") + "'"


class _PredictionSource:
	"""Opens `path` in a bounded DuckDB connection as view `src` (+ `__idx` = row position) and CTE `calc`."""

	def __init__(self, conn: duckdb.DuckDBPyConnection, path: Path):
		self.conn = conn
		described = conn.execute(f"DESCRIBE SELECT * FROM read_parquet({_literal(path.as_posix())})").fetchall()
		self.columns = [row[0] for row in described]
		self.types = {row[0]: str(row[1]) for row in described}
		conn.execute(
			f"CREATE VIEW src AS SELECT *, file_row_number AS __idx "
			f"FROM read_parquet({_literal(path.as_posix())}, file_row_number = true)"
		)
		self.calc_sql = self._calc_sql()

	def _calc_sql(self) -> str:
		cols = self.columns
		id_col = resolve_canonical_column(cols, SystemColumn.EVENT_ID)
		user_col = resolve_canonical_column(cols, SystemColumn.USER_ID)
		amt_col = resolve_canonical_column(cols, SystemColumn.AMOUNT)

		ev = f"COALESCE(CAST({_ident(id_col)} AS VARCHAR), CAST(__idx + 1 AS VARCHAR))" if id_col else "CAST(__idx + 1 AS VARCHAR)"
		usr = f"COALESCE(CAST({_ident(user_col)} AS VARCHAR), '—')" if user_col else "'—'"
		amount = f"COALESCE(TRY_CAST({_ident(amt_col)} AS DOUBLE), 0.0)" if amt_col else "0.0"
		amount = f"CASE WHEN isnan({amount}) THEN 0.0 ELSE {amount} END"

		score_col = "model_score" if "model_score" in cols else ("fraud_probability" if "fraud_probability" in cols else None)
		score = f"COALESCE(TRY_CAST({_ident(score_col)} AS DOUBLE), 0.0)" if score_col else "0.0"
		score = f"CASE WHEN isnan({score}) THEN 0.0 ELSE {score} END"

		fallback_action = "CASE WHEN \"prediction\" = 1 THEN 'REVIEW' ELSE 'ALLOW' END" if "prediction" in cols else "'ALLOW'"
		action = (
			f"UPPER(COALESCE(NULLIF(CAST(\"final_action\" AS VARCHAR), ''), {fallback_action}))"
			if "final_action" in cols
			else f"UPPER({fallback_action})"
		)

		empty = "[]::VARCHAR[]"
		codes = empty
		if "triggered_rules" in cols:
			t = self.types["triggered_rules"]
			if t == "VARCHAR":
				codes = (
					"CASE WHEN json_valid(\"triggered_rules\") AND json_type(\"triggered_rules\") = 'ARRAY' "
					f"THEN CAST(from_json(\"triggered_rules\", '[\"VARCHAR\"]') AS VARCHAR[]) ELSE {empty} END"
				)
			elif t.endswith("[]"):
				codes = "list_transform(\"triggered_rules\", x -> CAST(x AS VARCHAR))"
		return (
			f"calc AS (SELECT __idx, {ev} AS ev, {usr} AS usr, {amount} AS amount, {score} AS score, "
			f"{action} AS action, COALESCE({codes}, {empty}) AS codes FROM src)"
		)


def _open(storage: IFileStorage, output_path: str):
	return storage.open_local_path(output_path)


def query_prediction_results(
	storage: IFileStorage,
	output_path: str,
	action_filter: Optional[str] = None,
	rule_code: Optional[str] = None,
	search: Optional[str] = None,
	min_score: Optional[float] = None,
	max_score: Optional[float] = None,
	limit: int = 200,
	offset: int = 0,
) -> tuple[int, list[dict[str, Any]]]:
	"""Return (total matching rows, page of full raw rows incl. `__idx`), ordered REJECT > REVIEW > ALLOW, score, amount."""
	conn = create_bounded_duckdb_connection()
	try:
		with _open(storage, output_path) as path:
			source = _PredictionSource(conn, path)
			where: list[str] = []
			params: list[Any] = []
			if action_filter:
				af = action_filter.strip().upper()
				if af == "FLAGGED":
					where.append("action IN ('REJECT', 'REVIEW')")
				elif af in ("REJECT", "REVIEW", "ALLOW"):
					where.append("action = ?")
					params.append(af)
			if rule_code and rule_code.strip():
				where.append("list_contains(codes, ?)")
				params.append(rule_code.strip())
			if min_score is not None:
				where.append("score >= ?")
				params.append(min_score)
			if max_score is not None:
				where.append("score <= ?")
				params.append(max_score)
			if search and search.strip():
				q = search.strip().lower()
				where.append("(contains(lower(ev), ?) OR contains(lower(usr), ?))")
				params.extend([q, q])
			clause = (" WHERE " + " AND ".join(where)) if where else ""

			total = int(conn.execute(f"WITH {source.calc_sql} SELECT COUNT(*) FROM calc{clause}", params).fetchone()[0])
			page_idx = [
				r[0]
				for r in conn.execute(
					f"WITH {source.calc_sql} SELECT __idx FROM calc{clause} "
					f"ORDER BY {_ACTION_RANK_SQL}, round(score, 4) DESC, round(amount, 2) DESC, __idx "
					"LIMIT ? OFFSET ?",
					[*params, limit, offset],
				).fetchall()
			]
			if not page_idx:
				return total, []
			cursor = conn.execute("SELECT * FROM src WHERE __idx IN (SELECT unnest(?))", [page_idx])
			names = [d[0] for d in cursor.description]
			by_idx = {row[names.index("__idx")]: dict(zip(names, row)) for row in cursor.fetchall()}
			return total, [by_idx[i] for i in page_idx]
	finally:
		conn.close()


def fetch_prediction_events(storage: IFileStorage, output_path: str, event_ids: Sequence[str]) -> pd.DataFrame:
	"""Raw rows whose event id is in `event_ids` (duplicates in the file are all returned)."""
	conn = create_bounded_duckdb_connection()
	try:
		with _open(storage, output_path) as path:
			source = _PredictionSource(conn, path)
			frame = conn.execute(
				f"WITH {source.calc_sql} SELECT s.* EXCLUDE (__idx) FROM src s JOIN calc c USING (__idx) "
				"WHERE c.ev IN (SELECT unnest(?)) ORDER BY s.__idx",
				[list(dict.fromkeys(str(e) for e in event_ids))],
			).df()
			return frame
	finally:
		conn.close()


def export_prediction_results(
	storage: IFileStorage,
	output_path: str,
	dest_path: Path,
	file_format: str = "csv",
	only_flagged: bool = False,
) -> None:
	"""Write the (optionally flagged-only) results to `dest_path` as CSV or Parquet without loading them in Python."""
	conn = create_bounded_duckdb_connection()
	try:
		with _open(storage, output_path) as path:
			columns = [r[0] for r in conn.execute(f"DESCRIBE SELECT * FROM read_parquet({_literal(path.as_posix())})").fetchall()]
			where = ' WHERE "is_flagged" = 1' if only_flagged and "is_flagged" in columns else ""
			fmt = "PARQUET" if file_format.strip().lower() == "parquet" else "CSV, HEADER"
			conn.execute(
				f"COPY (SELECT * FROM read_parquet({_literal(path.as_posix())}){where}) "
				f"TO {_literal(dest_path.as_posix())} (FORMAT {fmt})"
			)
	finally:
		conn.close()
