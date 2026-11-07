export interface ReportScopeFilter {
	detectionJobId?: string;
	dateFrom?: string;
	dateTo?: string;
	useDatasetFallback?: boolean;
}

export interface ExecutiveKpis {
	gross_scanned_volume: number;
	gross_scanned_count: number;
	amount_at_risk: number;
	flagged_tx_count: number;
	flagged_rate: number;
	reject_count: number;
	review_count: number;
	confirmed_fraud_loss_prevented: number;
	confirmed_fraud_count: number;
	false_positive_friction_volume: number;
	false_positive_count: number;
	insult_rate: number;
	volume_insult_rate: number;
	verified_precision: number | null;
	alert_to_fraud_ratio: number | null;
	alert_to_fraud_label: string;
	case_resolution_rate: number;
	total_cases: number;
	resolved_cases: number;
	open_cases: number;
	in_progress_cases: number;
	pending_customer_cases: number;
	critical_high_backlog: number;
	label_source: 'VERIFIED_WITH_DATASET_FALLBACK' | 'VERIFIED_ONLY';
	has_dataset_labels: boolean;
}

export interface FunnelStage {
	stage: string;
	label: string;
	tx_count: number;
	amount: number;
	conversion_rate: number;
	reject_count?: number;
	review_count?: number;
	confirmed_fraud_count?: number;
	confirmed_fraud_amount?: number;
	false_positive_count?: number;
	false_positive_amount?: number;
	pending_count?: number;
	pending_amount?: number;
}

export interface FinancialTrendPoint {
	job_id: string;
	job_name: string;
	created_at: string;
	scanned_count: number;
	scanned_amount: number;
	flagged_count: number;
	confirmed_fraud_amount: number;
	false_positive_amount: number;
	pending_review_amount: number;
	fraud_rate: number;
}

export interface StatusBreakdownItem {
	status: string;
	label: string;
	count: number;
	amount: number;
}

export interface PriorityBreakdownItem {
	priority: string;
	open_count: number;
	in_progress_count: number;
	resolved_fraud_count: number;
	resolved_legitimate_count: number;
	total_count: number;
	total_amount: number;
}

export interface AvailableJobItem {
	job_id: string;
	job_name: string;
	model_version_id: string | null;
	total_records: number;
	fraud_records: number;
	score_threshold: number;
	created_at: string;
}

export interface ExecutiveOverviewData {
	kpis: ExecutiveKpis;
	funnel: FunnelStage[];
	financial_trends: FinancialTrendPoint[];
	queue_breakdown: {
		by_status: StatusBreakdownItem[];
		by_priority: PriorityBreakdownItem[];
	};
	available_jobs: AvailableJobItem[];
}

export interface AttributionSegment {
	segment: 'AI_EXCLUSIVE' | 'CONSENSUS_OVERLAP' | 'RULE_EXCLUSIVE';
	label: string;
	fraud_count: number;
	count_pct: number;
	fraud_amount: number;
	amount_pct: number;
}

export interface AttributionSummary {
	total_caught_fraud_count: number;
	total_caught_fraud_amount: number;
	ai_exclusive_catch_rate: number;
	rule_exclusive_catch_rate: number;
	consensus_overlap_rate: number;
	segments: AttributionSegment[];
}

export interface RuleLeaderboardRow {
	rule_id: string;
	rule_code: string;
	rule_name: string;
	status: string;
	action: string;
	version_number: number;
	total_hits: number;
	verified_cases: number;
	verified_tp: number;
	verified_fp: number;
	pending_cases: number;
	fraud_value_caught: number;
	false_positive_value: number;
	hit_rate: number;
	verified_precision: number | null;
	verified_fpr: number | null;
	policy_health_tag: 'HIGH_VALUE' | 'NOISY' | 'BALANCED' | 'UNVERIFIED';
}

export interface ScoreCalibrationBin {
	bin: string;
	lower: number;
	upper: number;
	total_count: number;
	confirmed_fraud_count: number;
	false_positive_count: number;
	unverified_count: number;
	fraud_amount: number;
	false_positive_amount: number;
}

export interface ThresholdSimulationPoint {
	threshold: number;
	review_queue_volume: number;
	hybrid_queue_volume: number;
	caught_fraud_count: number;
	caught_fraud_amount: number;
	false_positive_count: number;
	false_positive_amount: number;
	estimated_recall: number;
	estimated_precision: number;
	fp_reduction_pct: number;
}

export interface EffectivenessAnalysisData {
	attribution: AttributionSummary;
	rule_leaderboard: RuleLeaderboardRow[];
	score_calibration: ScoreCalibrationBin[];
	threshold_simulator: {
		total_known_fraud_count: number;
		baseline_fp_count: number;
		curve: ThresholdSimulationPoint[];
	};
	label_source: string;
}

export interface TypologyBreakdownItem {
	code: string;
	label: string;
	case_count: number;
	total_amount: number;
	pct: number;
}

