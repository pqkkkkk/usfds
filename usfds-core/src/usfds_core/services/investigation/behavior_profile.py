from math import isfinite

import pandas as pd

from usfds_core.domain.entities.case import Case, CaseStatus


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
	for column in ("device_id", "ip_address", "card_id", "merchant_id", "merchant_category"):
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
		"dataset_artifact_id": str(case.dataset_artifact_id), "source_case_id": str(case.case_id),
		"name": f"Draft from {case.case_code}", "message": "Review thresholds before saving" if clauses else "No eligible RAW features; build conditions manually"}