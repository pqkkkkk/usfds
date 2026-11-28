"""DuckDB OLAP Analytical Engine for Insight & Report Module (SUC-22, SUC-23, SUC-24)."""

from datetime import datetime, timezone
import json
import math
from typing import Any, Optional

import duckdb
import numpy as np
import pandas as pd

from usfds_core.domain.entities.case import Case, CaseStatus, EntityBlacklist
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.services.warehouse.normalization import extract_hour_utc as _extract_hour_utc
from usfds_core.services.warehouse.normalization import safe_float as _safe_float
from usfds_core.services.warehouse.project_warehouse import ProjectWarehouse, create_bounded_duckdb_connection
from usfds_core.storage.base_storage import IFileStorage

SLA_LIMITS_HOURS: dict[str, Optional[float]] = {
	"CRITICAL": 4.0,
	"HIGH": 24.0,
	"MEDIUM": 72.0,
	"LOW": None,
}

TOP_K_MILESTONES: tuple[int, ...] = (1, 2, 5, 10, 20, 30, 50, 100)

SEGMENT_DIMENSION_LABELS: dict[str, str] = {
	"amount_brackets": "Khoảng số tiền",
	"merchant_category": "Ngành hàng (MCC)",
	"merchant_id": "Đơn vị chấp nhận thẻ (Merchant)",
	"device_id": "Thiết bị",
	"ip_address": "Địa chỉ IP",
	"card_id": "Thẻ thanh toán",
}

FRAUD_TYPOLOGY_LABELS: dict[str, str] = {
	"CARD_TESTING": "Card Testing / Micro-probing",
	"VELOCITY_ATTACK": "Velocity Attack",
	"ACCOUNT_TAKEOVER": "Account Takeover (ATO)",
	"DEVICE_SHARING_RING": "Device-Sharing Fraud Ring",
	"COLLUSIVE_MERCHANT": "Collusive Merchant",
	"OTHER_FRAUD": "High-Value / Other Anomaly",
}

FP_REASON_LABELS: dict[str, str] = {
	"LEGITIMATE_UNUSUAL_SPENDING": "Legitimate Travel / High Spend",
	"CUSTOMER_CONFIRMED": "Customer Confirmed Legitimate",
	"OVERLY_STRICT_RULE": "Overly Strict Rule Threshold",
	"MODEL_FALSE_ALARM": "Model False Alarm",
	"OTHER_LEGITIMATE": "Other Legitimate Activity",
}

AMOUNT_BRACKET_SPECS: list[tuple[str, str, float, float]] = [
	("MICRO", "Micro (< $10)", 0.0, 10.0),
	("SMALL", "Small ($10–$100)", 10.0, 100.0),
	("MEDIUM", "Medium ($100–$500)", 100.0, 500.0),
	("LARGE", "Large ($500–$2,000)", 500.0, 2000.0),
	("HIGH_VALUE", "High-Value (> $2,000)", 2000.0, float("inf")),
]


# DEPRECATED [26-11-22] ISS-012: helpers moved to usfds_core.services.warehouse.normalization (shared with the warehouse).
# def _safe_float(val: Any, default: float = 0.0) -> float:
# 	if val is None:
# 		return default
# 	try:
# 		res = float(val)
# 		return default if not math.isfinite(res) else res
# 	except (ValueError, TypeError):
# 		return default
#
#
# def _parse_rule_codes(raw_val: Any) -> list[str]:
# 	if raw_val is None:
# 		return []
# 	if isinstance(raw_val, list):
# 		out: list[str] = []
# 		for item in raw_val:
# 			if isinstance(item, dict) and item.get("rule_code"):
# 				out.append(str(item["rule_code"]))
# 			elif isinstance(item, str) and item.strip():
# 				out.append(item.strip())
# 		return sorted(set(out))
# 	if isinstance(raw_val, str):
# 		text = raw_val.strip()
# 		if not text:
# 			return []
# 		try:
# 			parsed = json.loads(text)
# 			return _parse_rule_codes(parsed)
# 		except Exception:
# 			return [text]
# 	return []
#
#
# def _extract_hour_utc(raw_ts: Any) -> int:
# 	if raw_ts is None:
# 		return 0
# 	if isinstance(raw_ts, datetime):
# 		dt = raw_ts if raw_ts.tzinfo else raw_ts.replace(tzinfo=timezone.utc)
# 		return dt.astimezone(timezone.utc).hour
# 	try:
# 		ts = pd.to_datetime(raw_ts, utc=True, errors="coerce")
# 		if pd.isna(ts):
# 			num = _safe_float(raw_ts, -1.0)
# 			if num >= 0:
# 				return int((num // 3600) % 24)
# 			return 0
# 		return int(ts.hour)
# 	except Exception:
# 		return 0


class DuckDBInsightEngine:
	"""In-memory DuckDB OLAP engine joining DetectionJob Parquet outputs with Investigation Cases."""

	def __init__(
		self,
		file_storage: Optional[IFileStorage],
		jobs: list[DetectionJob],
		cases: list[Case],
		rules: Optional[list[tuple[Rule, Optional[RuleVersion]]]] = None,
		blacklist: Optional[list[EntityBlacklist]] = None,
		label_source: str = "VERIFIED_WITH_DATASET_FALLBACK",
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
		model_labels: Optional[dict[str, dict[str, str]]] = None,
	):
		self.file_storage = file_storage
		self.jobs = jobs
		self.cases = cases
		self.rules = rules or []
		self.blacklist = blacklist or []
		self.label_source = (
			"VERIFIED_ONLY"
			if str(label_source).upper() == "VERIFIED_ONLY"
			else "VERIFIED_WITH_DATASET_FALLBACK"
		)
		self.date_from = date_from
		self.date_to = date_to
		self.model_labels = model_labels or {}
		self.conn = create_bounded_duckdb_connection()
		self.has_dataset_labels = False
		self._build_unified_transactions_table()

	def _build_unified_transactions_table(self) -> None:
		"""Materializes `v_transactions` in DuckDB: warehouse facts (latest scan per event) joined with Case ground truth."""
		warehouse = ProjectWarehouse(self.file_storage)
		warehouse.sync_missing_jobs(self.jobs)
		warehouse.load_fact_table(self.conn, self.jobs, date_from=self.date_from, date_to=self.date_to, table="facts")
		self.has_dataset_labels = bool(self.conn.execute("SELECT COALESCE(BOOL_OR(has_label_col), FALSE) FROM facts").fetchone()[0])
		self._load_cases_table()
		fallback = self.label_source == "VERIFIED_WITH_DATASET_FALLBACK"
		self.conn.execute(f"""
			CREATE OR REPLACE TABLE v_transactions AS
			SELECT
				f.job_id, f.job_name, f.job_created_at, f.model_version_id, f.score_threshold, f.event_id,
				COALESCE(c.c_user_id, f.user_id) AS user_id,
				COALESCE(c.c_tx_timestamp, f.tx_timestamp) AS tx_timestamp,
				COALESCE(c.c_hour, f.hour_utc) AS hour_utc,
				COALESCE(c.c_amount, f.amount) AS amount,
				COALESCE(c.c_model_score, f.model_score) AS model_score,
				f.rule_action,
				COALESCE(c.c_final_action, f.final_action) AS final_action,
				CASE WHEN c.event_id IS NOT NULL THEN 1 ELSE f.is_flagged END AS is_flagged,
				CASE WHEN COALESCE(len(c.c_rule_codes), 0) > 0 THEN 1 ELSE f.has_rule_hit END AS has_rule_hit,
				f.has_ai_hit,
				CAST(to_json(list_sort(list_distinct(list_concat(
					COALESCE(f.rule_codes, []::VARCHAR[]), COALESCE(c.c_rule_codes, []::VARCHAR[])
				)))) AS VARCHAR) AS rule_codes_json,
				CASE WHEN c.event_id IS NULL THEN 0 ELSE 1 END AS has_case,
				COALESCE(c.case_id, '') AS case_id,
				COALESCE(c.case_status, '') AS case_status,
				COALESCE(c.case_priority, '') AS case_priority,
				COALESCE(c.resolution_reason, '') AS resolution_reason,
				COALESCE(c.verified_label, -1) AS verified_label,
				f.dataset_label AS dataset_label,
				CASE
					WHEN c.verified_label IS NOT NULL THEN c.verified_label
					WHEN {fallback} AND f.dataset_label <> -1 THEN f.dataset_label
					ELSE -1
				END AS effective_label,
				CASE
					WHEN c.verified_label IS NOT NULL THEN 'VERIFIED_CASE'
					WHEN {fallback} AND f.dataset_label <> -1 THEN 'DATASET_FALLBACK'
					ELSE 'UNVERIFIED'
				END AS label_origin,
				NULLIF(TRIM(COALESCE(f.device_id, c.c_device_id, '')), '') AS device_id,
				NULLIF(TRIM(COALESCE(f.ip_address, c.c_ip_address, '')), '') AS ip_address,
				NULLIF(TRIM(COALESCE(f.card_id, c.c_card_id, '')), '') AS card_id,
				NULLIF(TRIM(COALESCE(f.merchant_id, c.c_merchant_id, '')), '') AS merchant_id,
				NULLIF(TRIM(COALESCE(f.merchant_category, c.c_merchant_category, '')), '') AS merchant_category
			FROM facts f
			LEFT JOIN v_cases c ON c.event_id = f.event_id
			UNION ALL
			-- Cases whose event is not in the loaded facts (e.g. cases created by intake) still count.
			SELECT
				c.fb_job_id, c.fb_job_name, c.fb_job_created_at, c.fb_model_version_id, CAST(0.5 AS DOUBLE), c.event_id,
				c.c_user_id, c.c_tx_timestamp, c.c_hour, c.fb_amount, c.fb_model_score, c.fb_rule_action, c.c_final_action,
				1, c.fb_has_rule_hit, c.fb_has_ai_hit, CAST(to_json(c.c_rule_codes) AS VARCHAR),
				1, c.case_id, c.case_status, c.case_priority, c.resolution_reason,
				COALESCE(c.verified_label, -1), -1, COALESCE(c.verified_label, -1),
				CASE WHEN c.verified_label IS NOT NULL THEN 'VERIFIED_CASE' ELSE 'UNVERIFIED' END,
				NULLIF(TRIM(COALESCE(c.c_device_id, '')), ''),
				NULLIF(TRIM(COALESCE(c.c_ip_address, '')), ''),
				NULLIF(TRIM(COALESCE(c.c_card_id, '')), ''),
				NULLIF(TRIM(COALESCE(c.c_merchant_id, '')), ''),
				NULLIF(TRIM(COALESCE(c.c_merchant_category, '')), '')
			FROM v_cases c
			WHERE c.event_id NOT IN (SELECT event_id FROM facts)
		""")

	def _load_cases_table(self) -> None:
		"""Cases are small (DB rows): precompute per-case values in Python and expose them as the `v_cases` table."""
		self.conn.execute("""
			CREATE OR REPLACE TABLE v_cases (
				event_id VARCHAR, c_user_id VARCHAR, c_tx_timestamp TIMESTAMP, c_hour INTEGER, c_amount DOUBLE, c_model_score DOUBLE,
				c_final_action VARCHAR, c_rule_codes VARCHAR[], case_id VARCHAR, case_status VARCHAR,
				case_priority VARCHAR, resolution_reason VARCHAR, verified_label INTEGER,
				fb_job_id VARCHAR, fb_job_name VARCHAR, fb_job_created_at VARCHAR, fb_model_version_id VARCHAR,
				fb_amount DOUBLE, fb_model_score DOUBLE, fb_rule_action VARCHAR, fb_has_rule_hit INTEGER, fb_has_ai_hit INTEGER,
				c_device_id VARCHAR, c_ip_address VARCHAR, c_card_id VARCHAR, c_merchant_id VARCHAR, c_merchant_category VARCHAR
			)
		""")
		cases_by_event = {str(c.event_id): c for c in self.cases}  # last case wins, as before
		rows = []
		for ev_id, case in cases_by_event.items():
			codes = list(case.triggered_rule_codes)
			m_score = _safe_float(case.model_score, 0.0) if case.model_score is not None else 0.0
			has_rule_hit = 1 if codes else 0
			ts_naive: Optional[str] = None
			if case.tx_timestamp is not None:
				dt = case.tx_timestamp if case.tx_timestamp.tzinfo else case.tx_timestamp.replace(tzinfo=timezone.utc)
				ts_naive = dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
			attrs = case.attributes or {}
			rows.append({
				"event_id": ev_id,
				"c_user_id": case.user_id,
				"c_tx_timestamp": ts_naive,
				"c_hour": _extract_hour_utc(case.tx_timestamp),
				"c_amount": float(case.amount),
				"c_model_score": float(case.model_score) if case.model_score is not None else None,
				"c_final_action": case.final_action.value,
				"c_rule_codes_json": json.dumps(codes),
				"case_id": str(case.case_id),
				"case_status": case.status.value,
				"case_priority": case.priority.value,
				"resolution_reason": case.resolution_reason or "",
				"verified_label": case.verified_label,
				"fb_job_id": str(case.detection_job_id) if case.detection_job_id else "case-intake",
				"fb_job_name": f"Case Intake ({case.created_at.strftime('%Y-%m-%d')})",
				"fb_job_created_at": case.created_at.isoformat(),
				"fb_model_version_id": str(case.model_version_id) if case.model_version_id else "",
				"fb_amount": max(0.0, _safe_float(case.amount, 0.0)),
				"fb_model_score": m_score,
				"fb_rule_action": case.final_action.value if has_rule_hit else "ALLOW",
				"fb_has_rule_hit": has_rule_hit,
				"fb_has_ai_hit": 1 if (case.model_score is not None and m_score >= 0.5) else (1 if not has_rule_hit else 0),
				"c_device_id": str(attrs.get("device_id") or "") or None,
				"c_ip_address": str(attrs.get("ip_address") or "") or None,
				"c_card_id": str(attrs.get("card_id") or "") or None,
				"c_merchant_id": str(attrs.get("merchant_id") or "") or None,
				"c_merchant_category": str(attrs.get("merchant_category") or "") or None,
			})
		if not rows:
			return
		cases_df = pd.DataFrame(rows)  # noqa: F841  (referenced by name in the SQL below)
		self.conn.register("cases_df", cases_df)
		try:
			self.conn.execute("""
				INSERT INTO v_cases
				SELECT event_id, c_user_id, TRY_CAST(c_tx_timestamp AS TIMESTAMP), c_hour, c_amount, c_model_score, c_final_action,
					CAST(from_json(c_rule_codes_json, '["VARCHAR"]') AS VARCHAR[]), case_id, case_status,
					case_priority, resolution_reason, CAST(verified_label AS INTEGER),
					fb_job_id, fb_job_name, fb_job_created_at, fb_model_version_id,
					fb_amount, fb_model_score, fb_rule_action, fb_has_rule_hit, fb_has_ai_hit,
					CAST(c_device_id AS VARCHAR), CAST(c_ip_address AS VARCHAR), CAST(c_card_id AS VARCHAR),
					CAST(c_merchant_id AS VARCHAR), CAST(c_merchant_category AS VARCHAR)
				FROM cases_df
			""")
		finally:
			self.conn.unregister("cases_df")

	# DEPRECATED [26-11-22] ISS-012: replaced by _build_unified_transactions_table (warehouse facts + SQL join); kept for reference.
