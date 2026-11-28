"""Explicit label value validation and canonical binary (0/1) normalization helpers."""

import math
from typing import Any, Dict, List, Optional

_FLOAT_TYPES = {"FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "REAL"}
_BOOL_TYPES = {"BOOLEAN", "BOOL"}


def _quote_literal(value: str) -> str:
	return "'" + str(value).replace("'", "''") + "'"


def _parse_finite_float(text: str) -> Optional[float]:
	try:
		val = float(text)
	except (TypeError, ValueError):
		return None
	return val if math.isfinite(val) else None


def _build_numeric_lookup(mapping: Dict[str, int]) -> Dict[float, int]:
	"""Maps unambiguous numeric representations (e.g. '1' <-> '1.0') to 0/1."""
	lookup: Dict[float, int] = {}
	conflicted: set[float] = set()
	for key, target in mapping.items():
		num = _parse_finite_float(key)
		if num is None or num in conflicted:
			continue
		if num in lookup and lookup[num] != target:
			del lookup[num]
			conflicted.add(num)
			continue
		lookup[num] = target
	return lookup


def validate_label_value_mapping(
	mapping: Optional[Dict[str, int]],
) -> Optional[Dict[str, int]]:
	"""Validates and normalizes an explicit raw-label -> binary (0/1) mapping dictionary."""
	if mapping is None:
		return None
	if not isinstance(mapping, dict):
		raise ValueError("label_value_mapping phải là dictionary ánh xạ giá trị nguồn sang 0 hoặc 1.")
	if len(mapping) == 0:
		raise ValueError("label_value_mapping không được rỗng khi được cung cấp.")

	normalized: Dict[str, int] = {}
	for raw_key, target in mapping.items():
		if raw_key is None:
			raise ValueError("label_value_mapping không được chứa khóa rỗng.")
		key = str(raw_key).strip()
		if not key:
			raise ValueError("label_value_mapping không được chứa khóa rỗng.")
		if key in normalized:
			raise ValueError(
				f"label_value_mapping có khóa trùng lặp sau khi chuẩn hóa khoảng trắng: '{key}'."
			)
		if isinstance(target, bool) or not isinstance(target, int) or target not in (0, 1):
			raise ValueError(
				f"Giá trị đích cho nhãn '{key}' phải là 0 hoặc 1, nhận được {target!r}."
			)
		normalized[key] = int(target)

	return normalized


def build_label_parse_sql(
	col_ident: str,
	col_type: str,
	label_value_mapping: Optional[Dict[str, int]] = None,
) -> str:
	"""Builds a DuckDB SQL expression normalizing a raw label column to BIGINT (0, 1, or NULL)."""
	validated = validate_label_value_mapping(label_value_mapping)
	t_up = str(col_type).strip().upper()
	trimmed_sql = f"trim(CAST({col_ident} AS VARCHAR))"
	if t_up in _FLOAT_TYPES:
		blank_cond = f"{col_ident} IS NULL OR isnan({col_ident}) OR {trimmed_sql} = ''"
	else:
		blank_cond = f"{col_ident} IS NULL OR {trimmed_sql} = ''"

	if validated is None:
		if t_up in _BOOL_TYPES:
			return (
				f"CASE WHEN {col_ident} IS NULL THEN NULL "
				f"WHEN {col_ident} THEN CAST(1 AS BIGINT) ELSE CAST(0 AS BIGINT) END"
			)
		num_sql = f"TRY_CAST({trimmed_sql} AS DOUBLE)"
		return (
			f"CASE "
			f"WHEN {blank_cond} THEN NULL "
			f"WHEN {num_sql} IS NOT NULL AND isfinite({num_sql}) AND {num_sql} = 0.0 THEN CAST(0 AS BIGINT) "
			f"WHEN {num_sql} IS NOT NULL AND isfinite({num_sql}) AND {num_sql} = 1.0 THEN CAST(1 AS BIGINT) "
			f"ELSE NULL END"
		)

	when_clauses: List[str] = [f"WHEN {blank_cond} THEN NULL"]
	if t_up in _BOOL_TYPES:
		lower_map = {k.lower(): v for k, v in validated.items()}
		if "true" in lower_map:
			when_clauses.append(
				f"WHEN {col_ident} = TRUE THEN CAST({lower_map['true']} AS BIGINT)"
			)
		elif "1" in validated:
			when_clauses.append(
				f"WHEN {col_ident} = TRUE THEN CAST({validated['1']} AS BIGINT)"
			)
		if "false" in lower_map:
			when_clauses.append(
				f"WHEN {col_ident} = FALSE THEN CAST({lower_map['false']} AS BIGINT)"
			)
		elif "0" in validated:
			when_clauses.append(
				f"WHEN {col_ident} = FALSE THEN CAST({validated['0']} AS BIGINT)"
			)
	else:
		for key, target in validated.items():
			when_clauses.append(
				f"WHEN {trimmed_sql} = {_quote_literal(key)} THEN CAST({target} AS BIGINT)"
			)
		numeric_lookup = _build_numeric_lookup(validated)
		if numeric_lookup:
			num_sql = f"TRY_CAST({trimmed_sql} AS DOUBLE)"
			for num_val, target in numeric_lookup.items():
				when_clauses.append(
					f"WHEN {num_sql} IS NOT NULL AND isfinite({num_sql}) AND {num_sql} = {repr(num_val)} "
					f"THEN CAST({target} AS BIGINT)"
				)

	when_clauses.append("ELSE NULL")
	return "CASE " + " ".join(when_clauses) + " END"


def apply_label_mapping(
	value: Any,
	label_value_mapping: Optional[Dict[str, int]] = None,
) -> Optional[int]:
	"""Normalizes a single raw label scalar to 0, 1, or None using explicit mapping or strict 0/1."""
	validated = validate_label_value_mapping(label_value_mapping)
	if value is None:
		return None
	if type(value).__name__ in ("NAType", "NaTType"):
		return None
	if hasattr(value, "item") and not isinstance(value, (bytes, str)):
		value = value.item()
	if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
		return None

	if validated is None:
		if isinstance(value, bool):
			return 1 if value else 0
		if isinstance(value, int):
			return value if value in (0, 1) else None
		if isinstance(value, float):
			if value == 0.0:
				return 0
			if value == 1.0:
				return 1
			return None
		text = str(value).strip()
		if not text:
			return None
		num = _parse_finite_float(text)
		if num == 0.0:
			return 0
		if num == 1.0:
			return 1
		return None

	if isinstance(value, bool):
		lower_map = {k.lower(): v for k, v in validated.items()}
		if value:
			if "true" in lower_map:
				return lower_map["true"]
			if "1" in validated:
				return validated["1"]
		else:
			if "false" in lower_map:
				return lower_map["false"]
			if "0" in validated:
				return validated["0"]
		return None

	text = str(value).strip()
	if not text:
		return None
	if text in validated:
		return validated[text]
	num = _parse_finite_float(text)
	if num is not None:
		numeric_lookup = _build_numeric_lookup(validated)
		if num in numeric_lookup:
			return numeric_lookup[num]
	return None


__all__ = [
	"apply_label_mapping",
	"build_label_parse_sql",
	"validate_label_value_mapping",
]
