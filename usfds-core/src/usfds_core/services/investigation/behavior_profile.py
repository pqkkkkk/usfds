from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Sequence

import duckdb
import pandas as pd

from usfds_core.domain.entities.case import Case, CaseStatus
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.schemas.preprocessing_config import SystemColumn
from usfds_core.domain.schemas.system_metadata import resolve_canonical_column
from usfds_core.services.warehouse.project_warehouse import (
	OPTIONAL_ENTITY_COLUMNS,
	ProjectWarehouse,
	create_bounded_duckdb_connection,
)
from usfds_core.storage.base_storage import IFileStorage


def _ident(name: str) -> str:
	return '"' + name.replace('"', '""') + '"'


def _literal(value: str) -> str:
	return "'" + str(value).replace("'", "''") + "'"


def _to_aware_utc(value: datetime) -> datetime:
	dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
	return dt.astimezone(timezone.utc)


def _naive_utc_iso(value: datetime) -> str:
	return _to_aware_utc(value).replace(tzinfo=None).isoformat(sep=" ")


def _format_utc_iso(value: Any) -> str:
	if isinstance(value, datetime):
		return _to_aware_utc(value).isoformat()
	ts = pd.Timestamp(value)
	ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
	return ts.isoformat()


def build_behavior_profile_from_duckdb(
	conn: duckdb.DuckDBPyConnection,
	table: str,
	case: Case,
	days: int = 30,
) -> dict:
	"""Compute the 30/90-day baseline comparison and transaction timeline via DuckDB SQL."""
	if days not in {30, 90}:
		raise ValueError("Baseline window must be 30 or 90 days")

	table_cols = {row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()}
	required = {"event_id", "user_id", "tx_timestamp", "amount"}
	if not required.issubset(table_cols):
		raise ValueError("Source lacks required transaction columns")

	current_dt = _to_aware_utc(case.tx_timestamp)
	current_iso = current_dt.replace(tzinfo=None).isoformat(sep=" ")
	start_iso = (current_dt - timedelta(days=days)).replace(tzinfo=None).isoformat(sep=" ")

	conn.execute(
		f"""
		CREATE OR REPLACE TEMP VIEW _bp_valid AS
		SELECT *
		FROM {table}
		WHERE tx_timestamp IS NOT NULL
		  AND amount IS NOT NULL
		  AND isfinite(CAST(amount AS DOUBLE))
		  AND user_id IS NOT NULL
		  AND event_id IS NOT NULL
		"""
	)

	history_count = int(
		conn.execute(
			"""
			SELECT COUNT(*)
			FROM _bp_valid
			WHERE CAST(tx_timestamp AS TIMESTAMP) >= CAST(? AS TIMESTAMP)
			  AND CAST(tx_timestamp AS TIMESTAMP) < CAST(? AS TIMESTAMP)
			  AND CAST(user_id AS VARCHAR) = ?
			""",
			[start_iso, current_iso, case.user_id],
		).fetchone()[0]
	)
	cold_start = history_count == 0

	if cold_start:
		baseline_where = (
			"CAST(tx_timestamp AS TIMESTAMP) >= CAST(? AS TIMESTAMP) "
			"AND CAST(tx_timestamp AS TIMESTAMP) < CAST(? AS TIMESTAMP)"
		)
		baseline_params: list[Any] = [start_iso, current_iso]
	else:
		baseline_where = (
			"CAST(tx_timestamp AS TIMESTAMP) >= CAST(? AS TIMESTAMP) "
			"AND CAST(tx_timestamp AS TIMESTAMP) < CAST(? AS TIMESTAMP) "
			"AND CAST(user_id AS VARCHAR) = ?"
		)
		baseline_params = [start_iso, current_iso, case.user_id]

	stats_row = conn.execute(
		f"""
		SELECT COUNT(*), AVG(CAST(amount AS DOUBLE)), MAX(CAST(amount AS DOUBLE))
		FROM _bp_valid
		WHERE {baseline_where}
		""",
		baseline_params,
	).fetchone()
	baseline_count = int(stats_row[0])
	average = float(stats_row[1]) if stats_row[1] is not None else None
	maximum = float(stats_row[2]) if stats_row[2] is not None else None

	hour_rows = conn.execute(
		f"""
		SELECT CAST(EXTRACT(HOUR FROM CAST(tx_timestamp AS TIMESTAMP)) AS INTEGER) AS hr, COUNT(*) AS cnt
		FROM _bp_valid
		WHERE {baseline_where}
		GROUP BY hr
		ORDER BY cnt DESC, hr ASC
		LIMIT 3
		""",
		baseline_params,
	).fetchall()
	hours = [int(row[0]) for row in hour_rows]

	comparison: list[dict[str, Any]] = [
		{
			"field": "amount",
			"current": case.amount,
			"baseline": average,
			"is_anomalous": average is not None and average > 0 and case.amount >= 3 * average,
		},
		{
			"field": "hour_utc",
			"current": current_dt.hour,
			"baseline": hours,
			"is_anomalous": bool(hours) and current_dt.hour not in hours,
		},
	]

	for column in OPTIONAL_ENTITY_COLUMNS:
		if column not in table_cols:
			continue
		ident = _ident(column)
		known = [
			str(row[0])
			for row in conn.execute(
				f"""
				SELECT DISTINCT TRIM(CAST({ident} AS VARCHAR)) AS val
				FROM _bp_valid
				WHERE {baseline_where}
				  AND {ident} IS NOT NULL
				  AND TRIM(CAST({ident} AS VARCHAR)) <> ''
				ORDER BY val ASC
				LIMIT 20
				""",
				baseline_params,
			).fetchall()
		]
		value = case.attributes.get(column)
		if value is None:
			match = conn.execute(
				f"""
				SELECT TRIM(CAST({ident} AS VARCHAR))
				FROM _bp_valid
				WHERE CAST(event_id AS VARCHAR) = ?
				  AND {ident} IS NOT NULL
				  AND TRIM(CAST({ident} AS VARCHAR)) <> ''
				LIMIT 1
				""",
				[case.event_id],
			).fetchone()
			if match is not None:
				value = str(match[0])
		comparison.append({
			"field": column,
			"current": value,
			"baseline": known,
			"is_anomalous": value is not None and bool(known) and str(value) not in known,
		})

	timeline_where = (
		"CAST(user_id AS VARCHAR) = ? "
		"AND CAST(tx_timestamp AS TIMESTAMP) >= CAST(? AS TIMESTAMP) "
		"AND CAST(tx_timestamp AS TIMESTAMP) <= CAST(? AS TIMESTAMP)"
	)
	timeline_params = [case.user_id, start_iso, current_iso]
	timeline_total = int(
		conn.execute(f"SELECT COUNT(*) FROM _bp_valid WHERE {timeline_where}", timeline_params).fetchone()[0]
	)
	timeline_rows = conn.execute(
		f"""
		SELECT CAST(event_id AS VARCHAR), CAST(tx_timestamp AS TIMESTAMP), CAST(amount AS DOUBLE)
		FROM _bp_valid
		WHERE {timeline_where}
		ORDER BY CAST(tx_timestamp AS TIMESTAMP) DESC, CAST(event_id AS VARCHAR) DESC
		LIMIT 500
		""",
		timeline_params,
	).fetchall()
	timeline_rows.reverse()
	timeline = [
		{
			"event_id": str(ev_id),
			"timestamp": _format_utc_iso(ts_val),
			"amount": float(amt),
			"is_current": str(ev_id) == case.event_id,
		}
		for ev_id, ts_val, amt in timeline_rows
	]

	return {
		"available": baseline_count > 0,
		"cold_start": cold_start,
		"source": "POPULATION" if cold_start else "USER",
		"days": days,
		"history_count": history_count,
		"avg_amount": average,
		"max_amount": maximum,
		"transactions_per_day": history_count / days if not cold_start else None,
		"common_hours_utc": hours,
		"comparison": comparison,
		"timeline": timeline,
		"timeline_truncated": timeline_total > 500,
	}


