"""DuckDB OLAP Analytical Engine for Insight & Report Module (SUC-22, SUC-23, SUC-24)."""

from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import duckdb
import numpy as np
import pandas as pd

from usfds_core.domain.entities.case import Case, CaseStatus, EntityBlacklist
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.storage.base_storage import IFileStorage

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


def _safe_float(val: Any, default: float = 0.0) -> float:
	if val is None:
		return default
	try:
		res = float(val)
		return default if not math.isfinite(res) else res
	except (ValueError, TypeError):
		return default


def _parse_rule_codes(raw_val: Any) -> list[str]:
	if raw_val is None:
		return []
	if isinstance(raw_val, list):
		out: list[str] = []
		for item in raw_val:
			if isinstance(item, dict) and item.get("rule_code"):
				out.append(str(item["rule_code"]))
			elif isinstance(item, str) and item.strip():
				out.append(item.strip())
		return sorted(set(out))
	if isinstance(raw_val, str):
		text = raw_val.strip()
		if not text:
			return []
		try:
			parsed = json.loads(text)
			return _parse_rule_codes(parsed)
		except Exception:
			return [text]
	return []


def _extract_hour_utc(raw_ts: Any) -> int:
	if raw_ts is None:
		return 0
	if isinstance(raw_ts, datetime):
		dt = raw_ts if raw_ts.tzinfo else raw_ts.replace(tzinfo=timezone.utc)
		return dt.astimezone(timezone.utc).hour
	try:
		ts = pd.to_datetime(raw_ts, utc=True, errors="coerce")
		if pd.isna(ts):
			num = _safe_float(raw_ts, -1.0)
			if num >= 0:
				return int((num // 3600) % 24)
			return 0
		return int(ts.hour)
	except Exception:
		return 0


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
		self.conn = duckdb.connect(":memory:")
		self.has_dataset_labels = False
		self._tx_df = self._build_unified_transactions_df()
		self.conn.register("v_transactions", self._tx_df)

	def _read_parquet_bytes(self, storage_path: str) -> Optional[bytes]:
		if not storage_path:
			return None
		local_path = Path(storage_path)
		if local_path.is_file():
			return local_path.read_bytes()
		if self.file_storage and self.file_storage.exists(storage_path):
			try:
				return self.file_storage.read_bytes(storage_path)
			except Exception:
				return None
		return None

	def _build_unified_transactions_df(self) -> pd.DataFrame:
		"""Loads projected columns from DetectionJob parquet files and joins with Case ground-truth labels."""
		cases_by_event: dict[str, Case] = {str(c.event_id): c for c in self.cases}
		seen_events: set[str] = set()
		rows: list[dict[str, Any]] = []

		# Sort jobs chronologically so latest scan wins if an event_id was scanned multiple times
		sorted_jobs = sorted(
			self.jobs,
			key=lambda j: j.created_at or datetime.min.replace(tzinfo=timezone.utc),
		)

		for job in sorted_jobs:
			status_str = job.status.value if hasattr(job.status, "value") else str(job.status)
			if status_str != "COMPLETED" or not job.output_path:
				continue
			raw_bytes = self._read_parquet_bytes(job.output_path)
			if not raw_bytes:
				continue
			try:
				df = pd.read_parquet(io.BytesIO(raw_bytes))
			except Exception:
				continue
			if df.empty:
				continue

			id_col = next((c for c in ("event_id", "transaction_id", "tx_id", "id") if c in df.columns), None)
			user_col = next((c for c in ("user_id", "account_id", "card_id", "customer_id", "entity_id") if c in df.columns), None)
			ts_col = next((c for c in ("timestamp", "transaction_time", "tx_time", "event_timestamp", "time") if c in df.columns), None)
			amt_col = next((c for c in ("amount", "tx_amount", "transaction_amount", "amt", "Amount") if c in df.columns), None)
			lbl_col = next((c for c in ("label", "is_fraud", "isFraud", "Class", "class", "target") if c in df.columns), None)

			if lbl_col is not None:
				self.has_dataset_labels = True

			threshold = _safe_float(job.score_threshold, 0.5)
			has_model = bool(job.model_version_id is not None or (job.summary_metrics or {}).get("has_model", True))
			job_id_str = str(job.job_id)
			job_name_str = job.job_name or f"Job-{job_id_str[:8]}"
			job_time_str = (job.created_at or datetime.now(timezone.utc)).isoformat()
			model_ver_str = str(job.model_version_id) if job.model_version_id else ""

			records = df.to_dict(orient="records")
			for idx, rec in enumerate(records):
				ev_raw = rec.get(id_col) if id_col and rec.get(id_col) is not None else f"{job_id_str}:{idx + 1}"
				ev_id = str(ev_raw)
				seen_events.add(ev_id)

				user_id = str(rec.get(user_col) if user_col and rec.get(user_col) is not None else "unknown")
				amount = max(0.0, _safe_float(rec.get(amt_col) if amt_col else 0.0, 0.0))
				m_score = min(1.0, max(0.0, _safe_float(rec.get("model_score", rec.get("fraud_probability", 0.0)), 0.0)))

				final_action = str(
					rec.get("final_action") or ("REVIEW" if rec.get("prediction") == 1 else "ALLOW")
				).upper()
				rule_action = str(rec.get("rule_action") or "ALLOW").upper()
				is_flagged = 1 if final_action in ("REJECT", "REVIEW") else 0

				rule_codes = _parse_rule_codes(rec.get("triggered_rules"))
				has_rule_hit = 1 if (len(rule_codes) > 0 or rule_action in ("REJECT", "REVIEW")) else 0
				has_ai_hit = 1 if (has_model and m_score >= threshold) else 0

				ds_label: Optional[int] = None
				if lbl_col and rec.get(lbl_col) is not None:
					try:
						lbl_val = int(float(rec[lbl_col]))
						if lbl_val in (0, 1):
							ds_label = lbl_val
					except (ValueError, TypeError):
						ds_label = None

				matched_case = cases_by_event.get(ev_id)
				verified_lbl = matched_case.verified_label if matched_case else None
				if matched_case and matched_case.triggered_rule_codes:
					rule_codes = sorted(set(rule_codes) | set(matched_case.triggered_rule_codes))
					if rule_codes:
						has_rule_hit = 1

				if verified_lbl is not None:
					eff_label: Optional[int] = verified_lbl
					lbl_origin = "VERIFIED_CASE"
				elif self.label_source == "VERIFIED_WITH_DATASET_FALLBACK" and ds_label is not None:
					eff_label = ds_label
					lbl_origin = "DATASET_FALLBACK"
				else:
					eff_label = None
					lbl_origin = "UNVERIFIED"

				hour_utc = (
					_extract_hour_utc(matched_case.tx_timestamp)
					if matched_case
					else _extract_hour_utc(rec.get(ts_col) if ts_col else None)
				)

				rows.append({
					"job_id": job_id_str,
					"job_name": job_name_str,
					"job_created_at": job_time_str,
					"model_version_id": model_ver_str,
					"score_threshold": threshold,
					"event_id": ev_id,
					"user_id": matched_case.user_id if matched_case else user_id,
					"hour_utc": hour_utc,
					"amount": float(matched_case.amount) if matched_case else amount,
					"model_score": float(matched_case.model_score) if (matched_case and matched_case.model_score is not None) else m_score,
					"rule_action": rule_action,
					"final_action": matched_case.final_action.value if matched_case else final_action,
					"is_flagged": 1 if matched_case else is_flagged,
					"has_rule_hit": has_rule_hit,
					"has_ai_hit": has_ai_hit,
					"rule_codes_json": json.dumps(rule_codes),
					"has_case": 1 if matched_case else 0,
					"case_id": str(matched_case.case_id) if matched_case else "",
					"case_status": matched_case.status.value if matched_case else "",
					"case_priority": matched_case.priority.value if matched_case else "",
					"resolution_reason": matched_case.resolution_reason or "" if matched_case else "",
					"verified_label": verified_lbl if verified_lbl is not None else -1,
					"dataset_label": ds_label if ds_label is not None else -1,
					"effective_label": eff_label if eff_label is not None else -1,
					"label_origin": lbl_origin,
				})

		# Fallback: Include any Case whose event_id was not present in loaded parquet files
		for case in self.cases:
			ev_id = str(case.event_id)
			if ev_id in seen_events:
				continue
			seen_events.add(ev_id)
			rule_codes = case.triggered_rule_codes
			m_score = _safe_float(case.model_score, 0.0) if case.model_score is not None else 0.0
			has_rule_hit = 1 if len(rule_codes) > 0 else 0
			has_ai_hit = 1 if (case.model_score is not None and m_score >= 0.5) else (1 if not has_rule_hit else 0)
			verified_lbl = case.verified_label
			rows.append({
				"job_id": str(case.detection_job_id) if case.detection_job_id else "case-intake",
				"job_name": f"Case Intake ({case.created_at.strftime('%Y-%m-%d')})",
				"job_created_at": case.created_at.isoformat(),
				"model_version_id": str(case.model_version_id) if case.model_version_id else "",
				"score_threshold": 0.5,
				"event_id": ev_id,
				"user_id": case.user_id,
				"hour_utc": _extract_hour_utc(case.tx_timestamp),
				"amount": max(0.0, _safe_float(case.amount, 0.0)),
				"model_score": m_score,
				"rule_action": case.final_action.value if has_rule_hit else "ALLOW",
				"final_action": case.final_action.value,
				"is_flagged": 1,
				"has_rule_hit": has_rule_hit,
				"has_ai_hit": has_ai_hit,
				"rule_codes_json": json.dumps(rule_codes),
				"has_case": 1,
				"case_id": str(case.case_id),
				"case_status": case.status.value,
				"case_priority": case.priority.value,
				"resolution_reason": case.resolution_reason or "",
				"verified_label": verified_lbl if verified_lbl is not None else -1,
				"dataset_label": -1,
				"effective_label": verified_lbl if verified_lbl is not None else -1,
				"label_origin": "VERIFIED_CASE" if verified_lbl is not None else "UNVERIFIED",
			})

		if not rows:
			return pd.DataFrame(columns=[
				"job_id", "job_name", "job_created_at", "model_version_id", "score_threshold",
				"event_id", "user_id", "hour_utc", "amount", "model_score", "rule_action",
				"final_action", "is_flagged", "has_rule_hit", "has_ai_hit", "rule_codes_json",
				"has_case", "case_id", "case_status", "case_priority", "resolution_reason",
				"verified_label", "dataset_label", "effective_label", "label_origin",
			])

		return pd.DataFrame(rows)

	def compute_executive_overview(self) -> dict[str, Any]:
		"""Computes SUC-22: 6 Executive KPIs, 4-Stage Funnel, Financial Protection Trend, and Queue Breakdown."""
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
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = -1 THEN 1 ELSE 0 END), 0) AS pending_eval_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = -1 THEN amount ELSE 0.0 END), 0.0) AS pending_eval_amount,
				COALESCE(SUM(CASE WHEN verified_label = 1 THEN amount ELSE 0.0 END), 0.0) AS verified_case_fraud_amount,
				COALESCE(SUM(CASE WHEN verified_label = 0 THEN amount ELSE 0.0 END), 0.0) AS verified_case_fp_amount
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
		pending_eval_count = int(agg[10] or 0)
		pending_eval_amount = round(float(agg[11] or 0.0), 2)

		# Case operations metrics from self.cases
		total_cases = len(self.cases)
		open_cases = sum(1 for c in self.cases if c.status == CaseStatus.OPEN)
		in_progress_cases = sum(1 for c in self.cases if c.status == CaseStatus.IN_PROGRESS)
		pending_customer_cases = sum(1 for c in self.cases if c.status == CaseStatus.PENDING_CUSTOMER)
		resolved_fraud_cases = sum(1 for c in self.cases if c.status == CaseStatus.RESOLVED_FRAUD)
		resolved_legit_cases = sum(1 for c in self.cases if c.status == CaseStatus.RESOLVED_LEGITIMATE)
		resolved_cases = resolved_fraud_cases + resolved_legit_cases
		critical_high_backlog = sum(
			1 for c in self.cases
			if c.status in (CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.PENDING_CUSTOMER)
			and c.priority.value in ("CRITICAL", "HIGH")
		)
		dispatched_amount = round(sum(float(c.amount) for c in self.cases), 2)

		evaluated_alerts = tp_count + fp_count
		verified_precision = round(tp_count / evaluated_alerts, 4) if evaluated_alerts > 0 else None
		alert_to_fraud_ratio = round(evaluated_alerts / tp_count, 2) if tp_count > 0 else None
		insult_rate = round(fp_count / max(1, flagged_count), 4) if flagged_count > 0 else 0.0
		volume_insult_rate = round(fp_friction_volume / max(1.0, gross_amount), 4) if gross_amount > 0 else 0.0
		case_resolution_rate = round(resolved_cases / total_cases, 4) if total_cases > 0 else 0.0

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
			"false_positive_friction_volume": fp_friction_volume,
			"false_positive_count": fp_count,
			"insult_rate": insult_rate,
			"volume_insult_rate": volume_insult_rate,
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
			"label_source": self.label_source,
			"has_dataset_labels": self.has_dataset_labels,
		}

		funnel = [
			{
				"stage": "SCANNED",
				"label": "1. Total Scanned",
				"tx_count": gross_count,
				"amount": gross_amount,
				"conversion_rate": 1.0 if gross_count > 0 else 0.0,
			},
			{
				"stage": "FLAGGED",
				"label": "2. Flagged (REJECT / REVIEW)",
				"tx_count": flagged_count,
				"amount": amount_at_risk,
				"conversion_rate": round(flagged_count / max(1, gross_count), 4) if gross_count > 0 else 0.0,
				"reject_count": reject_count,
				"review_count": review_count,
			},
			{
				"stage": "DISPATCHED",
				"label": "3. Dispatched to Cases",
				"tx_count": total_cases,
				"amount": dispatched_amount,
				"conversion_rate": round(total_cases / max(1, flagged_count), 4) if flagged_count > 0 else 0.0,
			},
			{
				"stage": "RESOLVED",
				"label": "4. Evaluated / Resolved",
				"tx_count": evaluated_alerts,
				"amount": round(fraud_loss_prevented + fp_friction_volume, 2),
				"conversion_rate": round(evaluated_alerts / max(1, flagged_count), 4) if flagged_count > 0 else 0.0,
				"confirmed_fraud_count": tp_count,
				"confirmed_fraud_amount": fraud_loss_prevented,
				"false_positive_count": fp_count,
				"false_positive_amount": fp_friction_volume,
				"pending_count": pending_eval_count,
				"pending_amount": pending_eval_amount,
			},
		]

		trend_rows = self.conn.execute("""
			SELECT
				job_id,
				job_name,
				MIN(job_created_at) AS created_at,
				COUNT(*) AS scanned_count,
				COALESCE(SUM(amount), 0.0) AS scanned_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS confirmed_fraud_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS false_positive_amount,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = -1 THEN amount ELSE 0.0 END), 0.0) AS pending_review_amount
			FROM v_transactions
			GROUP BY job_id, job_name
			ORDER BY MIN(job_created_at) ASC
		""").fetchall()

		financial_trends = []
		for r in trend_rows:
			sc_cnt = int(r[3] or 0)
			fl_cnt = int(r[5] or 0)
			financial_trends.append({
				"job_id": str(r[0]),
				"job_name": str(r[1]),
				"created_at": str(r[2]),
				"scanned_count": sc_cnt,
				"scanned_amount": round(float(r[4] or 0.0), 2),
				"flagged_count": fl_cnt,
				"confirmed_fraud_amount": round(float(r[6] or 0.0), 2),
				"false_positive_amount": round(float(r[7] or 0.0), 2),
				"pending_review_amount": round(float(r[8] or 0.0), 2),
				"fraud_rate": round(fl_cnt / max(1, sc_cnt), 4),
			})

		status_order = [
			("OPEN", "Open"),
			("IN_PROGRESS", "In Progress"),
			("PENDING_CUSTOMER", "Pending Customer"),
			("RESOLVED_FRAUD", "Confirmed Fraud"),
			("RESOLVED_LEGITIMATE", "False Positive / Legit"),
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
			"queue_breakdown": {
				"by_status": by_status,
				"by_priority": by_priority,
			},
		}

	def compute_effectiveness_analysis(self) -> dict[str, Any]:
		"""Computes SUC-23: AI vs Rule Attribution, Rule Ground-Truth Leaderboard, and Score Calibration / Simulator."""
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
					"label": "AI-Exclusive Catches (ML Only)",
					"fraud_count": ai_only_cnt,
					"count_pct": round(ai_only_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
					"fraud_amount": ai_only_amt,
					"amount_pct": round(ai_only_amt / max(1.0, total_caught_amt), 4) if total_caught_amt > 0 else 0.0,
				},
				{
					"segment": "CONSENSUS_OVERLAP",
					"label": "Consensus / Overlap (Both AI & Rules)",
					"fraud_count": overlap_cnt,
					"count_pct": round(overlap_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
					"fraud_amount": overlap_amt,
					"amount_pct": round(overlap_amt / max(1.0, total_caught_amt), 4) if total_caught_amt > 0 else 0.0,
				},
				{
					"segment": "RULE_EXCLUSIVE",
					"label": "Rule-Exclusive Catches (Rules Only)",
					"fraud_count": rule_only_cnt,
					"count_pct": round(rule_only_cnt / max(1, total_caught), 4) if total_caught > 0 else 0.0,
					"fraud_amount": rule_only_amt,
					"amount_pct": round(rule_only_amt / max(1.0, total_caught_amt), 4) if total_caught_amt > 0 else 0.0,
				},
			],
		}

		# Area 2: Rule Ground-Truth Leaderboard
		gross_count = len(self._tx_df)
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
			}

		# Enrich rule metadata from case snapshots if a rule is not in rule_catalog
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
					}

		if not self._tx_df.empty:
			for row in self._tx_df.itertuples(index=False):
				codes = _parse_rule_codes(row.rule_codes_json)
				if not codes:
					continue
				amt = float(row.amount)
				eff_lbl = int(row.effective_label)
				for code in codes:
					entry = rule_catalog.setdefault(code, {
						"rule_id": "",
						"rule_code": code,
						"rule_name": code,
						"status": "ACTIVE",
						"action": str(row.rule_action or "REVIEW"),
						"version_number": 1,
						"total_hits": 0,
						"verified_cases": 0,
						"verified_tp": 0,
						"verified_fp": 0,
						"pending_cases": 0,
						"fraud_value_caught": 0.0,
						"false_positive_value": 0.0,
					})
					entry["total_hits"] += 1
					if eff_lbl == 1:
						entry["verified_cases"] += 1
						entry["verified_tp"] += 1
						entry["fraud_value_caught"] = round(entry["fraud_value_caught"] + amt, 2)
					elif eff_lbl == 0:
						entry["verified_cases"] += 1
						entry["verified_fp"] += 1
						entry["false_positive_value"] = round(entry["false_positive_value"] + amt, 2)
					else:
						entry["pending_cases"] += 1

		leaderboard: list[dict[str, Any]] = []
		for entry in rule_catalog.values():
			ver_cnt = entry["verified_cases"]
			tp = entry["verified_tp"]
			fp = entry["verified_fp"]
			prec = round(tp / ver_cnt, 4) if ver_cnt > 0 else None
			fpr = round(fp / ver_cnt, 4) if ver_cnt > 0 else None
			if ver_cnt == 0:
				health_tag = "UNVERIFIED"
			elif fpr is not None and fpr >= 0.70:
				health_tag = "NOISY"
			elif prec is not None and prec >= 0.70:
				health_tag = "HIGH_VALUE"
			else:
				health_tag = "BALANCED"

			leaderboard.append({
				**entry,
				"hit_rate": round(entry["total_hits"] / max(1, gross_count), 4) if gross_count > 0 else 0.0,
				"verified_precision": prec,
				"verified_fpr": fpr,
				"policy_health_tag": health_tag,
			})

		leaderboard.sort(
			key=lambda x: (-x["fraud_value_caught"], -x["total_hits"], x["rule_code"])
		)

		# Area 3: Model Score Calibration (10 bins: 0.0-0.1 .. 0.9-1.0) & What-If Threshold Simulator
		bins = np.linspace(0.0, 1.0, 11)
		score_calibration: list[dict[str, Any]] = []
		for i in range(10):
			low = round(float(bins[i]), 2)
			high = round(float(bins[i + 1]), 2)
			op = "<=" if i == 9 else "<"
			b_row = self.conn.execute(f"""
				SELECT
					COUNT(*) AS total_count,
					COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS fraud_count,
					COALESCE(SUM(CASE WHEN effective_label = 0 THEN 1 ELSE 0 END), 0) AS legit_count,
					COALESCE(SUM(CASE WHEN effective_label = -1 THEN 1 ELSE 0 END), 0) AS unverified_count,
					COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fraud_amount,
					COALESCE(SUM(CASE WHEN effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS legit_amount
				FROM v_transactions
				WHERE model_score >= ? AND model_score {op} ?
			""", [low, high]).fetchone()
			score_calibration.append({
				"bin": f"{low:.1f}-{high:.1f}",
				"lower": low,
				"upper": high,
				"total_count": int(b_row[0] or 0),
				"confirmed_fraud_count": int(b_row[1] or 0),
				"false_positive_count": int(b_row[2] or 0),
				"unverified_count": int(b_row[3] or 0),
				"fraud_amount": round(float(b_row[4] or 0.0), 2),
				"false_positive_amount": round(float(b_row[5] or 0.0), 2),
			})

		# Precompute What-If Threshold Simulator curve (0.05 to 0.95 step 0.05)
		total_known_fraud_row = self.conn.execute("""
			SELECT
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS total_fraud,
				COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS total_fraud_amt,
				COALESCE(SUM(CASE WHEN is_flagged = 1 AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS baseline_fp
			FROM v_transactions
		""").fetchone()
		total_known_fraud = int(total_known_fraud_row[0] or 0)
		baseline_fp = int(total_known_fraud_row[2] or 0)

		threshold_curve: list[dict[str, Any]] = []
		for step_int in range(5, 100, 5):
			thresh = round(step_int / 100.0, 2)
			sim_row = self.conn.execute("""
				SELECT
					COALESCE(SUM(CASE WHEN model_score >= ? OR has_rule_hit = 1 THEN 1 ELSE 0 END), 0) AS sim_flagged_all,
					COALESCE(SUM(CASE WHEN model_score >= ? THEN 1 ELSE 0 END), 0) AS sim_model_flagged,
					COALESCE(SUM(CASE WHEN model_score >= ? AND effective_label = 1 THEN 1 ELSE 0 END), 0) AS sim_tp,
					COALESCE(SUM(CASE WHEN model_score >= ? AND effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS sim_tp_amt,
					COALESCE(SUM(CASE WHEN model_score >= ? AND effective_label = 0 THEN 1 ELSE 0 END), 0) AS sim_fp,
					COALESCE(SUM(CASE WHEN model_score >= ? AND effective_label = 0 THEN amount ELSE 0.0 END), 0.0) AS sim_fp_amt
				FROM v_transactions
			""", [thresh, thresh, thresh, thresh, thresh, thresh]).fetchone()

			sim_flagged_all = int(sim_row[0] or 0)
			sim_model_flagged = int(sim_row[1] or 0)
			sim_tp = int(sim_row[2] or 0)
			sim_tp_amt = round(float(sim_row[3] or 0.0), 2)
			sim_fp = int(sim_row[4] or 0)
			sim_fp_amt = round(float(sim_row[5] or 0.0), 2)
			sim_eval = sim_tp + sim_fp

			est_recall = round(sim_tp / max(1, total_known_fraud), 4) if total_known_fraud > 0 else 0.0
			est_precision = round(sim_tp / max(1, sim_eval), 4) if sim_eval > 0 else 0.0
			fp_reduction = (
				round((baseline_fp - sim_fp) / max(1, baseline_fp), 4)
				if baseline_fp > 0
				else 0.0
			)

			threshold_curve.append({
				"threshold": thresh,
				"review_queue_volume": sim_model_flagged,
				"hybrid_queue_volume": sim_flagged_all,
				"caught_fraud_count": sim_tp,
				"caught_fraud_amount": sim_tp_amt,
				"false_positive_count": sim_fp,
				"false_positive_amount": sim_fp_amt,
				"estimated_recall": est_recall,
				"estimated_precision": est_precision,
				"fp_reduction_pct": fp_reduction,
			})

		return {
			"attribution": attribution,
			"rule_leaderboard": leaderboard,
			"score_calibration": score_calibration,
			"threshold_simulator": {
				"total_known_fraud_count": total_known_fraud,
				"baseline_fp_count": baseline_fp,
				"curve": threshold_curve,
			},
			"label_source": self.label_source,
		}

	def compute_typology_and_patterns(self) -> dict[str, Any]:
		"""Computes SUC-24: Fraud Typology & FP Reason Breakdown, 24h Temporal Profile, Amount Brackets, Top Subjects & Watchlist."""
		# Frame 1: Fraud Typology & False Positive Reason Breakdown
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

		# Frame 2: Temporal Fraud Distribution (24 hours: 00h -> 23h)
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
			rate = round((frd_tx if frd_tx > 0 else flg_tx) / max(1, tot_tx), 4) if tot_tx > 0 else 0.0
			hourly_distribution.append({
				"hour": h,
				"label": f"{h:02d}:00",
				"total_tx_count": tot_tx,
				"flagged_tx_count": flg_tx,
				"confirmed_fraud_count": frd_tx,
				"total_amount": tot_amt,
				"at_risk_amount": rsk_amt,
				"fraud_rate": rate,
			})

		# Mark top 4 highest fraud_rate hours (with at least 1 flagged/fraud tx) as peak risk hours
		ranked_hours = sorted(
			[item for item in hourly_distribution if item["flagged_tx_count"] > 0 or item["confirmed_fraud_count"] > 0],
			key=lambda x: (-x["fraud_rate"], -x["at_risk_amount"]),
		)
		peak_hour_set = {item["hour"] for item in ranked_hours[:4]}
		for item in hourly_distribution:
			item["is_peak_risk"] = item["hour"] in peak_hour_set

		# Frame 3: Amount Bracket Risk Profile (5 segments)
		amount_brackets: list[dict[str, Any]] = []
		for bracket_id, label, low, high in AMOUNT_BRACKET_SPECS:
			if math.isinf(high):
				b_row = self.conn.execute("""
					SELECT
						COUNT(*) AS total_count,
						COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
						COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS fraud_count,
						COALESCE(SUM(CASE WHEN effective_label = 0 AND is_flagged = 1 THEN 1 ELSE 0 END), 0) AS fp_count,
						COALESCE(SUM(amount), 0.0) AS total_amount,
						COALESCE(SUM(CASE WHEN is_flagged = 1 THEN amount ELSE 0.0 END), 0.0) AS risk_amount,
						COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fraud_amount
					FROM v_transactions
					WHERE amount >= ?
				""", [low]).fetchone()
			else:
				b_row = self.conn.execute("""
					SELECT
						COUNT(*) AS total_count,
						COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) AS flagged_count,
						COALESCE(SUM(CASE WHEN effective_label = 1 THEN 1 ELSE 0 END), 0) AS fraud_count,
						COALESCE(SUM(CASE WHEN effective_label = 0 AND is_flagged = 1 THEN 1 ELSE 0 END), 0) AS fp_count,
						COALESCE(SUM(amount), 0.0) AS total_amount,
						COALESCE(SUM(CASE WHEN is_flagged = 1 THEN amount ELSE 0.0 END), 0.0) AS risk_amount,
						COALESCE(SUM(CASE WHEN effective_label = 1 THEN amount ELSE 0.0 END), 0.0) AS fraud_amount
					FROM v_transactions
					WHERE amount >= ? AND amount < ?
				""", [low, high]).fetchone()

			tot_c = int(b_row[0] or 0)
			flg_c = int(b_row[1] or 0)
			amount_brackets.append({
				"bracket_id": bracket_id,
				"label": label,
				"total_count": tot_c,
				"flagged_count": flg_c,
				"confirmed_fraud_count": int(b_row[2] or 0),
				"false_positive_count": int(b_row[3] or 0),
				"total_amount": round(float(b_row[4] or 0.0), 2),
				"amount_at_risk": round(float(b_row[5] or 0.0), 2),
				"confirmed_fraud_amount": round(float(b_row[6] or 0.0), 2),
				"flag_rate": round(flg_c / max(1, tot_c), 4) if tot_c > 0 else 0.0,
			})

		# Frame 4: Top Flagged Subjects & Active Watchlist Impact
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
			WHERE is_flagged = 1
			GROUP BY user_id
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

		watchlist_summary = {
			"active_blacklist_count": len(active_bl),
			"removed_blacklist_count": len(removed_bl),
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
			"top_flagged_subjects": top_subjects,
			"watchlist_summary": watchlist_summary,
			"label_source": self.label_source,
		}