# 	def _read_parquet_bytes(self, storage_path: str) -> Optional[bytes]:
# 		if not storage_path:
# 			return None
# 		if self.file_storage and self.file_storage.exists(storage_path):
# 			try:
# 				return self.file_storage.read_bytes(storage_path)
# 			except Exception:
# 				return None
# 		return None
#
# 	def _build_unified_transactions_df(self) -> pd.DataFrame:
# 		"""Loads projected columns from DetectionJob parquet files and joins with Case ground-truth labels."""
# 		cases_by_event: dict[str, Case] = {str(c.event_id): c for c in self.cases}
# 		seen_events: set[str] = set()
# 		rows: list[dict[str, Any]] = []
#
# 		# Sort jobs chronologically so latest scan wins if an event_id was scanned multiple times
# 		sorted_jobs = sorted(
# 			self.jobs,
# 			key=lambda j: j.created_at or datetime.min.replace(tzinfo=timezone.utc),
# 		)
#
# 		for job in sorted_jobs:
# 			status_str = job.status.value if hasattr(job.status, "value") else str(job.status)
# 			if status_str != "COMPLETED" or not job.output_path:
# 				continue
# 			raw_bytes = self._read_parquet_bytes(job.output_path)
# 			if not raw_bytes:
# 				continue
# 			try:
# 				df = pd.read_parquet(io.BytesIO(raw_bytes))
# 			except Exception:
# 				continue
# 			if df.empty:
# 				continue
#
# 			id_col = resolve_canonical_column(df, SystemColumn.EVENT_ID)
# 			user_col = resolve_canonical_column(df, SystemColumn.USER_ID)
# 			ts_col = resolve_canonical_column(df, SystemColumn.TIMESTAMP)
# 			amt_col = resolve_canonical_column(df, SystemColumn.AMOUNT)
# 			lbl_col = resolve_canonical_column(df, SystemColumn.LABEL)
#
# 			if lbl_col is not None:
# 				self.has_dataset_labels = True
#
# 			threshold = _safe_float(job.score_threshold, 0.5)
# 			has_model = bool(job.model_version_id is not None or (job.summary_metrics or {}).get("has_model", True))
# 			job_id_str = str(job.job_id)
# 			job_name_str = job.job_name or f"Job-{job_id_str[:8]}"
# 			job_time_str = (job.created_at or datetime.now(timezone.utc)).isoformat()
# 			model_ver_str = str(job.model_version_id) if job.model_version_id else ""
#
# 			records = df.to_dict(orient="records")
# 			for idx, rec in enumerate(records):
# 				ev_raw = rec.get(id_col) if id_col and rec.get(id_col) is not None else f"{job_id_str}:{idx + 1}"
# 				ev_id = str(ev_raw)
# 				seen_events.add(ev_id)
#
# 				user_id = str(rec.get(user_col) if user_col and rec.get(user_col) is not None else "unknown")
# 				amount = max(0.0, _safe_float(rec.get(amt_col) if amt_col else 0.0, 0.0))
# 				m_score = min(1.0, max(0.0, _safe_float(rec.get("model_score", rec.get("fraud_probability", 0.0)), 0.0)))
#
# 				final_action = str(
# 					rec.get("final_action") or ("REVIEW" if rec.get("prediction") == 1 else "ALLOW")
# 				).upper()
# 				rule_action = str(rec.get("rule_action") or "ALLOW").upper()
# 				is_flagged = 1 if final_action in ("REJECT", "REVIEW") else 0
#
# 				rule_codes = _parse_rule_codes(rec.get("triggered_rules"))
# 				has_rule_hit = 1 if (len(rule_codes) > 0 or rule_action in ("REJECT", "REVIEW")) else 0
# 				has_ai_hit = 1 if (has_model and m_score >= threshold) else 0
#
# 				ds_label: Optional[int] = None
# 				if lbl_col and rec.get(lbl_col) is not None:
# 					try:
# 						lbl_val = int(float(rec[lbl_col]))
# 						if lbl_val in (0, 1):
# 							ds_label = lbl_val
# 					except (ValueError, TypeError):
# 						ds_label = None
#
# 				matched_case = cases_by_event.get(ev_id)
# 				verified_lbl = matched_case.verified_label if matched_case else None
# 				if matched_case and matched_case.triggered_rule_codes:
# 					rule_codes = sorted(set(rule_codes) | set(matched_case.triggered_rule_codes))
# 					if rule_codes:
# 						has_rule_hit = 1
#
# 				if verified_lbl is not None:
# 					eff_label: Optional[int] = verified_lbl
# 					lbl_origin = "VERIFIED_CASE"
# 				elif self.label_source == "VERIFIED_WITH_DATASET_FALLBACK" and ds_label is not None:
# 					eff_label = ds_label
# 					lbl_origin = "DATASET_FALLBACK"
# 				else:
# 					eff_label = None
# 					lbl_origin = "UNVERIFIED"
#
# 				hour_utc = (
# 					_extract_hour_utc(matched_case.tx_timestamp)
# 					if matched_case
# 					else _extract_hour_utc(rec.get(ts_col) if ts_col else None)
# 				)
#
# 				rows.append({
# 					"job_id": job_id_str,
# 					"job_name": job_name_str,
# 					"job_created_at": job_time_str,
# 					"model_version_id": model_ver_str,
# 					"score_threshold": threshold,
# 					"event_id": ev_id,
# 					"user_id": matched_case.user_id if matched_case else user_id,
# 					"hour_utc": hour_utc,
# 					"amount": float(matched_case.amount) if matched_case else amount,
# 					"model_score": float(matched_case.model_score) if (matched_case and matched_case.model_score is not None) else m_score,
# 					"rule_action": rule_action,
# 					"final_action": matched_case.final_action.value if matched_case else final_action,
# 					"is_flagged": 1 if matched_case else is_flagged,
# 					"has_rule_hit": has_rule_hit,
# 					"has_ai_hit": has_ai_hit,
# 					"rule_codes_json": json.dumps(rule_codes),
# 					"has_case": 1 if matched_case else 0,
# 					"case_id": str(matched_case.case_id) if matched_case else "",
# 					"case_status": matched_case.status.value if matched_case else "",
# 					"case_priority": matched_case.priority.value if matched_case else "",
# 					"resolution_reason": matched_case.resolution_reason or "" if matched_case else "",
# 					"verified_label": verified_lbl if verified_lbl is not None else -1,
# 					"dataset_label": ds_label if ds_label is not None else -1,
# 					"effective_label": eff_label if eff_label is not None else -1,
# 					"label_origin": lbl_origin,
# 				})
#
# 		# Fallback: Include any Case whose event_id was not present in loaded parquet files
# 		for case in self.cases:
# 			ev_id = str(case.event_id)
# 			if ev_id in seen_events:
# 				continue
# 			seen_events.add(ev_id)
# 			rule_codes = case.triggered_rule_codes
# 			m_score = _safe_float(case.model_score, 0.0) if case.model_score is not None else 0.0
# 			has_rule_hit = 1 if len(rule_codes) > 0 else 0
# 			has_ai_hit = 1 if (case.model_score is not None and m_score >= 0.5) else (1 if not has_rule_hit else 0)
# 			verified_lbl = case.verified_label
# 			rows.append({
# 				"job_id": str(case.detection_job_id) if case.detection_job_id else "case-intake",
# 				"job_name": f"Case Intake ({case.created_at.strftime('%Y-%m-%d')})",
# 				"job_created_at": case.created_at.isoformat(),
# 				"model_version_id": str(case.model_version_id) if case.model_version_id else "",
# 				"score_threshold": 0.5,
# 				"event_id": ev_id,
# 				"user_id": case.user_id,
# 				"hour_utc": _extract_hour_utc(case.tx_timestamp),
# 				"amount": max(0.0, _safe_float(case.amount, 0.0)),
# 				"model_score": m_score,
# 				"rule_action": case.final_action.value if has_rule_hit else "ALLOW",
# 				"final_action": case.final_action.value,
# 				"is_flagged": 1,
# 				"has_rule_hit": has_rule_hit,
# 				"has_ai_hit": has_ai_hit,
# 				"rule_codes_json": json.dumps(rule_codes),
# 				"has_case": 1,
# 				"case_id": str(case.case_id),
# 				"case_status": case.status.value,
# 				"case_priority": case.priority.value,
# 				"resolution_reason": case.resolution_reason or "",
# 				"verified_label": verified_lbl if verified_lbl is not None else -1,
# 				"dataset_label": -1,
# 				"effective_label": verified_lbl if verified_lbl is not None else -1,
# 				"label_origin": "VERIFIED_CASE" if verified_lbl is not None else "UNVERIFIED",
# 			})
#
# 		if not rows:
# 			return pd.DataFrame(columns=[
# 				"job_id", "job_name", "job_created_at", "model_version_id", "score_threshold",
# 				"event_id", "user_id", "hour_utc", "amount", "model_score", "rule_action",
# 				"final_action", "is_flagged", "has_rule_hit", "has_ai_hit", "rule_codes_json",
# 				"has_case", "case_id", "case_status", "case_priority", "resolution_reason",
# 				"verified_label", "dataset_label", "effective_label", "label_origin",
# 			])
#
# 		return pd.DataFrame(rows)

	def _has_full_ground_truth(self, gross_count: int, flagged_count: int, unflagged_known_count: int) -> bool:
		if self.label_source == "VERIFIED_ONLY":
			return False
		if gross_count > 0 and not self.has_dataset_labels and unflagged_known_count == 0 and (gross_count - flagged_count) > 0:
			return False
		return True

	def _compute_case_sla(self) -> dict[str, Any]:
		"""Computes Case MTTR (P50/P90), Backlog Aging, SLA breach counts, and Analyst consistency."""
		now_utc = datetime.now(timezone.utc)
		resolved_durations: list[float] = []
		aging_counts = {
			"LT_4H": {"bucket": "LT_4H", "label": "< 4 giờ", "count": 0, "amount": 0.0},
			"4H_24H": {"bucket": "4H_24H", "label": "4–24 giờ", "count": 0, "amount": 0.0},
			"1D_3D": {"bucket": "1D_3D", "label": "1–3 ngày", "count": 0, "amount": 0.0},
			"GT_3D": {"bucket": "GT_3D", "label": "> 3 ngày", "count": 0, "amount": 0.0},
		}
		sla_breach_count = 0
		eligible_sla_cases = 0
		analyst_map: dict[str, dict[str, Any]] = {}

		for c in self.cases:
			prio = c.priority.value if hasattr(c.priority, "value") else str(c.priority)
			sla_limit = SLA_LIMITS_HOURS.get(prio)
			created_at = c.created_at if c.created_at.tzinfo else c.created_at.replace(tzinfo=timezone.utc)
			is_resolved = c.status in (CaseStatus.RESOLVED_FRAUD, CaseStatus.RESOLVED_LEGITIMATE)

			elapsed_hours: Optional[float] = None
			if is_resolved and c.resolved_at is not None:
				res_at = c.resolved_at if c.resolved_at.tzinfo else c.resolved_at.replace(tzinfo=timezone.utc)
				elapsed_hours = max(0.0, (res_at - created_at).total_seconds() / 3600.0)
				resolved_durations.append(elapsed_hours)
			elif not is_resolved:
				age_hours = max(0.0, (now_utc - created_at).total_seconds() / 3600.0)
				elapsed_hours = age_hours
				bucket_key = (
					"LT_4H" if age_hours < 4.0
					else "4H_24H" if age_hours < 24.0
					else "1D_3D" if age_hours < 72.0
					else "GT_3D"
				)
				aging_counts[bucket_key]["count"] += 1
				aging_counts[bucket_key]["amount"] = round(aging_counts[bucket_key]["amount"] + float(c.amount), 2)

			is_breach = bool(sla_limit is not None and elapsed_hours is not None and elapsed_hours > sla_limit)
			if sla_limit is not None:
				eligible_sla_cases += 1
				if is_breach:
					sla_breach_count += 1

			if is_resolved:
				analyst = (c.resolved_by or "").strip() or "Chưa ghi nhận"
				a_stat = analyst_map.setdefault(analyst, {
					"analyst": analyst,
					"resolved_count": 0,
					"fraud_count": 0,
					"legit_count": 0,
					"sla_breach_count": 0,
					"_durations": [],
				})
				a_stat["resolved_count"] += 1
				if c.status == CaseStatus.RESOLVED_FRAUD:
					a_stat["fraud_count"] += 1
				else:
					a_stat["legit_count"] += 1
				if is_breach:
					a_stat["sla_breach_count"] += 1
				if elapsed_hours is not None:
					a_stat["_durations"].append(elapsed_hours)

		mttr_p50 = round(float(np.percentile(resolved_durations, 50)), 2) if resolved_durations else None
		mttr_p90 = round(float(np.percentile(resolved_durations, 90)), 2) if resolved_durations else None

		analyst_stats: list[dict[str, Any]] = []
		for a_stat in analyst_map.values():
			durs = a_stat.pop("_durations")
			res_cnt = a_stat["resolved_count"]
			a_stat["fraud_rate"] = round(a_stat["fraud_count"] / max(1, res_cnt), 4)
			a_stat["avg_mttr_hours"] = round(float(np.mean(durs)), 2) if durs else None
			a_stat["median_mttr_hours"] = round(float(np.percentile(durs, 50)), 2) if durs else None
			analyst_stats.append(a_stat)
		analyst_stats.sort(key=lambda x: (-x["resolved_count"], x["analyst"]))

		return {
			"mttr_p50_hours": mttr_p50,
			"mttr_p90_hours": mttr_p90,
			"resolved_with_duration_count": len(resolved_durations),
			"sla_breach_count": sla_breach_count,
			"eligible_sla_cases": eligible_sla_cases,
			"sla_breach_rate": round(sla_breach_count / eligible_sla_cases, 4) if eligible_sla_cases > 0 else 0.0,
			"sla_thresholds_hours": {k: v for k, v in SLA_LIMITS_HOURS.items() if v is not None},
			"aging_buckets": list(aging_counts.values()),
			"analyst_stats": analyst_stats,
		}

	def _compute_financial_trends(self, full_ground_truth: bool) -> tuple[list[dict[str, Any]], str]:
		"""Groups protection, missed fraud, and friction trends by tx_timestamp day (falls back to job when absent)."""
		has_ts = int(self.conn.execute("SELECT COUNT(*) FROM v_transactions WHERE tx_timestamp IS NOT NULL").fetchone()[0] or 0) > 0
		if has_ts:
			rows = self.conn.execute("""
				SELECT
					strftime(tx_timestamp, '%Y-%m-%d') AS day_key,
					COUNT(*) AS scanned_count,
					COALESCE(SUM(amount), 0.0) AS scanned_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS caught_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS confirmed_fraud_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS missed_fraud_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS false_positive_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = -1 THEN amount ELSE 0.0 END), 0.0) AS pending_review_amount
				FROM v_transactions
				WHERE tx_timestamp IS NOT NULL
				GROUP BY day_key
				ORDER BY day_key ASC
			""").fetchall()
			trends = []
			for day_key, sc_cnt, sc_amt, fl_cnt, caught_cnt, tp_amt, fn_amt, fp_amt, pend_amt in rows:
				sc_i = int(sc_cnt or 0)
				fl_i = int(fl_cnt or 0)
				c_i = int(caught_cnt or 0)
				day_str = str(day_key)
				trends.append({
					"date": day_str,
					"label": day_str,
					"granularity": "DAY",
					"job_id": day_str,
					"job_name": day_str,
					"created_at": f"{day_str}T00:00:00Z",
					"scanned_count": sc_i,
					"scanned_amount": round(float(sc_amt or 0.0), 2),
					"flagged_count": fl_i,
					"confirmed_fraud_amount": round(float(tp_amt or 0.0), 2),
					"missed_fraud_amount": round(float(fn_amt or 0.0), 2) if full_ground_truth else None,
					"false_positive_amount": round(float(fp_amt or 0.0), 2),
					"pending_review_amount": round(float(pend_amt or 0.0), 2),
					"flagged_rate": round(fl_i / max(1, sc_i), 4),
					"fraud_rate": round(c_i / max(1, sc_i), 4),
				})
			return trends, "DAY"

		rows = self.conn.execute("""
			SELECT
				job_id, job_name, MIN(job_created_at) AS created_at,
				COUNT(*) AS scanned_count,
				COALESCE(SUM(amount), 0.0) AS scanned_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS caught_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS confirmed_fraud_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS missed_fraud_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS false_positive_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = -1 THEN amount ELSE 0.0 END), 0.0) AS pending_review_amount
			FROM v_transactions
			GROUP BY job_id, job_name
			ORDER BY MIN(job_created_at) ASC
		""").fetchall()
		trends = []
		for j_id, j_name, created_at, sc_cnt, sc_amt, fl_cnt, caught_cnt, tp_amt, fn_amt, fp_amt, pend_amt in rows:
			sc_i = int(sc_cnt or 0)
			fl_i = int(fl_cnt or 0)
			c_i = int(caught_cnt or 0)
			trends.append({
				"date": str(created_at)[:10],
				"label": str(j_name),
				"granularity": "JOB",
				"job_id": str(j_id),
				"job_name": str(j_name),
				"created_at": str(created_at),
				"scanned_count": sc_i,
				"scanned_amount": round(float(sc_amt or 0.0), 2),
				"flagged_count": fl_i,
				"confirmed_fraud_amount": round(float(tp_amt or 0.0), 2),
				"missed_fraud_amount": round(float(fn_amt or 0.0), 2) if full_ground_truth else None,
				"false_positive_amount": round(float(fp_amt or 0.0), 2),
				"pending_review_amount": round(float(pend_amt or 0.0), 2),
				"flagged_rate": round(fl_i / max(1, sc_i), 4),
				"fraud_rate": round(c_i / max(1, sc_i), 4),
			})
		return trends, "JOB"

	def compute_executive_overview(self) -> dict[str, Any]:
		"""Computes SUC-22: 6 Executive KPIs, 4-Stage Monotonic Funnel, Daily Trends, and Case SLA/Aging."""
		agg = self.conn.execute("""
			SELECT
				COUNT(*) AS gross_count,
				COALESCE(SUM(amount), 0.0) AS gross_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN amount ELSE 0.0 END), 0.0) AS amount_at_risk,
				COALESCE(SUM(CASE WHEN final_action = 'REJECT' THEN 1 ELSE 0 END), 0) AS reject_count,
				COALESCE(SUM(CASE WHEN final_action = 'REVIEW' THEN 1 ELSE 0 END), 0) AS review_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS fraud_caught_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fraud_loss_prevented,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS fp_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS fp_friction_volume,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND final_action = 'REJECT' AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS hard_fp_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND final_action = 'REJECT' AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS hard_fp_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND final_action = 'REVIEW' AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS soft_fp_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND final_action = 'REVIEW' AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS soft_fp_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS fn_count,
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fn_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS tn_count,
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS tn_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label IN (0, 1) THEN 1 ELSE 0 END), 0) AS unflagged_known_count
			FROM v_transactions
		""").fetchone()

		gross_count = int(agg[0] or 0)
		gross_amount = round(float(agg[1] or 0.0), 2)
		flagged_count = int(agg[2] or 0)
		amount_at_risk = round(float(agg[3] or 0.0), 2)
		reject_count = int(agg[4] or 0)
		review_count = int(agg[5] or 0)
		tp_count = int(agg[6] or 0)
		fraud_loss_prevented = round(float(agg[7] or 0.0), 2)
		fp_count = int(agg[8] or 0)
		fp_friction_volume = round(float(agg[9] or 0.0), 2)
		hard_fp_count = int(agg[10] or 0)
		hard_fp_amount = round(float(agg[11] or 0.0), 2)
		soft_fp_count = int(agg[12] or 0)
		soft_fp_amount = round(float(agg[13] or 0.0), 2)
		fn_count = int(agg[14] or 0)
		fn_amount = round(float(agg[15] or 0.0), 2)
		tn_count = int(agg[16] or 0)
		tn_amount = round(float(agg[17] or 0.0), 2)
		unflagged_known_count = int(agg[18] or 0)

		full_ground_truth = self._has_full_ground_truth(gross_count, flagged_count, unflagged_known_count)
		ground_truth_coverage = "FULL" if full_ground_truth else "FLAGGED_ONLY"

		if full_ground_truth:
			missed_fraud_amount: Optional[float] = fn_amount
			missed_fraud_count: Optional[int] = fn_count
			total_fraud_amt = fraud_loss_prevented + fn_amount
			value_detection_rate: Optional[float] = (
				round(fraud_loss_prevented / total_fraud_amt, 4) if total_fraud_amt > 0 else None
			)
			net_fraud_loss_bps: Optional[float] = (
				round((fn_amount / gross_amount) * 10000.0, 2) if gross_amount > 0 else 0.0
			)
			legit_total = tn_count + fp_count
			customer_insult_rate: Optional[float] = (
				round(fp_count / legit_total, 6) if legit_total > 0 else None
			)
			legit_amt_total = tn_amount + fp_friction_volume
			volume_insult_rate: Optional[float] = (
				round(fp_friction_volume / legit_amt_total, 6) if legit_amt_total > 0 else None
			)
			hard_insult_rate: Optional[float] = round(hard_fp_count / legit_total, 6) if legit_total > 0 else None
			soft_insult_rate: Optional[float] = round(soft_fp_count / legit_total, 6) if legit_total > 0 else None
		else:
			missed_fraud_amount = None
			missed_fraud_count = None
			value_detection_rate = None
			net_fraud_loss_bps = None
			customer_insult_rate = None
			volume_insult_rate = None
			hard_insult_rate = None
			soft_insult_rate = None

		# Case operations metrics from self.cases
		total_cases = len(self.cases)
		open_cases = sum(1 for c in self.cases if c.status == CaseStatus.OPEN)
		in_progress_cases = sum(1 for c in self.cases if c.status == CaseStatus.IN_PROGRESS)
		pending_customer_cases = sum(1 for c in self.cases if c.status == CaseStatus.PENDING_CUSTOMER)
		resolved_fraud_list = [c for c in self.cases if c.status == CaseStatus.RESOLVED_FRAUD]
		resolved_legit_list = [c for c in self.cases if c.status == CaseStatus.RESOLVED_LEGITIMATE]
		resolved_fraud_cases = len(resolved_fraud_list)
		resolved_legit_cases = len(resolved_legit_list)
		resolved_cases = resolved_fraud_cases + resolved_legit_cases
		critical_high_backlog = sum(
			1 for c in self.cases
			if c.status in (CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.PENDING_CUSTOMER)
			and c.priority.value in ("CRITICAL", "HIGH")
		)
		dispatched_amount = round(sum(float(c.amount) for c in self.cases), 2)
		resolved_fraud_case_amt = round(sum(float(c.amount) for c in resolved_fraud_list), 2)
		resolved_legit_case_amt = round(sum(float(c.amount) for c in resolved_legit_list), 2)
		resolved_case_amt = round(resolved_fraud_case_amt + resolved_legit_case_amt, 2)
		pending_case_cnt = max(0, total_cases - resolved_cases)
		pending_case_amt = round(max(0.0, dispatched_amount - resolved_case_amt), 2)

		evaluated_alerts = tp_count + fp_count
		verified_precision = round(tp_count / evaluated_alerts, 4) if evaluated_alerts > 0 else None
		alert_to_fraud_ratio = round(evaluated_alerts / tp_count, 2) if tp_count > 0 else None
		case_resolution_rate = round(resolved_cases / total_cases, 4) if total_cases > 0 else 0.0
		case_sla = self._compute_case_sla()

		kpis = {
			"gross_scanned_volume": gross_amount,
			"gross_scanned_count": gross_count,
			"amount_at_risk": amount_at_risk,
			"flagged_tx_count": flagged_count,
			"flagged_rate": round(flagged_count / max(1, gross_count), 4) if gross_count > 0 else 0.0,
			"reject_count": reject_count,
			"review_count": review_count,
			"confirmed_fraud_loss_prevented": fraud_loss_prevented,
			"confirmed_fraud_count": tp_count,
			"missed_fraud_amount": missed_fraud_amount,
			"missed_fraud_count": missed_fraud_count,
			"value_detection_rate": value_detection_rate,
			"net_fraud_loss_bps": net_fraud_loss_bps,
			"false_positive_friction_volume": fp_friction_volume,
			"false_positive_count": fp_count,
			"hard_false_decline_amount": hard_fp_amount,
			"hard_false_decline_count": hard_fp_count,
			"soft_review_friction_amount": soft_fp_amount,
			"soft_review_friction_count": soft_fp_count,
			"customer_insult_rate": customer_insult_rate,
			"insult_rate": customer_insult_rate,
			"volume_insult_rate": volume_insult_rate,
			"hard_insult_rate": hard_insult_rate,
			"soft_insult_rate": soft_insult_rate,
			"verified_precision": verified_precision,
			"alert_to_fraud_ratio": alert_to_fraud_ratio,
			"alert_to_fraud_label": f"{alert_to_fraud_ratio:.1f} : 1" if alert_to_fraud_ratio is not None else "—",
			"case_resolution_rate": case_resolution_rate,
			"total_cases": total_cases,
			"resolved_cases": resolved_cases,
			"open_cases": open_cases,
			"in_progress_cases": in_progress_cases,
			"pending_customer_cases": pending_customer_cases,
			"critical_high_backlog": critical_high_backlog,
			"mttr_p50_hours": case_sla["mttr_p50_hours"],
			"mttr_p90_hours": case_sla["mttr_p90_hours"],
			"sla_breach_count": case_sla["sla_breach_count"],
			"sla_breach_rate": case_sla["sla_breach_rate"],
			"label_source": self.label_source,
			"ground_truth_coverage": ground_truth_coverage,
			"has_dataset_labels": self.has_dataset_labels,
		}

		# Strictly monotonic 4-stage funnel: Scanned >= Flagged >= Dispatched Cases >= Resolved Cases
		dispatched_count = min(flagged_count, total_cases) if flagged_count > 0 else total_cases
		resolved_funnel_count = min(dispatched_count, resolved_cases)
		funnel = [
			{
				"stage": "SCANNED",
				"label": "1. Tổng giao dịch quét",
				"tx_count": gross_count,
				"amount": gross_amount,
				"conversion_rate": 1.0 if gross_count > 0 else 0.0,
				"step_conversion_rate": 1.0 if gross_count > 0 else 0.0,
			},
			{
				"stage": "FLAGGED",
				"label": "2. Bị gắn cờ (REJECT / REVIEW)",
				"tx_count": flagged_count,
				"amount": amount_at_risk,
				"conversion_rate": round(flagged_count / max(1, gross_count), 4) if gross_count > 0 else 0.0,
				"step_conversion_rate": round(flagged_count / max(1, gross_count), 4) if gross_count > 0 else 0.0,
				"reject_count": reject_count,
				"review_count": review_count,
			},
			{
				"stage": "DISPATCHED",
				"label": "3. Chuyển hồ sơ điều tra",
				"tx_count": dispatched_count,
				"amount": dispatched_amount,
				"conversion_rate": round(dispatched_count / max(1, gross_count), 4) if gross_count > 0 else 0.0,
				"step_conversion_rate": round(dispatched_count / max(1, flagged_count), 4) if flagged_count > 0 else 0.0,
			},
			{
				"stage": "RESOLVED",
				"label": "4. Đã xử lý & kết luận",
				"tx_count": resolved_funnel_count,
				"amount": resolved_case_amt,
				"conversion_rate": round(resolved_funnel_count / max(1, gross_count), 4) if gross_count > 0 else 0.0,
				"step_conversion_rate": round(resolved_funnel_count / max(1, dispatched_count), 4) if dispatched_count > 0 else 0.0,
				"confirmed_fraud_count": resolved_fraud_cases,
				"confirmed_fraud_amount": resolved_fraud_case_amt,
				"false_positive_count": resolved_legit_cases,
				"false_positive_amount": resolved_legit_case_amt,
				"pending_count": pending_case_cnt,
				"pending_amount": pending_case_amt,
			},
		]

		financial_trends, trends_granularity = self._compute_financial_trends(full_ground_truth)

		status_order = [
			("OPEN", "Mới mở"),
			("IN_PROGRESS", "Đang điều tra"),
			("PENDING_CUSTOMER", "Chờ khách hàng"),
			("RESOLVED_FRAUD", "Xác nhận gian lận"),
			("RESOLVED_LEGITIMATE", "Hợp lệ / Báo giả"),
		]
		by_status = []
		for st_code, st_label in status_order:
			matching = [c for c in self.cases if c.status.value == st_code]
			by_status.append({
				"status": st_code,
				"label": st_label,
				"count": len(matching),
				"amount": round(sum(float(c.amount) for c in matching), 2),
			})

		priority_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
		by_priority = []
		for prio in priority_order:
			p_cases = [c for c in self.cases if c.priority.value == prio]
			by_priority.append({
				"priority": prio,
				"open_count": sum(1 for c in p_cases if c.status == CaseStatus.OPEN),
				"in_progress_count": sum(1 for c in p_cases if c.status in (CaseStatus.IN_PROGRESS, CaseStatus.PENDING_CUSTOMER)),
				"resolved_fraud_count": sum(1 for c in p_cases if c.status == CaseStatus.RESOLVED_FRAUD),
				"resolved_legitimate_count": sum(1 for c in p_cases if c.status == CaseStatus.RESOLVED_LEGITIMATE),
				"total_count": len(p_cases),
				"total_amount": round(sum(float(c.amount) for c in p_cases), 2),
			})

		return {
			"kpis": kpis,
			"funnel": funnel,
			"financial_trends": financial_trends,
			"financial_trends_granularity": trends_granularity,
			"case_sla": case_sla,
			"queue_breakdown": {
				"by_status": by_status,
				"by_priority": by_priority,
			},
		}

	def _compute_calibration_and_health(self) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
		"""Computes equal-width & equal-count calibration curves, Brier score, ECE, and KS statistic."""
		bins = np.linspace(0.0, 1.0, 11)
		equal_width: list[dict[str, Any]] = []
		total_verified_for_ece = 0
		ece_accum = 0.0

		for i in range(10):
			low = round(float(bins[i]), 2)
			high = round(float(bins[i + 1]), 2)
			op = "<=" if i == 9 else "<"
			b_row = self.conn.execute(f"""
				SELECT
					COUNT(*) AS total_count,
					COALESCE(SUM(CASE WHEN effective_label IN (0, 1) THEN 1 ELSE 0 END), 0) AS verified_count,
					COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS fraud_count,
					COALESCE(SUM(CASE WHEN effective_label = 0 THEN 1 ELSE 0 END), 0) AS legit_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS fp_count,
					COALESCE(SUM(CASE WHEN effective_label = -1 THEN 1 ELSE 0 END), 0) AS unverified_count,
					COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fraud_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS fp_amount,
					AVG(CASE WHEN effective_label IN (0, 1) THEN model_score ELSE NULL END) AS mean_pred_verified,
					AVG(model_score) AS mean_pred_all
				FROM v_transactions
				WHERE model_score >= ? AND model_score {op} ?
			""", [low, high]).fetchone()

			tot_c = int(b_row[0] or 0)
			ver_c = int(b_row[1] or 0)
			frd_c = int(b_row[2] or 0)
			leg_c = int(b_row[3] or 0)
			fp_c = int(b_row[4] or 0)
			unv_c = int(b_row[5] or 0)
			mean_pred = b_row[8] if b_row[8] is not None else b_row[9]
			mean_pred_val = round(float(mean_pred), 4) if mean_pred is not None else round((low + high) / 2.0, 4)
			obs_rate = round(frd_c / ver_c, 4) if ver_c > 0 else None
			if ver_c > 0 and obs_rate is not None:
				total_verified_for_ece += ver_c
				ece_accum += ver_c * abs(obs_rate - mean_pred_val)

			equal_width.append({
				"bin": f"{low:.1f}-{high:.1f}",
				"lower": low,
				"upper": high,
				"total_count": tot_c,
				"verified_count": ver_c,
				"confirmed_fraud_count": frd_c,
				"legit_count": leg_c,
				"false_positive_count": fp_c,
				"unverified_count": unv_c,
				"fraud_amount": round(float(b_row[6] or 0.0), 2),
				"false_positive_amount": round(float(b_row[7] or 0.0), 2),
				"mean_predicted_score": mean_pred_val,
				"observed_fraud_rate": obs_rate,
			})

		ece = round(ece_accum / total_verified_for_ece, 4) if total_verified_for_ece > 0 else None

		# Equal-count (decile) calibration via NTILE(10)
		ec_rows = self.conn.execute("""
			WITH ranked AS (
				SELECT
					NTILE(10) OVER (ORDER BY model_score ASC, event_id ASC) AS bucket_id,
					model_score, effective_label, is_flagged, amount
				FROM v_transactions
			)
			SELECT
				bucket_id,
				MIN(model_score) AS low_s,
				MAX(model_score) AS high_s,
				COUNT(*) AS total_count,
				COALESCE(SUM(CASE WHEN effective_label IN (0, 1) THEN 1 ELSE 0 END), 0) AS verified_count,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS fraud_count,
				COALESCE(SUM(CASE WHEN effective_label = 0 THEN 1 ELSE 0 END), 0) AS legit_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS fp_count,
				COALESCE(SUM(CASE WHEN effective_label = -1 THEN 1 ELSE 0 END), 0) AS unverified_count,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fraud_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS fp_amount,
				AVG(CASE WHEN effective_label IN (0, 1) THEN model_score ELSE NULL END) AS mean_pred_verified,
				AVG(model_score) AS mean_pred_all
			FROM ranked
			GROUP BY bucket_id
			ORDER BY bucket_id ASC
		""").fetchall()
		equal_count: list[dict[str, Any]] = []
		for r in ec_rows:
			low_s = round(float(r[1] or 0.0), 3)
			high_s = round(float(r[2] or 0.0), 3)
			ver_c = int(r[4] or 0)
			frd_c = int(r[5] or 0)
			mean_pred = r[11] if r[11] is not None else r[12]
			equal_count.append({
				"bin": f"D{int(r[0])} ({low_s:.2f}–{high_s:.2f})",
				"lower": low_s,
				"upper": high_s,
				"total_count": int(r[3] or 0),
				"verified_count": ver_c,
				"confirmed_fraud_count": frd_c,
				"legit_count": int(r[6] or 0),
				"false_positive_count": int(r[7] or 0),
				"unverified_count": int(r[8] or 0),
				"fraud_amount": round(float(r[9] or 0.0), 2),
				"false_positive_amount": round(float(r[10] or 0.0), 2),
				"mean_predicted_score": round(float(mean_pred or 0.0), 4),
				"observed_fraud_rate": round(frd_c / ver_c, 4) if ver_c > 0 else None,
			})

		brier_row = self.conn.execute("""
			SELECT AVG(POWER(model_score - effective_label, 2)), COUNT(*)
			FROM v_transactions
			WHERE effective_label IN (0, 1)
		""").fetchone()
		brier_score = round(float(brier_row[0]), 4) if brier_row and brier_row[0] is not None else None
		evaluated_count = int(brier_row[1] or 0) if brier_row else 0

		ks_row = self.conn.execute("""
			WITH per_score AS (
				SELECT
					model_score,
					SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END) AS pos_cnt,
					SUM(CASE WHEN effective_label = 0 THEN 1 ELSE 0 END) AS neg_cnt
				FROM v_transactions
				WHERE effective_label IN (0, 1)
				GROUP BY model_score
			),
			totals AS (
				SELECT SUM(pos_cnt) AS n_pos, SUM(neg_cnt) AS n_neg FROM per_score
			),
			cdfs AS (
				SELECT
					SUM(pos_cnt) OVER (ORDER BY model_score ASC ROWS UNBOUNDED PRECEDING) AS cum_pos,
					SUM(neg_cnt) OVER (ORDER BY model_score ASC ROWS UNBOUNDED PRECEDING) AS cum_neg
				FROM per_score
			)
			SELECT MAX(ABS(CAST(c.cum_pos AS DOUBLE) / t.n_pos - CAST(c.cum_neg AS DOUBLE) / t.n_neg))
			FROM cdfs c CROSS JOIN totals t
			WHERE t.n_pos > 0 AND t.n_neg > 0
		""").fetchone()
		ks_stat = round(float(ks_row[0]), 4) if ks_row and ks_row[0] is not None else None

		return equal_width, {"equal_width": equal_width, "equal_count": equal_count}, {
			"brier_score": brier_score,
			"ece": ece,
			"ks_statistic": ks_stat,
			"evaluated_count": evaluated_count,
		}

	def _compute_lift_gain_curve(self) -> list[dict[str, Any]]:
		"""Computes Top-K Cumulative Gain & Lift curve across standard population percentiles."""
		totals = self.conn.execute("""
			SELECT
				COUNT(*) AS total_tx,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS total_fraud_cnt,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS total_fraud_amt
			FROM v_transactions
		""").fetchone()
		total_tx = int(totals[0] or 0)
		total_fraud_cnt = int(totals[1] or 0)
		total_fraud_amt = float(totals[2] or 0.0)
		if total_tx == 0:
			return []

		ranked_rows = self.conn.execute("""
			SELECT
				ROW_NUMBER() OVER (ORDER BY model_score DESC, event_id ASC) AS rn,
				effective_label,
				amount
			FROM v_transactions
		""").fetchall()

		milestones = [(pct, min(total_tx, max(1, math.ceil(total_tx * pct / 100.0)))) for pct in TOP_K_MILESTONES]
		curve: list[dict[str, Any]] = []
		cum_tp = 0
		cum_fp = 0
		cum_tp_amt = 0.0
		m_idx = 0

		for rn, eff_lbl, amt in ranked_rows:
			if int(eff_lbl) == 1:
				cum_tp += 1
				cum_tp_amt += float(amt or 0.0)
			elif int(eff_lbl) == 0:
				cum_fp += 1
			while m_idx < len(milestones) and int(rn) == milestones[m_idx][1]:
				pct, k_cnt = milestones[m_idx]
				gain_cnt = round(cum_tp / total_fraud_cnt, 4) if total_fraud_cnt > 0 else 0.0
				gain_amt = round(cum_tp_amt / total_fraud_amt, 4) if total_fraud_amt > 0 else 0.0
				pop_share = k_cnt / total_tx
				lift_val = round(gain_cnt / pop_share, 2) if (total_fraud_cnt > 0 and pop_share > 0) else 0.0
				eval_cnt = cum_tp + cum_fp
				curve.append({
					"top_pct": pct,
					"label": f"Top {pct}%",
					"tx_count": k_cnt,
					"fraud_count_caught": cum_tp,
					"fraud_amount_caught": round(cum_tp_amt, 2),
					"gain_count_pct": gain_cnt,
					"gain_amount_pct": gain_amt,
					"lift": lift_val,
					"precision": round(cum_tp / eval_cnt, 4) if eval_cnt > 0 else None,
				})
				m_idx += 1
		return curve

	def _compute_score_drift_psi(self) -> dict[str, Any]:
		"""Computes 10-bin Population Stability Index (PSI) between chronological first half and second half."""
		total_tx = int(self.conn.execute("SELECT COUNT(*) FROM v_transactions").fetchone()[0] or 0)
		base_target = total_tx // 2
		cur_target = total_tx - base_target
		if total_tx < 20 or base_target < 10 or cur_target < 10:
			return {
				"psi": None,
				"status": "INSUFFICIENT_DATA",
				"baseline_count": base_target,
				"current_count": cur_target,
				"bins": [],
			}

		bin_rows = self.conn.execute(f"""
			WITH ordered AS (
				SELECT
					model_score,
					ROW_NUMBER() OVER (
						ORDER BY COALESCE(tx_timestamp, TRY_CAST(job_created_at AS TIMESTAMP)) ASC, event_id ASC
					) AS rn
				FROM v_transactions
			),
			split AS (
				SELECT
					CASE WHEN rn <= {base_target} THEN 'BASE' ELSE 'CUR' END AS period,
					LEAST(9, GREATEST(0, CAST(FLOOR(model_score * 10.0) AS INTEGER))) AS bin_idx
				FROM ordered
			)
			SELECT
				bin_idx,
				COALESCE(SUM(CASE WHEN period = 'BASE' THEN 1 ELSE 0 END), 0) AS base_cnt,
				COALESCE(SUM(CASE WHEN period = 'CUR' THEN 1 ELSE 0 END), 0) AS cur_cnt
			FROM split
			GROUP BY bin_idx
			ORDER BY bin_idx ASC
		""").fetchall()
		by_idx = {int(r[0]): (int(r[1] or 0), int(r[2] or 0)) for r in bin_rows}

		share_floor = 0.0001
		total_psi = 0.0
		bins_out: list[dict[str, Any]] = []
		for idx in range(10):
			b_cnt, c_cnt = by_idx.get(idx, (0, 0))
			p_base = max(b_cnt / base_target, share_floor)
			p_cur = max(c_cnt / cur_target, share_floor)
			contrib = (p_cur - p_base) * math.log(p_cur / p_base)
			total_psi += contrib
			low = idx / 10.0
			high = (idx + 1) / 10.0
			bins_out.append({
				"bin": f"{low:.1f}-{high:.1f}",
				"baseline_count": b_cnt,
				"current_count": c_cnt,
				"baseline_pct": round(b_cnt / base_target, 4),
				"current_pct": round(c_cnt / cur_target, 4),
				"psi_contribution": round(contrib, 5),
			})

		psi_val = round(total_psi, 4)
		status = (
			"STABLE" if psi_val < 0.10
			else "MODERATE_SHIFT" if psi_val <= 0.25
			else "SIGNIFICANT_SHIFT"
		)
		return {
			"psi": psi_val,
			"status": status,
			"baseline_count": base_target,
			"current_count": cur_target,
			"bins": bins_out,
		}

	@staticmethod
	def evaluate_dual_threshold_pair(
		curve: list[dict[str, Any]],
		mode: str,
		tau_review: float,
		tau_reject: float,
		total_known_fraud_amt: float,
		review_cost: float = 5.0,
		false_decline_cost_ratio: float = 0.15,
	) -> dict[str, Any]:
		"""Evaluates a (tau_review <= tau_reject) pair for either 'hybrid' or 'model_only' from the precomputed curve."""
		eff_reject = max(tau_review, tau_reject)
		pt_rev = min(curve, key=lambda p: abs(p["threshold"] - tau_review))
		pt_rej = min(curve, key=lambda p: abs(p["threshold"] - eff_reject))
		rev_data = pt_rev[mode]
		rej_data = pt_rej[mode]

		caught_cnt = rev_data["flagged_tp_count"]
		caught_amt = rev_data["flagged_tp_amount"]
		review_cnt = max(0, rev_data["flagged_count"] - rej_data["reject_count"])
		reject_cnt = rej_data["reject_count"]
		hard_fp_cnt = rej_data["reject_fp_count"]
		hard_fp_amt = rej_data["reject_fp_amount"]
		soft_fp_cnt = max(0, rev_data["flagged_fp_count"] - hard_fp_cnt)
		total_eval = caught_cnt + rev_data["flagged_fp_count"]
		vdr = round(caught_amt / total_known_fraud_amt, 4) if total_known_fraud_amt > 0 else 0.0
		precision = round(caught_cnt / total_eval, 4) if total_eval > 0 else 0.0
		net_savings = round(
			caught_amt - (review_cnt * review_cost) - (hard_fp_amt * false_decline_cost_ratio),
			2,
		)
		return {
			"tau_review": pt_rev["threshold"],
			"tau_reject": pt_rej["threshold"],
			"caught_fraud_count": caught_cnt,
			"caught_fraud_amount": round(caught_amt, 2),
			"vdr": vdr,
			"precision": precision,
			"review_queue_count": review_cnt,
			"reject_count": reject_cnt,
			"hard_false_decline_count": hard_fp_cnt,
			"hard_false_decline_amount": round(hard_fp_amt, 2),
			"soft_review_fp_count": soft_fp_cnt,
			"net_savings": net_savings,
		}

	def _compute_dual_threshold_simulator(self) -> dict[str, Any]:
		"""Computes 19-point curves and optimization recommendations for both Hybrid and Model-only dual thresholds."""
		totals_row = self.conn.execute("""
			SELECT
				COUNT(*) AS gross_count,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS total_fraud,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS total_fraud_amt,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS baseline_fp
			FROM v_transactions
		""").fetchone()
		gross_count = int(totals_row[0] or 0)
		total_known_fraud = int(totals_row[1] or 0)
		total_known_fraud_amt = round(float(totals_row[2] or 0.0), 2)
		baseline_fp = int(totals_row[3] or 0)

		curve: list[dict[str, Any]] = []
		for step_int in range(5, 100, 5):
			thresh = round(step_int / 100.0, 2)
			sim_row = self.conn.execute("""
				SELECT
					-- Model-only flagged (score >= t)
					COALESCE(SUM(CASE WHEN model_score >= ? THEN 1 ELSE 0 END), 0) AS mo_flg_cnt,
					COALESCE(SUM(CASE WHEN model_score >= ? AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS mo_flg_tp,
					COALESCE(SUM(CASE WHEN model_score >= ? AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS mo_flg_tp_amt,
					COALESCE(SUM(CASE WHEN model_score >= ? AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS mo_flg_fp,
					COALESCE(SUM(CASE WHEN model_score >= ? AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS mo_flg_fp_amt,
					-- Hybrid flagged (score >= t OR rule hit)
					COALESCE(SUM(CASE WHEN model_score >= ? OR has_rule_hit = 1 OR rule_action IN ('REVIEW', 'REJECT') THEN 1 ELSE 0 END), 0) AS hy_flg_cnt,
					COALESCE(SUM(CASE WHEN (model_score >= ? OR has_rule_hit = 1 OR rule_action IN ('REVIEW', 'REJECT')) AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS hy_flg_tp,
					COALESCE(SUM(CASE WHEN (model_score >= ? OR has_rule_hit = 1 OR rule_action IN ('REVIEW', 'REJECT')) AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS hy_flg_tp_amt,
					COALESCE(SUM(CASE WHEN (model_score >= ? OR has_rule_hit = 1 OR rule_action IN ('REVIEW', 'REJECT')) AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS hy_flg_fp,
					COALESCE(SUM(CASE WHEN (model_score >= ? OR has_rule_hit = 1 OR rule_action IN ('REVIEW', 'REJECT')) AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS hy_flg_fp_amt,
					-- Hybrid reject (score >= t OR rule_action = 'REJECT')
					COALESCE(SUM(CASE WHEN model_score >= ? OR rule_action = 'REJECT' THEN 1 ELSE 0 END), 0) AS hy_rej_cnt,
					COALESCE(SUM(CASE WHEN (model_score >= ? OR rule_action = 'REJECT') AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS hy_rej_tp,
					COALESCE(SUM(CASE WHEN (model_score >= ? OR rule_action = 'REJECT') AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS hy_rej_tp_amt,
					COALESCE(SUM(CASE WHEN (model_score >= ? OR rule_action = 'REJECT') AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS hy_rej_fp,
					COALESCE(SUM(CASE WHEN (model_score >= ? OR rule_action = 'REJECT') AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS hy_rej_fp_amt
				FROM v_transactions
			""", [thresh] * 15).fetchone()

			mo_cnt = int(sim_row[0] or 0)
			mo_tp = int(sim_row[1] or 0)
			mo_tp_amt = round(float(sim_row[2] or 0.0), 2)
			mo_fp = int(sim_row[3] or 0)
			mo_fp_amt = round(float(sim_row[4] or 0.0), 2)
			mo_eval = mo_tp + mo_fp

			hy_cnt = int(sim_row[5] or 0)
			hy_tp = int(sim_row[6] or 0)
			hy_tp_amt = round(float(sim_row[7] or 0.0), 2)
			hy_fp = int(sim_row[8] or 0)
			hy_fp_amt = round(float(sim_row[9] or 0.0), 2)

			hy_rej_cnt = int(sim_row[10] or 0)
			hy_rej_tp = int(sim_row[11] or 0)
			hy_rej_tp_amt = round(float(sim_row[12] or 0.0), 2)
			hy_rej_fp = int(sim_row[13] or 0)
			hy_rej_fp_amt = round(float(sim_row[14] or 0.0), 2)

			curve.append({
				"threshold": thresh,
				"review_queue_volume": mo_cnt,
				"hybrid_queue_volume": hy_cnt,
				"caught_fraud_count": mo_tp,
				"caught_fraud_amount": mo_tp_amt,
				"false_positive_count": mo_fp,
				"false_positive_amount": mo_fp_amt,
				"estimated_recall": round(mo_tp / max(1, total_known_fraud), 4) if total_known_fraud > 0 else 0.0,
				"estimated_precision": round(mo_tp / max(1, mo_eval), 4) if mo_eval > 0 else 0.0,
				"fp_reduction_pct": round((baseline_fp - mo_fp) / max(1, baseline_fp), 4) if baseline_fp > 0 else 0.0,
				"model_only": {
					"flagged_count": mo_cnt,
					"flagged_tp_count": mo_tp,
					"flagged_tp_amount": mo_tp_amt,
					"flagged_fp_count": mo_fp,
					"flagged_fp_amount": mo_fp_amt,
					"reject_count": mo_cnt,
					"reject_tp_count": mo_tp,
					"reject_tp_amount": mo_tp_amt,
					"reject_fp_count": mo_fp,
					"reject_fp_amount": mo_fp_amt,
				},
				"hybrid": {
					"flagged_count": hy_cnt,
					"flagged_tp_count": hy_tp,
					"flagged_tp_amount": hy_tp_amt,
					"flagged_fp_count": hy_fp,
					"flagged_fp_amount": hy_fp_amt,
					"reject_count": hy_rej_cnt,
					"reject_tp_count": hy_rej_tp,
					"reject_tp_amount": hy_rej_tp_amt,
					"reject_fp_count": hy_rej_fp,
					"reject_fp_amount": hy_rej_fp_amt,
				},
			})

		recommendations: dict[str, dict[str, Any]] = {}
		capacity_cap = max(1, math.ceil(gross_count * 0.10)) if gross_count > 0 else 0
		for mode in ("hybrid", "model_only"):
			all_pairs = [
				self.evaluate_dual_threshold_pair(curve, mode, curve[i]["threshold"], curve[j]["threshold"], total_known_fraud_amt)
				for i in range(len(curve))
				for j in range(i, len(curve))
			]
			best_savings = max(all_pairs, key=lambda x: (x["net_savings"], x["caught_fraud_amount"], -x["review_queue_count"]))
			cap_candidates = [p for p in all_pairs if p["review_queue_count"] <= capacity_cap] or all_pairs
			best_capacity = max(cap_candidates, key=lambda x: (x["caught_fraud_amount"], x["net_savings"]))
			prec_candidates = [p for p in all_pairs if p["precision"] >= 0.50] or all_pairs
			best_precision = max(prec_candidates, key=lambda x: (x["caught_fraud_amount"], x["precision"]))
			recommendations[mode] = {
				"max_net_savings": best_savings,
				"capacity_top_k": best_capacity,
				"target_precision": best_precision,
			}

		return {
			"total_known_fraud_count": total_known_fraud,
			"total_known_fraud_amount": total_known_fraud_amt,
			"baseline_fp_count": baseline_fp,
			"default_review_cost": 5.0,
			"default_false_decline_cost_ratio": 0.15,
			"curve": curve,
			"recommendations": recommendations,
		}

	def _compute_model_comparison(self, full_ground_truth: bool) -> list[dict[str, Any]]:
		"""Summarizes per-model_version effectiveness metrics with resolved model labels."""
		rows = self.conn.execute("""
			SELECT
				NULLIF(TRIM(model_version_id), '') AS mv_id,
				COUNT(*) AS tx_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS tp_cnt,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS fp_cnt,
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS fn_cnt,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS tp_amt,
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fn_amt,
				AVG(CASE WHEN effective_label IN (0, 1) THEN POWER(model_score - effective_label, 2) ELSE NULL END) AS brier
			FROM v_transactions
			GROUP BY mv_id
			ORDER BY tx_count DESC
		""").fetchall()

		out: list[dict[str, Any]] = []
		for mv_id, tx_cnt, flg_cnt, tp_cnt, fp_cnt, fn_cnt, tp_amt, fn_amt, brier in rows:
			if mv_id is None and len(rows) > 1:
				continue
			mv_key = str(mv_id) if mv_id else ""
			if not mv_key:
				continue
			meta = self.model_labels.get(mv_key, {})
			tp_i = int(tp_cnt or 0)
			fp_i = int(fp_cnt or 0)
			eval_i = tp_i + fp_i
			tot_f_amt = float(tp_amt or 0.0) + float(fn_amt or 0.0)
			ks_row = self.conn.execute("""
				WITH per_score AS (
					SELECT model_score,
						SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END) AS pos_cnt,
						SUM(CASE WHEN effective_label = 0 THEN 1 ELSE 0 END) AS neg_cnt
					FROM v_transactions
					WHERE model_version_id = ? AND effective_label IN (0, 1)
					GROUP BY model_score
				),
				totals AS (SELECT SUM(pos_cnt) AS n_pos, SUM(neg_cnt) AS n_neg FROM per_score),
				cdfs AS (
					SELECT
						SUM(pos_cnt) OVER (ORDER BY model_score ASC ROWS UNBOUNDED PRECEDING) AS cum_pos,
						SUM(neg_cnt) OVER (ORDER BY model_score ASC ROWS UNBOUNDED PRECEDING) AS cum_neg
					FROM per_score
				)
				SELECT MAX(ABS(CAST(c.cum_pos AS DOUBLE) / t.n_pos - CAST(c.cum_neg AS DOUBLE) / t.n_neg))
				FROM cdfs c CROSS JOIN totals t
				WHERE t.n_pos > 0 AND t.n_neg > 0
			""", [mv_key]).fetchone()
			out.append({
				"model_version_id": mv_key,
				"model_name": meta.get("model_name") or f"Model-{mv_key[:8]}",
				"semver": meta.get("semver") or "",
				"display_label": meta.get("display_label") or f"Model-{mv_key[:8]}",
				"tx_count": int(tx_cnt or 0),
				"flagged_count": int(flg_cnt or 0),
				"verified_tp": tp_i,
				"verified_fp": fp_i,
				"verified_fn": int(fn_cnt or 0) if full_ground_truth else None,
				"verified_precision": round(tp_i / eval_i, 4) if eval_i > 0 else None,
				"vdr": round(float(tp_amt or 0.0) / tot_f_amt, 4) if (full_ground_truth and tot_f_amt > 0) else None,
				"brier_score": round(float(brier), 4) if brier is not None else None,
				"ks_statistic": round(float(ks_row[0]), 4) if (ks_row and ks_row[0] is not None) else None,
			})
		return out

	def compute_effectiveness_analysis(self) -> dict[str, Any]:
		"""Computes SUC-23: AI vs Rule Attribution, Rule Leaderboard with Unique Catch & FP/FN samples, Calibration, Lift/KS, PSI & Dual-Threshold Simulator."""
		attr_row = self.conn.execute("""
			SELECT
				COUNT(*) AS total_caught,
				COALESCE(SUM(amount), 0.0) AS total_caught_amount,
				COALESCE(SUM(CASE WHEN has_ai_hit = 1 AND has_rule_hit = 0 THEN 1 ELSE 0 END), 0) AS ai_only_count,
				COALESCE(SUM(CASE WHEN has_ai_hit = 1 AND has_rule_hit = 0 THEN amount ELSE 0.0 END), 0.0) AS ai_only_amount,
				COALESCE(SUM(CASE WHEN has_rule_hit = 1 AND has_ai_hit = 0 THEN 1 ELSE 0 END), 0) AS rule_only_count,
				COALESCE(SUM(CASE WHEN has_rule_hit = 1 AND has_ai_hit = 0 THEN amount ELSE 0.0 END), 0.0) AS rule_only_amount,
				COALESCE(SUM(CASE WHEN has_ai_hit = 1 AND has_rule_hit = 1 THEN 1 ELSE 0 END), 0) AS overlap_count,
				COALESCE(SUM(CASE WHEN has_ai_hit = 1 AND has_rule_hit = 1 THEN amount ELSE 0.0 END), 0.0) AS overlap_amount
			FROM v_transactions
			WHERE is_flagged = 1 AND effective_label = 1
		""").fetchone()

		total_caught = int(attr_row[0] or 0)
		total_caught_amt = round(float(attr_row[1] or 0.0), 2)
		ai_only_cnt = int(attr_row[2] or 0)
		ai_only_amt = round(float(attr_row[3] or 0.0), 2)
		rule_only_cnt = int(attr_row[4] or 0)
		rule_only_amt = round(float(attr_row[5] or 0.0), 2)
		overlap_cnt = int(attr_row[6] or 0)
		overlap_amt = round(float(attr_row[7] or 0.0), 2)

		attribution = {
			"total_caught_fraud_count": total_caught,
			"total_caught_fraud_amount": total_caught_amt,
			"ai_exclusive_catch_rate": round(ai_only_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
			"rule_exclusive_catch_rate": round(rule_only_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
			"consensus_overlap_rate": round(overlap_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
			"segments": [
				{
					"segment": "AI_EXCLUSIVE",
					"label": "Chỉ mô hình AI bắt",
					"fraud_count": ai_only_cnt,
					"count_pct": round(ai_only_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
					"fraud_amount": ai_only_amt,
					"amount_pct": round(ai_only_amt / max(1.0, total_caught_amt), 4) if total_caught_amt > 0 else 0.0,
				},
				{
					"segment": "CONSENSUS_OVERLAP",
					"label": "Đồng thuận kết hợp (AI + Luật)",
					"fraud_count": overlap_cnt,
					"count_pct": round(overlap_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
					"fraud_amount": overlap_amt,
					"amount_pct": round(overlap_amt / max(1.0, total_caught_amt), 4) if total_caught_amt > 0 else 0.0,
				},
				{
					"segment": "RULE_EXCLUSIVE",
					"label": "Chỉ luật nghiệp vụ bắt",
					"fraud_count": rule_only_cnt,
					"count_pct": round(rule_only_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
					"fraud_amount": rule_only_amt,
					"amount_pct": round(rule_only_amt / max(1.0, total_caught_amt), 4) if total_caught_amt > 0 else 0.0,
				},
			],
		}

		counts_row = self.conn.execute("""
			SELECT
				COUNT(*),
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0),
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label IN (0, 1) THEN 1 ELSE 0 END), 0)
			FROM v_transactions
		""").fetchone()
		gross_count = int(counts_row[0] or 0)
		flagged_count = int(counts_row[1] or 0)
		unflagged_known_count = int(counts_row[2] or 0)
		full_ground_truth = self._has_full_ground_truth(gross_count, flagged_count, unflagged_known_count)

		rule_catalog: dict[str, dict[str, Any]] = {}
		for rule, ver in self.rules:
			status_str = rule.status.value if hasattr(rule.status, "value") else str(rule.status)
			act_str = ver.action.value if (ver and hasattr(ver.action, "value")) else (str(ver.action) if ver else "REVIEW")
			rule_catalog[rule.rule_code] = {
				"rule_id": str(rule.rule_id),
				"rule_code": rule.rule_code,
				"rule_name": rule.name,
				"status": status_str,
				"action": act_str,
				"version_number": ver.version_number if ver else 1,
				"total_hits": 0,
				"verified_cases": 0,
				"verified_tp": 0,
				"verified_fp": 0,
				"pending_cases": 0,
				"fraud_value_caught": 0.0,
				"false_positive_value": 0.0,
				"unique_catch_count": 0,
				"unique_catch_amount": 0.0,
			}

		for case in self.cases:
			for r_snap in case.triggered_rules:
				r_code = str(r_snap.get("rule_code") or "")
				if r_code and r_code not in rule_catalog:
					rule_catalog[r_code] = {
						"rule_id": str(r_snap.get("rule_id") or ""),
						"rule_code": r_code,
						"rule_name": str(r_snap.get("rule_name") or r_code),
						"status": "ACTIVE",
						"action": str(r_snap.get("action") or "REVIEW"),
						"version_number": int(r_snap.get("version_number") or 1),
						"total_hits": 0,
						"verified_cases": 0,
						"verified_tp": 0,
						"verified_fp": 0,
						"pending_cases": 0,
						"fraud_value_caught": 0.0,
						"false_positive_value": 0.0,
						"unique_catch_count": 0,
						"unique_catch_amount": 0.0,
					}

		hit_rows = self.conn.execute("""
			SELECT
				code,
				COUNT(*) AS hits,
				SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END) AS tp,
				SUM(CASE WHEN effective_label = 0 THEN 1 ELSE 0 END) AS fp,
				SUM(CASE WHEN effective_label NOT IN (0, 1) THEN 1 ELSE 0 END) AS pending,
				SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END) AS tp_amount,
				SUM(CASE WHEN effective_label = 0 THEN amount ELSE 0.0 END) AS fp_amount,
				ANY_VALUE(rule_action) AS rule_action
			FROM (
				SELECT unnest(from_json(rule_codes_json, '["VARCHAR"]')) AS code, amount, effective_label, rule_action
				FROM v_transactions
			)
			GROUP BY code
		""").fetchall()
		for code, hits, tp, fp, pending, tp_amount, fp_amount, rule_action in hit_rows:
			entry = rule_catalog.setdefault(code, {
				"rule_id": "",
				"rule_code": code,
				"rule_name": code,
				"status": "ACTIVE",
				"action": str(rule_action or "REVIEW"),
				"version_number": 1,
				"total_hits": 0,
				"verified_cases": 0,
				"verified_tp": 0,
				"verified_fp": 0,
				"pending_cases": 0,
				"fraud_value_caught": 0.0,
				"false_positive_value": 0.0,
				"unique_catch_count": 0,
				"unique_catch_amount": 0.0,
			})
			entry["total_hits"] += int(hits)
			entry["verified_cases"] += int(tp) + int(fp)
			entry["verified_tp"] += int(tp)
			entry["verified_fp"] += int(fp)
			entry["pending_cases"] += int(pending)
			entry["fraud_value_caught"] = round(entry["fraud_value_caught"] + float(tp_amount or 0.0), 2)
			entry["false_positive_value"] = round(entry["false_positive_value"] + float(fp_amount or 0.0), 2)

		uniq_rows = self.conn.execute("""
			SELECT
				list_extract(from_json(rule_codes_json, '["VARCHAR"]'), 1) AS code,
				COUNT(*) AS uniq_cnt,
				COALESCE(SUM(amount), 0.0) AS uniq_amt
			FROM v_transactions
			WHERE is_flagged = 1
			  AND effective_label = 1
			  AND has_ai_hit = 0
			  AND len(from_json(rule_codes_json, '["VARCHAR"]')) = 1
			GROUP BY code
		""").fetchall()
		for code, u_cnt, u_amt in uniq_rows:
			if code in rule_catalog:
				rule_catalog[code]["unique_catch_count"] = int(u_cnt or 0)
				rule_catalog[code]["unique_catch_amount"] = round(float(u_amt or 0.0), 2)

		fp_sample_rows = self.conn.execute("""
			SELECT code, event_id, user_id, amount, model_score, final_action, CAST(tx_timestamp AS VARCHAR), case_id
			FROM (
				SELECT unnest(from_json(rule_codes_json, '["VARCHAR"]')) AS code,
					event_id, user_id, amount, model_score, final_action, tx_timestamp, case_id
				FROM v_transactions
				WHERE is_flagged = 1 AND effective_label = 0
			)
			QUALIFY row_number() OVER (PARTITION BY code ORDER BY amount DESC, event_id ASC) <= 5
		""").fetchall()
		fp_samples_by_code: dict[str, list[dict[str, Any]]] = {}
		for code, ev_id, u_id, amt, m_score, f_act, tx_ts, c_id in fp_sample_rows:
			fp_samples_by_code.setdefault(str(code), []).append({
				"event_id": str(ev_id),
				"user_id": str(u_id),
				"amount": round(float(amt or 0.0), 2),
				"model_score": round(float(m_score or 0.0), 4),
				"final_action": str(f_act),
				"tx_timestamp": str(tx_ts) if tx_ts else None,
				"case_id": str(c_id) if c_id else None,
			})

		leaderboard: list[dict[str, Any]] = []
		for entry in rule_catalog.values():
			ver_cnt = entry["verified_cases"]
			tp = entry["verified_tp"]
			fp = entry["verified_fp"]
			prec = round(tp / ver_cnt, 4) if ver_cnt > 0 else None
			far = round(fp / ver_cnt, 4) if ver_cnt > 0 else None
			if ver_cnt == 0:
				health_tag = "UNVERIFIED"
			elif far is not None and far >= 0.70:
				health_tag = "NOISY"
			elif prec is not None and prec >= 0.70:
				health_tag = "HIGH_VALUE"
			else:
				health_tag = "BALANCED"

			leaderboard.append({
				**entry,
				"hit_rate": round(entry["total_hits"] / max(1, gross_count), 4) if gross_count > 0 else 0.0,
				"verified_precision": prec,
				"false_alert_rate": far,
				"verified_fpr": far,  # Backward-compatible alias for False Alert Rate
				"is_small_sample": ver_cnt < 30,
				"fp_samples": fp_samples_by_code.get(entry["rule_code"], []),
				"policy_health_tag": health_tag,
			})

		leaderboard.sort(
			key=lambda x: (-x["fraud_value_caught"], -x["total_hits"], x["rule_code"])
		)

		fn_samples: list[dict[str, Any]] = []
		if full_ground_truth:
			fn_rows = self.conn.execute("""
				SELECT event_id, user_id, amount, model_score, final_action, CAST(tx_timestamp AS VARCHAR), case_id
				FROM v_transactions
				WHERE is_flagged = 0 AND effective_label = 1
				ORDER BY amount DESC, event_id ASC
				LIMIT 5
			""").fetchall()
			fn_samples = [
				{
					"event_id": str(ev_id),
					"user_id": str(u_id),
					"amount": round(float(amt or 0.0), 2),
					"model_score": round(float(m_score or 0.0), 4),
					"final_action": str(f_act),
					"tx_timestamp": str(tx_ts) if tx_ts else None,
					"case_id": str(c_id) if c_id else None,
				}
				for ev_id, u_id, amt, m_score, f_act, tx_ts, c_id in fn_rows
			]

		score_calibration, calibration_modes, health_metrics = self._compute_calibration_and_health()
		lift_gain_curve = self._compute_lift_gain_curve()
		score_drift = self._compute_score_drift_psi()
		model_health = {
			**health_metrics,
			"psi": score_drift["psi"],
			"psi_status": score_drift["status"],
		}
		threshold_simulator = self._compute_dual_threshold_simulator()
		model_comparison = self._compute_model_comparison(full_ground_truth)

		return {
			"attribution": attribution,
			"rule_leaderboard": leaderboard,
			"fn_samples": fn_samples,
			"score_calibration": score_calibration,
			"score_calibration_modes": calibration_modes,
			"model_health": model_health,
			"lift_gain_curve": lift_gain_curve,
			"score_drift": score_drift,
			"threshold_simulator": threshold_simulator,
			"model_comparison": model_comparison,
			"label_source": self.label_source,
			"ground_truth_coverage": "FULL" if full_ground_truth else "FLAGGED_ONLY",
		}

	def _compute_segment_row_metrics(
		self,
		seg_val: str,
		label: str,
		row: tuple[Any, ...],
		overall_fraud_rate: Optional[float],
		full_ground_truth: bool,
	) -> dict[str, Any]:
		tot_c = int(row[0] or 0)
		flg_c = int(row[1] or 0)
		tp_c = int(row[2] or 0)
		fp_c = int(row[3] or 0)
		fn_c = int(row[4] or 0)
		tn_c = int(row[5] or 0)
		tot_amt = round(float(row[6] or 0.0), 2)
		rsk_amt = round(float(row[7] or 0.0), 2)
		tp_amt = round(float(row[8] or 0.0), 2)
		fn_amt = round(float(row[9] or 0.0), 2)

		eval_flagged = tp_c + fp_c
		verified_sample_cnt = tp_c + fp_c + fn_c + tn_c
		seg_fraud_cnt = tp_c + fn_c
		seg_fraud_rate = (seg_fraud_cnt / tot_c) if (full_ground_truth and tot_c > 0) else None
		lift = (
			round(seg_fraud_rate / overall_fraud_rate, 2)
			if (seg_fraud_rate is not None and overall_fraud_rate and overall_fraud_rate > 0)
			else None
		)
		return {
			"segment_value": seg_val,
			"label": label,
			"total_count": tot_c,
			"flagged_count": flg_c,
			"confirmed_fraud_count": seg_fraud_cnt,
			"false_positive_count": fp_c,
			"missed_fraud_count": fn_c if full_ground_truth else None,
			"missed_fraud_amount": fn_amt if full_ground_truth else None,
			"total_amount": tot_amt,
			"amount_at_risk": rsk_amt,
			"confirmed_fraud_amount": round(tp_amt + fn_amt, 2) if full_ground_truth else tp_amt,
			"prevented_fraud_amount": tp_amt,
			"alert_rate": round(flg_c / max(1, tot_c), 4) if tot_c > 0 else 0.0,
			"hit_rate": round(tp_c / eval_flagged, 4) if eval_flagged > 0 else None,
			"detection_rate": round(tp_c / seg_fraud_cnt, 4) if (full_ground_truth and seg_fraud_cnt > 0) else None,
			"lift": lift,
			"is_small_sample": verified_sample_cnt < 30,
		}

	def _compute_segment_analytics(self, full_ground_truth: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
		"""Computes 6-dimension Segment Alert Hit-Rate Matrix (Amount + 5 ProjectWarehouse entity columns)."""
		overall_row = self.conn.execute("""
			SELECT
				COUNT(*),
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0)
			FROM v_transactions
		""").fetchone()
		overall_tot = int(overall_row[0] or 0)
		overall_frd = int(overall_row[1] or 0)
		overall_fraud_rate = (overall_frd / overall_tot) if (full_ground_truth and overall_tot > 0) else None

		amount_brackets: list[dict[str, Any]] = []
		amount_segment_items: list[dict[str, Any]] = []
		for bracket_id, label, low, high in AMOUNT_BRACKET_SPECS:
			where_clause = "amount >= ?" if math.isinf(high) else "amount >= ? AND amount < ?"
			params = [low] if math.isinf(high) else [low, high]
			b_row = self.conn.execute(f"""
				SELECT
					COUNT(*) AS total_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS tp_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS fp_count,
					COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS fn_count,
					COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS tn_count,
					COALESCE(SUM(amount), 0.0) AS total_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 1 THEN amount ELSE 0.0 END), 0.0) AS risk_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS tp_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fn_amount
				FROM v_transactions
				WHERE {where_clause}
			""", params).fetchone()
			seg_item = self._compute_segment_row_metrics(bracket_id, label, b_row, overall_fraud_rate, full_ground_truth)
			amount_segment_items.append(seg_item)
			amount_brackets.append({
				"bracket_id": bracket_id,
				"label": label,
				"total_count": seg_item["total_count"],
				"flagged_count": seg_item["flagged_count"],
				"confirmed_fraud_count": seg_item["confirmed_fraud_count"],
				"false_positive_count": seg_item["false_positive_count"],
				"total_amount": seg_item["total_amount"],
				"amount_at_risk": seg_item["amount_at_risk"],
				"confirmed_fraud_amount": seg_item["prevented_fraud_amount"],
				"flag_rate": seg_item["alert_rate"],
			})

		segment_analytics: dict[str, Any] = {
			"amount_brackets": {
				"dimension": "amount_brackets",
				"label": SEGMENT_DIMENSION_LABELS["amount_brackets"],
				"available": overall_tot > 0,
				"items": amount_segment_items,
			}
		}
		for col in ("merchant_category", "merchant_id", "device_id", "ip_address", "card_id"):
			non_null = int(self.conn.execute(f"SELECT COUNT(*) FROM v_transactions WHERE {col} IS NOT NULL").fetchone()[0] or 0)
			if non_null == 0:
				segment_analytics[col] = {
					"dimension": col,
					"label": SEGMENT_DIMENSION_LABELS[col],
					"available": False,
					"items": [],
				}
				continue
			seg_rows = self.conn.execute(f"""
				SELECT
					{col} AS seg_val,
					COUNT(*) AS total_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS tp_count,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS fp_count,
					COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS fn_count,
					COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS tn_count,
					COALESCE(SUM(amount), 0.0) AS total_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 1 THEN amount ELSE 0.0 END), 0.0) AS risk_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS tp_amount,
					COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fn_amount
				FROM v_transactions
				WHERE {col} IS NOT NULL
				GROUP BY {col}
				ORDER BY flagged_count DESC, total_count DESC, seg_val ASC
				LIMIT 20
			""").fetchall()
			items = [
				self._compute_segment_row_metrics(str(r[0]), str(r[0]), r[1:], overall_fraud_rate, full_ground_truth)
				for r in seg_rows
			]
			segment_analytics[col] = {
				"dimension": col,
				"label": SEGMENT_DIMENSION_LABELS[col],
				"available": True,
				"items": items,
			}

		return amount_brackets, segment_analytics

	def compute_typology_and_patterns(self) -> dict[str, Any]:
		"""Computes SUC-24: Fraud Typology & FP Reason Breakdown, 24h Temporal Profile, 6-Dim Segment Hit-Rate, Top Subjects & Watchlist Impact."""
		fraud_cases = [c for c in self.cases if c.status == CaseStatus.RESOLVED_FRAUD]
		legit_cases = [c for c in self.cases if c.status == CaseStatus.RESOLVED_LEGITIMATE]

		typology_counts: dict[str, dict[str, Any]] = {
			code: {"code": code, "label": label, "case_count": 0, "total_amount": 0.0}
			for code, label in FRAUD_TYPOLOGY_LABELS.items()
		}
		for c in fraud_cases:
			code = c.resolution_reason if c.resolution_reason in typology_counts else "OTHER_FRAUD"
			typology_counts[code]["case_count"] += 1
			typology_counts[code]["total_amount"] = round(typology_counts[code]["total_amount"] + float(c.amount), 2)

		total_fraud_cases = len(fraud_cases)
		typology_breakdown = [
			{
				**item,
				"pct": round(item["case_count"] / max(1, total_fraud_cases), 4) if total_fraud_cases > 0 else 0.0,
			}
			for item in sorted(typology_counts.values(), key=lambda x: (-x["case_count"], -x["total_amount"]))
		]

		fp_counts: dict[str, dict[str, Any]] = {
			code: {"code": code, "label": label, "case_count": 0, "total_amount": 0.0}
			for code, label in FP_REASON_LABELS.items()
		}
		for c in legit_cases:
			code = c.resolution_reason if c.resolution_reason in fp_counts else "OTHER_LEGITIMATE"
			fp_counts[code]["case_count"] += 1
			fp_counts[code]["total_amount"] = round(fp_counts[code]["total_amount"] + float(c.amount), 2)

		total_legit_cases = len(legit_cases)
		fp_reason_breakdown = [
			{
				**item,
				"pct": round(item["case_count"] / max(1, total_legit_cases), 4) if total_legit_cases > 0 else 0.0,
			}
			for item in sorted(fp_counts.values(), key=lambda x: (-x["case_count"], -x["total_amount"]))
		]

		counts_row = self.conn.execute("""
			SELECT
				COUNT(*),
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0),
				COALESCE(SUM(CASE WHEN is_flagged = 0 AND effective_label IN (0, 1) THEN 1 ELSE 0 END), 0)
			FROM v_transactions
		""").fetchone()
		full_ground_truth = self._has_full_ground_truth(
			int(counts_row[0] or 0),
			int(counts_row[1] or 0),
			int(counts_row[2] or 0),
		)

		# Frame 2: Temporal Fraud Distribution (24 hours: 00h -> 23h) with strict separation of confirmed_fraud_rate vs flagged_rate
		hour_rows = self.conn.execute("""
			SELECT
				hour_utc,
				COUNT(*) AS total_tx,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_tx,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS fraud_tx,
				COALESCE(SUM(amount), 0.0) AS total_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN amount ELSE 0.0 END), 0.0) AS at_risk_amount
			FROM v_transactions
			GROUP BY hour_utc
		""").fetchall()
		hour_map = {int(r[0]): r for r in hour_rows if r[0] is not None and 0 <= int(r[0]) <= 23}

		hourly_distribution: list[dict[str, Any]] = []
		for h in range(24):
			r = hour_map.get(h)
			tot_tx = int(r[1] or 0) if r else 0
			flg_tx = int(r[2] or 0) if r else 0
			frd_tx = int(r[3] or 0) if r else 0
			tot_amt = round(float(r[4] or 0.0), 2) if r else 0.0
			rsk_amt = round(float(r[5] or 0.0), 2) if r else 0.0
			confirmed_rate = round(frd_tx / max(1, tot_tx), 4) if tot_tx > 0 else 0.0
			flagged_rate = round(flg_tx / max(1, tot_tx), 4) if tot_tx > 0 else 0.0
			hourly_distribution.append({
				"hour": h,
				"label": f"{h:02d}:00",
				"total_tx_count": tot_tx,
				"flagged_tx_count": flg_tx,
				"confirmed_fraud_count": frd_tx,
				"total_amount": tot_amt,
				"at_risk_amount": rsk_amt,
				"confirmed_fraud_rate": confirmed_rate,
				"flagged_rate": flagged_rate,
				"fraud_rate": confirmed_rate,
			})

		has_any_confirmed = any(item["confirmed_fraud_count"] > 0 for item in hourly_distribution)
		ranked_hours = sorted(
			[item for item in hourly_distribution if (item["confirmed_fraud_count"] > 0 if has_any_confirmed else item["flagged_tx_count"] > 0)],
			key=lambda x: (-(x["confirmed_fraud_rate"] if has_any_confirmed else x["flagged_rate"]), -x["at_risk_amount"]),
		)
		peak_hour_set = {item["hour"] for item in ranked_hours[:4]}
		for item in hourly_distribution:
			item["is_peak_risk"] = item["hour"] in peak_hour_set

		amount_brackets, segment_analytics = self._compute_segment_analytics(full_ground_truth)

		# Frame 4: Top Flagged Subjects with TRUE total_tx_count across ALL transactions
		active_bl_users = {
			entry.entity_value
			for entry in self.blacklist
			if entry.status == "ACTIVE" and entry.entity_type.value == "USER_ID"
		}

		subj_rows = self.conn.execute("""
			SELECT
				user_id,
				COUNT(*) AS total_tx_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_tx_count,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS confirmed_fraud_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS fp_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN amount ELSE 0.0 END), 0.0) AS amount_at_risk,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS confirmed_fraud_amount,
				COALESCE(MAX(model_score), 0.0) AS max_model_score
			FROM v_transactions
			GROUP BY user_id
			HAVING COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) > 0
			ORDER BY confirmed_fraud_amount DESC, amount_at_risk DESC, flagged_tx_count DESC
			LIMIT 10
		""").fetchall()

		top_subjects = [
			{
				"user_id": str(r[0]),
				"total_tx_count": int(r[1] or 0),
				"flagged_tx_count": int(r[2] or 0),
				"confirmed_fraud_count": int(r[3] or 0),
				"false_positive_count": int(r[4] or 0),
				"amount_at_risk": round(float(r[5] or 0.0), 2),
				"confirmed_fraud_amount": round(float(r[6] or 0.0), 2),
				"max_model_score": round(float(r[7] or 0.0), 4),
				"is_blacklisted": str(r[0]) in active_bl_users,
			}
			for r in subj_rows
		]

		active_bl = [e for e in self.blacklist if e.status == "ACTIVE"]
		removed_bl = [e for e in self.blacklist if e.status != "ACTIVE"]
		entity_types = ["USER_ID", "CARD_ID", "DEVICE_ID", "IP_ADDRESS", "MERCHANT_ID"]
		by_entity_type = [
			{
				"entity_type": et,
				"active_count": sum(1 for e in active_bl if e.entity_type.value == et),
				"removed_count": sum(1 for e in removed_bl if e.entity_type.value == et),
			}
			for et in entity_types
		]

		# Watchlist Impact across all 5 entity columns in v_transactions
		bl_by_col: dict[str, set[str]] = {
			"user_id": {e.entity_value for e in active_bl if e.entity_type.value == "USER_ID" and e.entity_value},
			"card_id": {e.entity_value for e in active_bl if e.entity_type.value == "CARD_ID" and e.entity_value},
			"device_id": {e.entity_value for e in active_bl if e.entity_type.value == "DEVICE_ID" and e.entity_value},
			"ip_address": {e.entity_value for e in active_bl if e.entity_type.value == "IP_ADDRESS" and e.entity_value},
			"merchant_id": {e.entity_value for e in active_bl if e.entity_type.value == "MERCHANT_ID" and e.entity_value},
		}
		matched_tx_count = 0
		matched_flagged_count = 0
		matched_amount = 0.0
		predicates = []
		params_wl: list[str] = []
		for col_name, values in bl_by_col.items():
			if values:
				placeholders = ", ".join("?" for _ in values)
				predicates.append(f"{col_name} IN ({placeholders})")
				params_wl.extend(sorted(values))
		if predicates:
			wl_row = self.conn.execute(
				f"""
				SELECT
					COUNT(*),
					COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0),
					COALESCE(SUM(amount), 0.0)
				FROM v_transactions
				WHERE {" OR ".join(predicates)}
				""",
				params_wl,
			).fetchone()
			matched_tx_count = int(wl_row[0] or 0)
			matched_flagged_count = int(wl_row[1] or 0)
			matched_amount = round(float(wl_row[2] or 0.0), 2)

		watchlist_summary = {
			"active_blacklist_count": len(active_bl),
			"removed_blacklist_count": len(removed_bl),
			"matched_tx_count": matched_tx_count,
			"matched_flagged_count": matched_flagged_count,
			"matched_amount": matched_amount,
			"by_entity_type": by_entity_type,
			"recent_active_entries": [
				{
					"blacklist_id": str(e.blacklist_id),
					"entity_type": e.entity_type.value,
					"entity_value": e.entity_value,
					"reason": e.reason,
					"created_by": e.created_by,
					"created_at": e.created_at.isoformat(),
					"source_case_id": str(e.source_case_id) if e.source_case_id else None,
				}
				for e in active_bl[:10]
			],
		}

		return {
			"typology_breakdown": typology_breakdown,
			"fp_reason_breakdown": fp_reason_breakdown,
			"hourly_distribution": hourly_distribution,
			"amount_brackets": amount_brackets,
			"segment_analytics": segment_analytics,
			"top_flagged_subjects": top_subjects,
			"watchlist_summary": watchlist_summary,
			"label_source": self.label_source,
			"ground_truth_coverage": "FULL" if full_ground_truth else "FLAGGED_ONLY",
		}
