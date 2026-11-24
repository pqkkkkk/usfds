"""Seed templates for PAYMENT & LOCATIONS built-in PYTHON_CODE features."""

CARD_BIN_PREFIX_6_CODE = '''import re
import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "card_bin")
	if col not in df.columns:
		return pd.Series("", index=df.index, dtype=object)
	return df[col].fillna("").astype(str).apply(lambda s: re.sub(r"\\D+", "", s)[:6]).astype(object)
'''

AMOUNT_TO_MEAN_RATIO_CODE = '''import pandas as pd

def fit(train_df: pd.DataFrame, params: dict) -> dict:
	col = params.get("col", "amount")
	if col not in train_df.columns or len(train_df) == 0:
		return {"mean_amount": 1.0}
	vals = pd.to_numeric(train_df[col], errors="coerce").dropna()
	mean_val = float(vals.mean()) if len(vals) > 0 else 1.0
	if mean_val <= 1e-9:
		mean_val = 1.0
	return {"mean_amount": mean_val}

def compute(df: pd.DataFrame, params: dict, state: dict) -> pd.Series:
	col = params.get("col", "amount")
	if col not in df.columns:
		return pd.Series(1.0, index=df.index, dtype=float)
	denom = float((state or {}).get("mean_amount", 1.0) or 1.0)
	if abs(denom) <= 1e-9:
		denom = 1.0
	vals = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
	return (vals / denom).astype(float)
'''

GEO_DISTANCE_KM_CODE = '''import math
import pandas as pd

def _haversine(lat1, lon1, lat2, lon2):
	try:
		la1, lo1, la2, lo2 = float(lat1), float(lon1), float(lat2), float(lon2)
	except (TypeError, ValueError):
		return 0.0
	if any(math.isnan(x) for x in (la1, lo1, la2, lo2)):
		return 0.0
	r = 6371.0
	phi1, phi2 = math.radians(la1), math.radians(la2)
	dphi = math.radians(la2 - la1)
	dl = math.radians(lo2 - lo1)
	a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
	return 2.0 * r * math.asin(min(1.0, math.sqrt(max(0.0, a))))

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	lat_col = params.get("lat_col", "lat")
	lon_col = params.get("lon_col", "long")
	mlat_col = params.get("merch_lat_col", "merch_lat")
	mlon_col = params.get("merch_lon_col", "merch_long")
	if not all(c in df.columns for c in (lat_col, lon_col, mlat_col, mlon_col)):
		return pd.Series(0.0, index=df.index, dtype=float)
	dists = [
		_haversine(a, b, c, d)
		for a, b, c, d in zip(df[lat_col], df[lon_col], df[mlat_col], df[mlon_col])
	]
	return pd.Series(dists, index=df.index, dtype=float)
'''

GEO_TRAVEL_SPEED_KMH_CODE = '''import math
import pandas as pd

def _haversine(lat1, lon1, lat2, lon2):
	try:
		la1, lo1, la2, lo2 = float(lat1), float(lon1), float(lat2), float(lon2)
	except (TypeError, ValueError):
		return 0.0
	if any(math.isnan(x) for x in (la1, lo1, la2, lo2)):
		return 0.0
	r = 6371.0
	phi1, phi2 = math.radians(la1), math.radians(la2)
	dphi = math.radians(la2 - la1)
	dl = math.radians(lo2 - lo1)
	a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
	return 2.0 * r * math.asin(min(1.0, math.sqrt(max(0.0, a))))

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	user_col = params.get("user_col", "user_id")
	ts_col = params.get("ts_col", "timestamp")
	lat_col = params.get("lat_col", "lat")
	lon_col = params.get("lon_col", "long")
	if not all(c in df.columns for c in (user_col, ts_col, lat_col, lon_col)):
		return pd.Series(0.0, index=df.index, dtype=float)
	work = df[[user_col, ts_col, lat_col, lon_col]].copy()
	work["_orig_idx"] = df.index
	ts_raw = work[ts_col]
	if pd.api.types.is_numeric_dtype(ts_raw):
		work["_ts_parsed"] = pd.to_datetime(ts_raw, unit="s", errors="coerce")
	else:
		work["_ts_parsed"] = pd.to_datetime(ts_raw, errors="coerce")
	work = work.sort_values([user_col, "_ts_parsed", "_orig_idx"], kind="mergesort")
	prev_user = work[user_col].shift(1)
	prev_ts = work["_ts_parsed"].shift(1)
	prev_lat = work[lat_col].shift(1)
	prev_lon = work[lon_col].shift(1)
	speeds = []
	for u, pu, t, pt, la, pla, lo, plo in zip(
		work[user_col], prev_user, work["_ts_parsed"], prev_ts, work[lat_col], prev_lat, work[lon_col], prev_lon
	):
		if pd.isna(pu) or str(u) != str(pu) or pd.isna(t) or pd.isna(pt):
			speeds.append(0.0)
			continue
		hours = max((t - pt).total_seconds() / 3600.0, 1e-4)
		speeds.append(_haversine(pla, plo, la, lo) / hours)
	work["_speed"] = speeds
	restored = work.set_index("_orig_idx").loc[df.index, "_speed"]
	return restored.astype(float)
'''

ADDRESS_SIMILARITY_CODE = '''import re
import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col_a = params.get("col_a", "billing_zip")
	col_b = params.get("col_b", "country")
	if col_a not in df.columns or col_b not in df.columns:
		return pd.Series(0.0, index=df.index, dtype=float)
	def _sim(a, b):
		ta = set(re.findall(r"[a-z0-9]+", str(a or "").lower()))
		tb = set(re.findall(r"[a-z0-9]+", str(b or "").lower()))
		if not ta or not tb:
			return 0.0
		return float(len(ta & tb)) / float(len(ta | tb))
	vals = [_sim(a, b) for a, b in zip(df[col_a], df[col_b])]
	return pd.Series(vals, index=df.index, dtype=float)
'''
