from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from usfds_core.domain.entities.enums import ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import SystemColumn


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
			non_positive_mask = (amount_numeric <= 0) | amount_numeric.isna()
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
			warnings=warnings,
			critical_errors=critical_errors,
			recommendations=recommendations,
		)


__all__ = [
	"ColumnQualityMetric",
	"DataQualityReport",
	"DataQualityValidationService",
]