export interface HourlyRiskItem {
	hour: number;
	label: string;
	total_tx_count: number;
	flagged_tx_count: number;
	confirmed_fraud_count: number;
	total_amount: number;
	at_risk_amount: number;
	fraud_rate: number;
	is_peak_risk: boolean;
}

export interface AmountBracketItem {
	bracket_id: string;
	label: string;
	total_count: number;
	flagged_count: number;
	confirmed_fraud_count: number;
	false_positive_count: number;
	total_amount: number;
	amount_at_risk: number;
	confirmed_fraud_amount: number;
	flag_rate: number;
}

export interface FlaggedSubjectItem {
	user_id: string;
	total_tx_count: number;
	flagged_tx_count: number;
	confirmed_fraud_count: number;
	false_positive_count: number;
	amount_at_risk: number;
	confirmed_fraud_amount: number;
	max_model_score: number;
	is_blacklisted: boolean;
}

export interface WatchlistSummary {
	active_blacklist_count: number;
	removed_blacklist_count: number;
	by_entity_type: {
		entity_type: string;
		active_count: number;
		removed_count: number;
	}[];
	recent_active_entries: {
		blacklist_id: string;
		entity_type: string;
		entity_value: string;
		reason: string;
		created_by: string;
		created_at: string;
		source_case_id: string | null;
	}[];
}

export interface TypologiesPatternsData {
	typology_breakdown: TypologyBreakdownItem[];
	fp_reason_breakdown: TypologyBreakdownItem[];
	hourly_distribution: HourlyRiskItem[];
	amount_brackets: AmountBracketItem[];
	top_flagged_subjects: FlaggedSubjectItem[];
	watchlist_summary: WatchlistSummary;
	label_source: string;
}

export interface SarDossierData {
	report_type: 'SAR_DOSSIER';
	report_id: string;
	generated_at: string;
	project_id: string;
	project_name: string;
	prepared_by: string;
	reviewer_notes: string;
	section_1_identification: {
		case_id: string;
		case_code: string;
		subject_user_id: string;
		priority: string;
		priority_score: number;
		status: string;
		verdict: string;
		verified_label: number | null;
		detected_at: string;
		resolved_at: string | null;
		assigned_to: string;
		resolved_by: string;
		detection_job_id: string | null;
		model_version_id: string | null;
	};
	section_2_financial_summary: {
		primary_event_id: string;
		primary_tx_timestamp: string;
		primary_amount: number;
		final_action: string;
		channel: string;
		merchant_category: string;
		country: string;
		subject_flagged_tx_count: number;
		total_subject_exposure: number;
		confirmed_fraud_loss_prevented: number;
		transactions: {
			case_id: string;
			case_code: string;
			event_id: string;
			tx_timestamp: string;
			amount: number;
			final_action: string;
			model_score: number | null;
			status: string;
			channel: string;
			merchant_category: string;
			country: string;
		}[];
	};
	section_3_detection_evidence: {
		model_version_id: string | null;
		model_score: number | null;
		priority_score: number;
		violated_rules: {
			rule_code: string;
			rule_name: string;
			action: string;
			version_number: number;
			trigger_reason: string;
			matched_clauses: string[];
		}[];
		top_feature_contributions: {
			feature_name: string;
			feature_value: unknown;
			shap_value: number;
			direction: string;
		}[];
		attributes_snapshot: Record<string, unknown>;
	};
	section_4_narrative_and_typology: {
		fraud_typology_code: string;
		fraud_typology_label: string;
		automated_technical_narrative: string;
		analyst_resolution_summary: string;
		reviewer_notes: string;
	};
	section_5_mitigation_and_audit: {
		is_subject_blacklisted: boolean;
		blacklisted_entities: {
			blacklist_id: string;
			entity_type: string;
			entity_value: string;
			status: string;
			reason: string;
			created_by: string;
			created_at: string;
		}[];
		audit_trail: {
			log_id: string;
			action: string;
			actor: string;
			note: string;
			details: Record<string, unknown>;
			created_at: string;
		}[];
	};
}

export interface ExecutiveAuditReportData {
	report_type: 'EXECUTIVE_AUDIT_REPORT';
	report_id: string;
	generated_at: string;
	project_id: string;
	project_name: string;
	prepared_by: string;
	reviewer_notes: string;
	section_1_financial_kpis: ExecutiveKpis;
	section_2_operations_funnel: {
		funnel: FunnelStage[];
		queue_breakdown: ExecutiveOverviewData['queue_breakdown'];
		financial_trends: FinancialTrendPoint[];
	};
	section_3_policy_and_model_effectiveness: {
		attribution: AttributionSummary;
		rule_leaderboard: RuleLeaderboardRow[];
	};
	section_4_typologies_and_patterns: {
		typology_breakdown: TypologyBreakdownItem[];
		fp_reason_breakdown: TypologyBreakdownItem[];
		peak_risk_hours: HourlyRiskItem[];
		amount_brackets: AmountBracketItem[];
	};
	section_5_watchlist_and_governance: {
		top_flagged_subjects: FlaggedSubjectItem[];
		watchlist_summary: WatchlistSummary;
	};
}
