/**
 * Detection Jobs, Hybrid Inference Results, and Investigation Case types
 */

export type DetectionJobStatusType = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
export type DetectionDecisionAction = 'REJECT' | 'REVIEW' | 'ALLOW';
export type DetectionActionFilter = 'ALL' | 'FLAGGED' | 'REJECT' | 'REVIEW' | 'ALLOW';
export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type InvestigationStatus =
	| 'PENDING'
	| 'IN_PROGRESS'
	| 'CONFIRMED_FRAUD'
	| 'FALSE_POSITIVE'
	| 'RESOLVED'
	| 'NEW'
	| 'UNDER_REVIEW'
	| 'DISMISSED';

export interface RuleTriggerBreakdownItem {
	rule_id: string;
	rule_code: string;
	rule_name: string;
	version_number: number;
	action: DetectionDecisionAction;
	hit_count: number;
	hit_rate: number;
}

export interface ScoreDistributionBin {
	bin?: string;
	lower?: number;
	upper?: number;
	count: number;
	flagged_count?: number;
}

export interface DetectionSummaryMetrics {
	input_source_type?: 'ARTIFACT' | 'FILE';
	target_artifact_id?: string;
	dataset_id?: string;
	dataset_name?: string;
	input_file_name?: string;
	original_file_path?: string;
	input_label?: string;
	model_id?: string;
	model_version_id?: string;
	model_name?: string;
	model_display_name?: string;
	semver?: string;
	artifact_uri?: string;
	default_threshold?: number;
	score_threshold?: number;
	use_rules?: boolean;
	active_rules_count?: number;
	has_model?: boolean;
	reject_count?: number;
	review_count?: number;
	allow_count?: number;
	flagged_count?: number;
	flagged_rate?: number;
	amount_at_risk?: number;
	rule_trigger_breakdown?: RuleTriggerBreakdownItem[];
	score_distribution?: ScoreDistributionBin[];
}

export interface StartDetectionJobRequest {
	project_id: string;
	target_artifact_id?: string | null;
	input_file_path?: string | null;
	model_version_id?: string | null;
	use_rules?: boolean;
	score_threshold?: number | null;
	job_name?: string | null;
	created_by?: string | null;
}

export interface DetectionJobResponse {
	job_id: string;
	project_id: string;
	deployment_id?: string | null;
	target_artifact_id?: string | null;
	model_version_id?: string | null;
	job_name?: string | null;
	input_path: string;
	output_path?: string | null;
	score_threshold: number;
	use_rules: boolean;
	status: DetectionJobStatusType;
	total_records?: number | null;
	fraud_records?: number | null;
	fraud_rate?: number | null;
	summary_metrics?: DetectionSummaryMetrics | null;
	execution_time_seconds?: number | null;
	error_message?: string | null;
	created_by?: string | null;
	created_at: string;
	started_at?: string | null;
	completed_at?: string | null;
}

export interface TriggeredRuleDetail {
	rule_id: string;
	rule_version_id: string;
	version_number: number;
	rule_code: string;
	rule_name: string;
	action: DetectionDecisionAction;
	matched_clauses: string[];
}

export interface DetectionTransactionRecord {
	row_index: number;
	event_id: string;
	user_id: string;
	timestamp: string;
	amount: number;
	model_score: number;
	triggered_rules: string[];
	triggered_rule_details: TriggeredRuleDetail[];
	rule_action: DetectionDecisionAction;
	final_action: DetectionDecisionAction;
	is_flagged: boolean;
	case_id?: string | null;
	features: Record<string, unknown>;
}

export interface DetectionJobResultsResponse {
	job: DetectionJobResponse;
	total_filtered: number;
	transactions: DetectionTransactionRecord[];
	summary_metrics: DetectionSummaryMetrics;
}

export interface SendToInvestigationRequest {
	event_ids: string[];
	analyst_notes?: string | null;
}

export interface InvestigationCaseMetadata {
	job_id?: string;
	job_name?: string;
	raw_event_id?: string;
	user_id?: string;
	timestamp?: string;
	amount?: number;
	model_score?: number;
	final_action?: DetectionDecisionAction;
	rule_action?: DetectionDecisionAction;
	triggered_rules?: string[];
	triggered_rule_details?: TriggeredRuleDetail[];
	features?: Record<string, unknown>;
}

export interface InvestigationCaseResponse {
	case_id: string;
	project_id: string;
	event_id: number;
	assigned_to?: string | null;
	status: InvestigationStatus;
	risk_level: AlertSeverity;
	fraud_probability: number;
	analyst_notes?: string | null;
	action_taken?: string | null;
	sar_narrative?: string | null;
	metadata: InvestigationCaseMetadata;
	created_at: string;
	updated_at: string;
	resolved_at?: string | null;
}

export interface DetectionJob {
	id: string;
	projectId: string;
	name: string;
	type: 'BATCH' | 'STREAM';
	status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
	totalTransactions: number;
	flaggedCount: number;
	runtimeSeconds?: number;
	createdAt: string;
}

export interface FraudAlert {
	id: string;
	transactionId: string;
	timestamp: string;
	amount: number;
	currency: string;
	cardBin?: string;
	merchantCategory?: string;
	riskScore: number;
	severity: AlertSeverity;
	triggeredRules: string[];
	mlModelScore: number;
	status: InvestigationStatus;
	assignee?: string;
}
