from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from usfds_core.domain.entities.enums import ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import SystemColumn
from usfds_core.services.data_management.duckdb_io import (
	create_utc_bounded_duckdb_connection,
	duckdb_type_to_physical_dtype,
	is_duckdb_datetime_type,
	is_duckdb_numeric_type,
	is_duckdb_string_type,
	quote_ident,
	quote_literal,
	register_file_view,
)

_FLOAT_TYPES = {"FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "REAL"}


@dataclass
class ColumnQualityMetric:
	name: str
	dtype: str
	null_count: int
	null_percentage: float
	unique_count: int
	sample_values: List[Any] = field(default_factory=list)


@dataclass
class DataQualityReport:
	"""Detailed quality validation report for MAPPED stage datasets."""
	quality_score: float
	rating: str
	validation_status: ValidationStatus
	total_rows: int
	total_columns: int
	duplicate_rows_count: int
	duplicate_rows_ratio: float
	duplicate_event_ids_count: int
	duplicate_event_ids_ratio: float
	non_positive_amount_count: int
	non_positive_amount_ratio: float
	future_timestamp_count: int
	future_timestamp_ratio: float
	amount_outliers_count: int
	amount_outliers_ratio: float
	amount_q999: Optional[float] = None
	column_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
	sample_records: List[Dict[str, Any]] = field(default_factory=list)
	warnings: List[str] = field(default_factory=list)
	critical_errors: List[str] = field(default_factory=list)
	recommendations: List[str] = field(default_factory=list)

	def to_dict(self) -> Dict[str, Any]:
		result = asdict(self)
		result["validation_status"] = (
			self.validation_status.value
			if hasattr(self.validation_status, "value")
			else str(self.validation_status)
		)
		return result


def _serialize_scalar(val: Any) -> Any:
	if val is None:
		return None
	if hasattr(val, "isoformat"):
		return val.isoformat()
	if isinstance(val, bool):
		return int(val)
	if isinstance(val, (np.integer, int)):
		return int(val)
	if isinstance(val, (np.floating, float)):
		fval = float(val)
		return None if (math.isnan(fval) or math.isinf(fval)) else fval
	if isinstance(val, Decimal):
		return float(val)
	return str(val)


def _serialize_record_value(val: Any) -> Any:
	if val is None:
		return None
	if hasattr(val, "isoformat"):
		return val.isoformat()
	if isinstance(val, bool):
		return val
	if isinstance(val, (np.integer, int)):
		return int(val)
	if isinstance(val, (np.floating, float)):
		fval = float(val)
		return None if (math.isnan(fval) or math.isinf(fval)) else fval
	if isinstance(val, Decimal):
		return float(val)
	if isinstance(val, (list, dict)):
		return val
	return str(val)


class DataQualityValidationService:
	"""Service implementing: View data validation report & Data Quality Score (0-100)."""

	MANDATORY_COLUMNS = {
		SystemColumn.EVENT_ID.value,
		SystemColumn.TIMESTAMP.value,
		SystemColumn.AMOUNT.value,
		SystemColumn.USER_ID.value,
		SystemColumn.LABEL.value,
	}

	def validate(self, df: pd.DataFrame) -> DataQualityReport:
		"""Evaluates tabular data against financial fraud validation rules and computes a 0-100 Quality Score."""
		total_rows = len(df)
		total_columns = len(df.columns)

		if total_rows == 0:
			return DataQualityReport(
				quality_score=0.0,
				rating="POOR",
				validation_status=ValidationStatus.FAILED,
				total_rows=0,
				total_columns=total_columns,
				duplicate_rows_count=0,
				duplicate_rows_ratio=0.0,
				duplicate_event_ids_count=0,
				duplicate_event_ids_ratio=0.0,
				non_positive_amount_count=0,
				non_positive_amount_ratio=0.0,
				future_timestamp_count=0,
				future_timestamp_ratio=0.0,
				amount_outliers_count=0,
				amount_outliers_ratio=0.0,
				critical_errors=["Dataset contains 0 rows."],
			)

		warnings: List[str] = []
		critical_errors: List[str] = []
		recommendations: List[str] = []
		column_metrics: Dict[str, Dict[str, Any]] = {}

		# 1. Missing Values & Column Profiling
		mandatory_null_penalties = 0.0
		optional_null_penalties = 0.0
		optional_col_count = 0

		for col in df.columns:
			series = df[col]
			# Account for NaN and empty strings
			if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
				null_mask = series.isna() | (series.astype(str).str.strip() == "")
			else:
				null_mask = series.isna()

			null_count = int(null_mask.sum())
			null_pct = round((null_count / total_rows) * 100.0, 2)
			unique_count = int(series.nunique(dropna=True))

			# Sample top values
			samples = series.dropna().head(5).tolist()
			samples_serializable = [
				x.isoformat() if hasattr(x, "isoformat") else (
					int(x) if isinstance(x, (np.integer, int)) else (
						float(x) if isinstance(x, (np.floating, float)) else str(x)
					)
				)
				for x in samples
			]

			column_metrics[str(col)] = {
				"name": str(col),
				"dtype": str(series.dtype),
				"null_count": null_count,
				"null_percentage": null_pct,
				"unique_count": unique_count,
				"sample_values": samples_serializable,
			}

			# Business rule checks for missing values
			if str(col) in self.MANDATORY_COLUMNS:
				if null_pct > 50.0:
					critical_errors.append(
						f"Trường bắt buộc '{col}' có tỷ lệ missing {null_pct}% (vượt quá 50%). "
						"Tập dữ liệu có chất lượng kém nghiêm trọng, khuyến nghị không sử dụng trực tiếp để huấn luyện mô hình."
					)
				elif null_pct > 0.0:
					warnings.append(f"Trường bắt buộc '{col}' có {null_count} giá trị thiếu ({null_pct}%).")
					mandatory_null_penalties += null_pct * 0.5
				if str(col) == SystemColumn.LABEL.value and unique_count == 1:
					warnings.append(
						"Cột nhãn 'label' chỉ có 1 lớp giá trị phân biệt sau ánh xạ; "
						"cần ít nhất 2 lớp (0 và 1) để huấn luyện mô hình phân loại."
					)
			else:
				optional_col_count += 1
				if null_pct > 0.0:
					optional_null_penalties += null_pct
					if pd.api.types.is_numeric_dtype(series):
						recommendations.append(f"Cột '{col}' có {null_pct}% missing: Khuyến nghị dùng phép bù trung vị (Median Imputation).")
					else:
						recommendations.append(f"Cột '{col}' có {null_pct}% missing: Khuyến nghị gán giá trị mặc định 'missing' hoặc Mode Imputation.")

		missing_penalty = min(30.0, mandatory_null_penalties + (
			(optional_null_penalties / max(1, optional_col_count)) * 0.3
		))

		# 2. Duplicate Checks
		duplicate_rows_count = int(df.duplicated().sum())
		duplicate_rows_ratio = round(duplicate_rows_count / total_rows, 4)

		event_id_col = SystemColumn.EVENT_ID.value
		duplicate_event_ids_count = 0
		duplicate_event_ids_ratio = 0.0
		if event_id_col in df.columns:
			duplicate_event_ids_count = int(df[event_id_col].duplicated().sum())
			duplicate_event_ids_ratio = round(duplicate_event_ids_count / total_rows, 4)

		if duplicate_event_ids_count > 0:
			warnings.append(
				f"Phát hiện {duplicate_event_ids_count} bản ghi ({duplicate_event_ids_ratio * 100:.2f}%) trùng lặp mã giao dịch '{event_id_col}'."
			)
			recommendations.append(f"Nên loại bỏ các bản ghi trùng lặp '{event_id_col}' để tránh sai lệch mô hình.")

		if duplicate_rows_count > 0 and duplicate_rows_count != duplicate_event_ids_count:
			warnings.append(f"Phát hiện {duplicate_rows_count} dòng trùng lặp hoàn toàn ({duplicate_rows_ratio * 100:.2f}%).")

		duplicate_penalty = min(25.0, (duplicate_event_ids_ratio * 100.0 * 2.0) + (duplicate_rows_ratio * 100.0 * 0.5))

		# 3. Business Logic Checks: Amount <= 0 and Future Timestamp
		amount_col = SystemColumn.AMOUNT.value
		non_positive_amount_count = 0
		non_positive_amount_ratio = 0.0
		if amount_col in df.columns:
			amount_numeric = pd.to_numeric(df[amount_col], errors="coerce")
			non_positive_amount_count = int((amount_numeric <= 0).sum())
			non_positive_amount_ratio = round(non_positive_amount_count / total_rows, 4)
			if non_positive_amount_count > 0:
				warnings.append(
					f"Có {non_positive_amount_count} giao dịch ({non_positive_amount_ratio * 100:.2f}%) có số tiền <= 0."
				)
				recommendations.append("Kiểm tra và lọc các giao dịch có số tiền <= 0 (hoàn tiền hoặc lỗi ghi nhận).")

		timestamp_col = SystemColumn.TIMESTAMP.value
		future_timestamp_count = 0
		future_timestamp_ratio = 0.0
		if timestamp_col in df.columns:
			try:
				ts_series = pd.to_datetime(df[timestamp_col], utc=True, errors="coerce")
				now_utc = pd.Timestamp.now(tz="UTC")
				future_mask = ts_series > now_utc
				future_timestamp_count = int(future_mask.sum())
				future_timestamp_ratio = round(future_timestamp_count / total_rows, 4)
				if future_timestamp_count > 0:
					warnings.append(
						f"Có {future_timestamp_count} giao dịch ({future_timestamp_ratio * 100:.2f}%) có mốc thời gian lớn hơn thời gian hiện tại."
					)
					recommendations.append("Kiểm tra múi giờ của dữ liệu nguồn để tránh lỗi mốc thời gian tương lai.")
			except Exception:
				pass

		business_logic_penalty = min(25.0, (non_positive_amount_ratio * 100.0 * 2.0) + (future_timestamp_ratio * 100.0 * 2.0))

		# 4. Outlier Detection on Amount
		amount_outliers_count = 0
		amount_outliers_ratio = 0.0
		amount_q999 = None
		if amount_col in df.columns:
			amount_numeric = pd.to_numeric(df[amount_col], errors="coerce").dropna()
			if len(amount_numeric) > 0:
				amount_q999 = float(amount_numeric.quantile(0.999))
				mean_amt = float(amount_numeric.mean())
				std_amt = float(amount_numeric.std()) or 1.0
				z_scores = (amount_numeric - mean_amt).abs() / std_amt
				outlier_mask = (amount_numeric > amount_q999) | (z_scores > 3.0)
				amount_outliers_count = int(outlier_mask.sum())
				amount_outliers_ratio = round(amount_outliers_count / total_rows, 4)
				if amount_outliers_ratio > 0.01:
					warnings.append(
						f"Phát hiện {amount_outliers_count} giao dịch ngoại lai ({amount_outliers_ratio * 100:.2f}%) vượt ngưỡng phân vị 99.9% ({amount_q999:.2f}) hoặc Z-score > 3."
					)
					recommendations.append("Áp dụng RobustScaler hoặc Outlier Clipping ở bước tiền xử lý để hạn chế ảnh hưởng của giá trị ngoại lai.")

		outlier_penalty = min(10.0, amount_outliers_ratio * 100.0 * 0.5)

		# 5. Calculate Score & Status
		total_penalties = missing_penalty + duplicate_penalty + business_logic_penalty + outlier_penalty
		score = round(max(0.0, min(100.0, 100.0 - total_penalties)), 2)

		if len(critical_errors) > 0:
			status = ValidationStatus.FAILED
			rating = "POOR"
		elif score >= 80.0:
			status = ValidationStatus.PASSED
			rating = "GOOD"
		elif score >= 60.0:
			status = ValidationStatus.WARNING
			rating = "FAIR"
		else:
			status = ValidationStatus.FAILED
			rating = "POOR"

		# Sample records for preview (first 10 rows)
		sample_records: List[Dict[str, Any]] = []
		try:
			sample_records = json.loads(df.head(10).to_json(orient="records", date_format="iso"))
		except Exception:
			pass

		return DataQualityReport(
			quality_score=score,
			rating=rating,
			validation_status=status,
			total_rows=total_rows,
			total_columns=total_columns,
			duplicate_rows_count=duplicate_rows_count,
			duplicate_rows_ratio=duplicate_rows_ratio,
			duplicate_event_ids_count=duplicate_event_ids_count,
			duplicate_event_ids_ratio=duplicate_event_ids_ratio,
			non_positive_amount_count=non_positive_amount_count,
			non_positive_amount_ratio=non_positive_amount_ratio,
			future_timestamp_count=future_timestamp_count,
			future_timestamp_ratio=future_timestamp_ratio,
			amount_outliers_count=amount_outliers_count,
			amount_outliers_ratio=amount_outliers_ratio,
			amount_q999=amount_q999,
			column_metrics=column_metrics,
			sample_records=sample_records,
			warnings=warnings,
			critical_errors=critical_errors,
			recommendations=recommendations,
		)

	def validate_duckdb(self, conn: Any, view_name: str = "mapped_src") -> DataQualityReport:
		"""Evaluates a registered DuckDB view against fraud validation rules without pandas."""
		v = quote_ident(view_name)
		described = conn.execute(f"DESCRIBE SELECT * FROM {v}").fetchall()
		columns = [str(row[0]) for row in described]
		col_types = {str(row[0]): str(row[1]) for row in described}
		total_columns = len(columns)
		total_rows = int(conn.execute(f"SELECT COUNT(*) FROM {v}").fetchone()[0])

		if total_rows == 0:
			return DataQualityReport(
				quality_score=0.0,
				rating="POOR",
				validation_status=ValidationStatus.FAILED,
				total_rows=0,
				total_columns=total_columns,
				duplicate_rows_count=0,
				duplicate_rows_ratio=0.0,
				duplicate_event_ids_count=0,
				duplicate_event_ids_ratio=0.0,
				non_positive_amount_count=0,
				non_positive_amount_ratio=0.0,
				future_timestamp_count=0,
				future_timestamp_ratio=0.0,
				amount_outliers_count=0,
				amount_outliers_ratio=0.0,
				critical_errors=["Dataset contains 0 rows."],
			)

		warnings: List[str] = []
		critical_errors: List[str] = []
		recommendations: List[str] = []
		column_metrics: Dict[str, Dict[str, Any]] = {}

		# 1. Missing Values & Column Profiling in batched SQL passes
		null_counts: Dict[str, int] = {}
		unique_counts: Dict[str, int] = {}
		batch_size = 40
		for idx in range(0, total_columns, batch_size):
			batch = columns[idx : idx + batch_size]
			exprs: List[str] = []
			for col in batch:
				c = quote_ident(col)
				t_up = col_types[col].strip().upper()
				if is_duckdb_string_type(t_up):
					null_expr = f"SUM(CASE WHEN {c} IS NULL OR trim(CAST({c} AS VARCHAR)) = '' THEN 1 ELSE 0 END)"
					uniq_expr = f"COUNT(DISTINCT {c})"
				elif t_up in _FLOAT_TYPES:
					null_expr = f"SUM(CASE WHEN {c} IS NULL OR isnan({c}) THEN 1 ELSE 0 END)"
					uniq_expr = f"COUNT(DISTINCT CASE WHEN {c} IS NULL OR isnan({c}) THEN NULL ELSE {c} END)"
				else:
					null_expr = f"(COUNT(*) - COUNT({c}))"
					uniq_expr = f"COUNT(DISTINCT {c})"
				exprs.append(null_expr)
				exprs.append(uniq_expr)
			row = conn.execute(f"SELECT {', '.join(exprs)} FROM {v}").fetchone()
			for c_idx, col in enumerate(batch):
				null_counts[col] = int(row[c_idx * 2] or 0) if row else 0
				unique_counts[col] = int(row[c_idx * 2 + 1] or 0) if row else 0

		mandatory_null_penalties = 0.0
		optional_null_penalties = 0.0
		optional_col_count = 0

		for col in columns:
			c = quote_ident(col)
			t_up = col_types[col].strip().upper()
			null_count = null_counts.get(col, 0)
			null_pct = round((null_count / total_rows) * 100.0, 2)
			unique_count = unique_counts.get(col, 0)

			if t_up in _FLOAT_TYPES:
				not_null_cond = f"{c} IS NOT NULL AND NOT isnan({c})"
			else:
				not_null_cond = f"{c} IS NOT NULL"
			sample_rows = conn.execute(f"SELECT {c} FROM {v} WHERE {not_null_cond} LIMIT 5").fetchall()
			samples_serializable = [_serialize_scalar(r[0]) for r in sample_rows]

			column_metrics[col] = {
				"name": col,
				"dtype": duckdb_type_to_physical_dtype(col_types[col]),
				"null_count": null_count,
				"null_percentage": null_pct,
				"unique_count": unique_count,
				"sample_values": samples_serializable,
			}

			if col in self.MANDATORY_COLUMNS:
				if null_pct > 50.0:
					critical_errors.append(
						f"Trường bắt buộc '{col}' có tỷ lệ missing {null_pct}% (vượt quá 50%). "
						"Tập dữ liệu có chất lượng kém nghiêm trọng, khuyến nghị không sử dụng trực tiếp để huấn luyện mô hình."
					)
				elif null_pct > 0.0:
					warnings.append(f"Trường bắt buộc '{col}' có {null_count} giá trị thiếu ({null_pct}%).")
					mandatory_null_penalties += null_pct * 0.5
				if str(col) == SystemColumn.LABEL.value and unique_count == 1:
					warnings.append(
						"Cột nhãn 'label' chỉ có 1 lớp giá trị phân biệt sau ánh xạ; "
						"cần ít nhất 2 lớp (0 và 1) để huấn luyện mô hình phân loại."
					)
			else:
				optional_col_count += 1
				if null_pct > 0.0:
					optional_null_penalties += null_pct
					if is_duckdb_numeric_type(col_types[col]):
						recommendations.append(f"Cột '{col}' có {null_pct}% missing: Khuyến nghị dùng phép bù trung vị (Median Imputation).")
					else:
						recommendations.append(f"Cột '{col}' có {null_pct}% missing: Khuyến nghị gán giá trị mặc định 'missing' hoặc Mode Imputation.")

		missing_penalty = min(30.0, mandatory_null_penalties + (
			(optional_null_penalties / max(1, optional_col_count)) * 0.3
		))

		# 2. Duplicate Checks (NULLs treated as equal via SELECT DISTINCT, matching pandas duplicated())
		distinct_rows = int(conn.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {v})").fetchone()[0])
		duplicate_rows_count = max(0, total_rows - distinct_rows)
		duplicate_rows_ratio = round(duplicate_rows_count / total_rows, 4)

		event_id_col = SystemColumn.EVENT_ID.value
		duplicate_event_ids_count = 0
		duplicate_event_ids_ratio = 0.0
		if event_id_col in col_types:
			ev_ident = quote_ident(event_id_col)
			distinct_ev = int(
				conn.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT {ev_ident} FROM {v})").fetchone()[0]
			)
			duplicate_event_ids_count = max(0, total_rows - distinct_ev)
			duplicate_event_ids_ratio = round(duplicate_event_ids_count / total_rows, 4)

		if duplicate_event_ids_count > 0:
			warnings.append(
				f"Phát hiện {duplicate_event_ids_count} bản ghi ({duplicate_event_ids_ratio * 100:.2f}%) trùng lặp mã giao dịch '{event_id_col}'."
			)
			recommendations.append(f"Nên loại bỏ các bản ghi trùng lặp '{event_id_col}' để tránh sai lệch mô hình.")

		if duplicate_rows_count > 0 and duplicate_rows_count != duplicate_event_ids_count:
			warnings.append(f"Phát hiện {duplicate_rows_count} dòng trùng lặp hoàn toàn ({duplicate_rows_ratio * 100:.2f}%).")

		duplicate_penalty = min(25.0, (duplicate_event_ids_ratio * 100.0 * 2.0) + (duplicate_rows_ratio * 100.0 * 0.5))

		# 3. Business Logic Checks: Amount <= 0 and Future Timestamp
		amount_col = SystemColumn.AMOUNT.value
		non_positive_amount_count = 0
		non_positive_amount_ratio = 0.0
		amt_expr: Optional[str] = None
		if amount_col in col_types:
			amt_ident = quote_ident(amount_col)
			amt_expr = f"TRY_CAST({amt_ident} AS DOUBLE)"
			non_pos_row = conn.execute(
				f"SELECT SUM(CASE WHEN {amt_expr} IS NOT NULL AND NOT isnan({amt_expr}) AND {amt_expr} <= 0 THEN 1 ELSE 0 END) "
				f"FROM {v}"
			).fetchone()
			non_positive_amount_count = int(non_pos_row[0] or 0) if non_pos_row else 0
			non_positive_amount_ratio = round(non_positive_amount_count / total_rows, 4)
			if non_positive_amount_count > 0:
				warnings.append(
					f"Có {non_positive_amount_count} giao dịch ({non_positive_amount_ratio * 100:.2f}%) có số tiền <= 0."
				)
				recommendations.append("Kiểm tra và lọc các giao dịch có số tiền <= 0 (hoàn tiền hoặc lỗi ghi nhận).")

		timestamp_col = SystemColumn.TIMESTAMP.value
		future_timestamp_count = 0
		future_timestamp_ratio = 0.0
		if timestamp_col in col_types:
			ts_ident = quote_ident(timestamp_col)
			now_utc_lit = quote_literal(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f+00:00"))
			if is_duckdb_datetime_type(col_types[timestamp_col]):
				ts_utc_expr = f"CAST({ts_ident} AS TIMESTAMPTZ)"
			else:
				ts_utc_expr = (
					f"COALESCE(TRY_CAST({ts_ident} AS TIMESTAMPTZ), "
					f"CAST(TRY_CAST({ts_ident} AS TIMESTAMP) AS TIMESTAMPTZ))"
				)
			try:
				fut_row = conn.execute(
					f"SELECT SUM(CASE WHEN {ts_utc_expr} > CAST({now_utc_lit} AS TIMESTAMPTZ) THEN 1 ELSE 0 END) FROM {v}"
				).fetchone()
				future_timestamp_count = int(fut_row[0] or 0) if fut_row else 0
				future_timestamp_ratio = round(future_timestamp_count / total_rows, 4)
				if future_timestamp_count > 0:
					warnings.append(
						f"Có {future_timestamp_count} giao dịch ({future_timestamp_ratio * 100:.2f}%) có mốc thời gian lớn hơn thời gian hiện tại."
					)
					recommendations.append("Kiểm tra múi giờ của dữ liệu nguồn để tránh lỗi mốc thời gian tương lai.")
			except Exception:
				pass

		business_logic_penalty = min(25.0, (non_positive_amount_ratio * 100.0 * 2.0) + (future_timestamp_ratio * 100.0 * 2.0))

		# 4. Outlier Detection on Amount
		amount_outliers_count = 0
		amount_outliers_ratio = 0.0
		amount_q999: Optional[float] = None
		if amt_expr is not None:
			stats_row = conn.execute(
				f"SELECT COUNT({amt_expr}), quantile_cont({amt_expr}, 0.999), AVG({amt_expr}), STDDEV_SAMP({amt_expr}) "
				f"FROM {v} WHERE {amt_expr} IS NOT NULL AND NOT isnan({amt_expr})"
			).fetchone()
			valid_amt_count = int(stats_row[0] or 0) if stats_row else 0
			if valid_amt_count > 0:
				amount_q999 = float(stats_row[1])
				mean_amt = float(stats_row[2])
				raw_std = stats_row[3]
				std_amt = float(raw_std) if raw_std is not None else float("nan")

				if not math.isnan(std_amt) and std_amt > 0.0:
					out_cond = f"({amt_expr} > ? OR abs({amt_expr} - ?) / ? > 3.0)"
					out_params: List[Any] = [amount_q999, mean_amt, std_amt]
				else:
					out_cond = f"({amt_expr} > ?)"
					out_params = [amount_q999]

				out_row = conn.execute(
					f"SELECT SUM(CASE WHEN {amt_expr} IS NOT NULL AND NOT isnan({amt_expr}) AND {out_cond} THEN 1 ELSE 0 END) "
					f"FROM {v}",
					out_params,
				).fetchone()
				amount_outliers_count = int(out_row[0] or 0) if out_row else 0
				amount_outliers_ratio = round(amount_outliers_count / total_rows, 4)
				if amount_outliers_ratio > 0.01:
					warnings.append(
						f"Phát hiện {amount_outliers_count} giao dịch ngoại lai ({amount_outliers_ratio * 100:.2f}%) vượt ngưỡng phân vị 99.9% ({amount_q999:.2f}) hoặc Z-score > 3."
					)
					recommendations.append("Áp dụng RobustScaler hoặc Outlier Clipping ở bước tiền xử lý để hạn chế ảnh hưởng của giá trị ngoại lai.")

		outlier_penalty = min(10.0, amount_outliers_ratio * 100.0 * 0.5)

		# 5. Calculate Score & Status
		total_penalties = missing_penalty + duplicate_penalty + business_logic_penalty + outlier_penalty
		score = round(max(0.0, min(100.0, 100.0 - total_penalties)), 2)

		if len(critical_errors) > 0:
			status = ValidationStatus.FAILED
			rating = "POOR"
		elif score >= 80.0:
			status = ValidationStatus.PASSED
			rating = "GOOD"
		elif score >= 60.0:
			status = ValidationStatus.WARNING
			rating = "FAIR"
		else:
			status = ValidationStatus.FAILED
			rating = "POOR"

		# Sample records for preview (first 10 rows)
		sample_records: List[Dict[str, Any]] = []
		try:
			cur = conn.execute(f"SELECT * FROM {v} LIMIT 10")
			col_names = [str(d[0]) for d in cur.description]
			for row in cur.fetchall():
				sample_records.append(
					{col_names[i]: _serialize_record_value(row[i]) for i in range(len(col_names))}
				)
		except Exception:
			pass

		return DataQualityReport(
			quality_score=score,
			rating=rating,
			validation_status=status,
			total_rows=total_rows,
			total_columns=total_columns,
			duplicate_rows_count=duplicate_rows_count,
			duplicate_rows_ratio=duplicate_rows_ratio,
			duplicate_event_ids_count=duplicate_event_ids_count,
			duplicate_event_ids_ratio=duplicate_event_ids_ratio,
			non_positive_amount_count=non_positive_amount_count,
			non_positive_amount_ratio=non_positive_amount_ratio,
			future_timestamp_count=future_timestamp_count,
			future_timestamp_ratio=future_timestamp_ratio,
			amount_outliers_count=amount_outliers_count,
			amount_outliers_ratio=amount_outliers_ratio,
			amount_q999=amount_q999,
			column_metrics=column_metrics,
			sample_records=sample_records,
			warnings=warnings,
			critical_errors=critical_errors,
			recommendations=recommendations,
		)

	def validate_file(self, file_path: Union[str, Path]) -> DataQualityReport:
		"""Evaluates a tabular file on disk using a bounded DuckDB connection."""
		conn = create_utc_bounded_duckdb_connection()
		try:
			register_file_view(conn, file_path, view_name="mapped_src", source_hint=str(file_path))
			return self.validate_duckdb(conn, view_name="mapped_src")
		finally:
			conn.close()


__all__ = [
	"ColumnQualityMetric",
	"DataQualityReport",
	"DataQualityValidationService",
]
