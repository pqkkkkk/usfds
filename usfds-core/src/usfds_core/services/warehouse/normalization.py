"""Row-level value normalization shared by the Project Fact Warehouse and the Insight engine (ISS-012)."""

from datetime import datetime, timezone
import json
import math
from typing import Any, Optional

import pandas as pd


def safe_float(val: Any, default: float = 0.0) -> float:
	if val is None:
		return default
	try:
		res = float(val)
		return default if not math.isfinite(res) else res
	except (ValueError, TypeError):
		return default


def parse_rule_codes(raw_val: Any) -> list[str]:
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
			return parse_rule_codes(parsed)
		except Exception:
			return [text]
	return []


def extract_hour_utc(raw_ts: Any) -> int:
	if raw_ts is None:
		return 0
	if isinstance(raw_ts, datetime):
		dt = raw_ts if raw_ts.tzinfo else raw_ts.replace(tzinfo=timezone.utc)
		return dt.astimezone(timezone.utc).hour
	try:
		ts = pd.to_datetime(raw_ts, utc=True, errors="coerce")
		if pd.isna(ts):
			num = safe_float(raw_ts, -1.0)
			if num >= 0:
				return int((num // 3600) % 24)
			return 0
		return int(ts.hour)
	except Exception:
		return 0


def parse_tx_timestamp(raw_ts: Any) -> Optional[datetime]:
	"""Transaction time as naive UTC, or None when it is missing/unparseable or a bare number (seconds offset)."""
	if raw_ts is None or (isinstance(raw_ts, (int, float)) and not isinstance(raw_ts, bool)):
		return None
	try:
		if isinstance(raw_ts, datetime):
			dt = raw_ts
		else:
			ts = pd.to_datetime(raw_ts, utc=True, errors="coerce")
			if pd.isna(ts):
				return None
			dt = ts.to_pydatetime()
	except Exception:
		return None
	dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
	return dt.astimezone(timezone.utc).replace(tzinfo=None)