def build_behavior_profile_from_warehouse(
	warehouse: ProjectWarehouse,
	jobs: Sequence[DetectionJob],
	case: Case,
	days: int = 30,
) -> dict:
	"""Query Project Fact Warehouse via bounded DuckDB for Workbench behavior profile & timeline."""
	if days not in {30, 90}:
		raise ValueError("Baseline window must be 30 or 90 days")
	current_dt = _to_aware_utc(case.tx_timestamp)
	start_dt = current_dt - timedelta(days=days)
	conn = create_bounded_duckdb_connection()
	try:
		warehouse.load_fact_table(conn, jobs, date_from=start_dt, date_to=current_dt, table="wb_facts")
		return build_behavior_profile_from_duckdb(conn, "wb_facts", case, days=days)
	finally:
		conn.close()


def build_behavior_profile_from_storage_file(
	storage: IFileStorage,
	storage_path: str,
	case: Case,
	days: int = 30,
) -> dict:
	"""Fallback DuckDB query over a single mapped/prediction artifact when warehouse facts are absent."""
	if days not in {30, 90}:
		raise ValueError("Baseline window must be 30 or 90 days")
	conn = create_bounded_duckdb_connection()
	try:
		with storage.open_local_path(storage_path) as local_path:
			reader = (
				f"read_csv_auto({_literal(local_path.as_posix())})"
				if storage_path.lower().endswith(".csv")
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
			projections = [
				f"CAST({_ident(ev_col)} AS VARCHAR) AS event_id",  # type: ignore[arg-type]
				f"CAST({_ident(user_col)} AS VARCHAR) AS user_id",  # type: ignore[arg-type]
				f"COALESCE(TRY_CAST({ts_ident} AS TIMESTAMPTZ) AT TIME ZONE 'UTC', TRY_CAST({ts_ident} AS TIMESTAMP)) AS tx_timestamp",
				f"TRY_CAST({_ident(amt_col)} AS DOUBLE) AS amount",  # type: ignore[arg-type]
			]
			for entity_col in OPTIONAL_ENTITY_COLUMNS:
				resolved = resolve_canonical_column(cols, entity_col)
				if resolved:
					projections.append(f"CAST({_ident(resolved)} AS VARCHAR) AS {entity_col}")
			conn.execute(f"CREATE OR REPLACE TEMP VIEW artifact_facts AS SELECT {', '.join(projections)} FROM {reader}")
			return build_behavior_profile_from_duckdb(conn, "artifact_facts", case, days=days)
	finally:
		conn.close()


def build_behavior_profile(frame: pd.DataFrame, case: Case, days: int = 30) -> dict:
	if days not in {30, 90}:
		raise ValueError("Baseline window must be 30 or 90 days")
	required = {"event_id", "user_id", "timestamp", "amount"}
	if not required.issubset(frame.columns):
		raise ValueError("Artifact must contain event_id, user_id, timestamp and amount")
	data = frame.copy()
	data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
	data["amount"] = pd.to_numeric(data["amount"], errors="coerce")
	data = data.dropna(subset=["timestamp", "amount", "user_id", "event_id"])
	data = data[data["amount"].map(isfinite)]
	current = pd.Timestamp(case.tx_timestamp)
	current = current.tz_localize("UTC") if current.tzinfo is None else current.tz_convert("UTC")
	start = current - pd.Timedelta(days=days)
	past = data[(data["timestamp"] >= start) & (data["timestamp"] < current)]
	history = past[past["user_id"].astype(str) == case.user_id]
	cold_start = history.empty
	baseline = past if cold_start else history
	average = float(baseline["amount"].mean()) if not baseline.empty else None
	maximum = float(baseline["amount"].max()) if not baseline.empty else None
	hours = [int(hour) for hour in baseline["timestamp"].dt.hour.value_counts().head(3).index]
	comparison = [{"field": "amount", "current": case.amount, "baseline": average,
		"is_anomalous": average is not None and average > 0 and case.amount >= 3 * average},
		{"field": "hour_utc", "current": current.hour, "baseline": hours,
		 "is_anomalous": bool(hours) and current.hour not in hours}]
	for column in OPTIONAL_ENTITY_COLUMNS:
		if column not in data.columns:
			continue
		known = sorted(set(baseline[column].dropna().astype(str)))
		value = case.attributes.get(column)
		if value is None:
			matching = data[data["event_id"].astype(str) == case.event_id]
			if not matching.empty and pd.notna(matching.iloc[0][column]):
				value = str(matching.iloc[0][column])
		comparison.append({"field": column, "current": value, "baseline": known[:20],
			"is_anomalous": value is not None and bool(known) and str(value) not in known})
	user_timeline = data[(data["user_id"].astype(str) == case.user_id) & (data["timestamp"] >= start) & (data["timestamp"] <= current)]
	timeline = [{"event_id": str(row.event_id), "timestamp": row.timestamp.isoformat(), "amount": float(row.amount),
		"is_current": str(row.event_id) == case.event_id} for row in user_timeline.sort_values("timestamp").tail(500).itertuples()]
	return {"available": not baseline.empty, "cold_start": cold_start, "source": "POPULATION" if cold_start else "USER",
		"days": days, "history_count": len(history), "avg_amount": average, "max_amount": maximum,
		"transactions_per_day": len(history) / days if not cold_start else None,
		"common_hours_utc": hours, "comparison": comparison, "timeline": timeline,
		"timeline_truncated": len(user_timeline) > 500}


def build_rule_draft(case: Case, raw_schema: dict | None) -> dict:
	if case.status != CaseStatus.RESOLVED_FRAUD:
		raise ValueError("Only confirmed fraud cases can seed a rule draft")
	columns = (raw_schema or {}).get("columns", {})
	clauses, selected = [], set()
	for feature in sorted(case.feature_contributions, key=lambda item: item["contribution"], reverse=True):
		name = feature["feature_name"]
		value = case.attributes.get(name)
		if feature["contribution"] <= 0 or name not in columns or value is None or name in selected:
			continue
		numeric = columns[name].get("logical_type") == "NUMERIC"
		if numeric and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)):
			continue
		clauses.append({">=" if numeric else "==": [{"var": name}, value]})
		selected.add(name)
		if len(clauses) == 3:
			break
	return {"condition": {"and": clauses} if clauses else None, "action": "REVIEW", "status": "DRAFT",
		"dataset_artifact_id": str(case.dataset_artifact_id) if case.dataset_artifact_id else None,
		"detection_job_id": str(case.detection_job_id) if case.detection_job_id else None, "source_case_id": str(case.case_id),
		"name": f"Draft from {case.case_code}", "message": "Review thresholds before saving" if clauses else "No eligible RAW features; build conditions manually"}
