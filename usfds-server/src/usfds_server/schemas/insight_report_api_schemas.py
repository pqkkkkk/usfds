from typing import Any, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ReportExportQuery(BaseModel):
	project_id: UUID
	report_type: Literal["sar", "executive"] = Field(..., description="Report template type: 'sar' or 'executive'")
	file_format: Literal["md", "json", "csv", "html"] = Field("md", description="Export format")
	case_id: Optional[UUID] = Field(None, description="Required when report_type == 'sar'")
	job_ids: Optional[list[UUID]] = None
	label_source: Literal["VERIFIED_ONLY", "VERIFIED_WITH_DATASET_FALLBACK"] = "VERIFIED_WITH_DATASET_FALLBACK"
	prepared_by: str = "local-analyst"
	reviewer_notes: str = ""


class OverviewResponse(BaseModel):
	kpis: dict[str, Any]
	funnel: list[dict[str, Any]]
	financial_trends: list[dict[str, Any]]
	queue_breakdown: dict[str, Any]
	available_jobs: list[dict[str, Any]]


class EffectivenessResponse(BaseModel):
	attribution: dict[str, Any]
	rule_leaderboard: list[dict[str, Any]]
	score_calibration: list[dict[str, Any]]
	threshold_simulator: dict[str, Any]
	label_source: str


class TypologiesPatternsResponse(BaseModel):
	typology_breakdown: list[dict[str, Any]]
	fp_reason_breakdown: list[dict[str, Any]]
	hourly_distribution: list[dict[str, Any]]
	amount_brackets: list[dict[str, Any]]
	top_flagged_subjects: list[dict[str, Any]]
	watchlist_summary: dict[str, Any]
	label_source: str
