export type CaseStatus = 'OPEN' | 'IN_PROGRESS' | 'PENDING_CUSTOMER' | 'RESOLVED_FRAUD' | 'RESOLVED_LEGITIMATE';
export type CasePriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type EntityType = 'USER_ID' | 'CARD_ID' | 'DEVICE_ID' | 'IP_ADDRESS' | 'MERCHANT_ID';

export interface Case {
	case_id: string;
	case_code: string;
	project_id: string;
	event_id: string;
	user_id: string;
	tx_timestamp: string;
	amount: number;
	model_score: number | null;
	final_action: 'REVIEW' | 'REJECT';
	dataset_artifact_id: string;
	detection_job_id: string | null;
	model_version_id: string | null;
	triggered_rules: { rule_id: string; rule_version_id: string; rule_code: string; version_number: number; rule_name: string; action: string; trigger_reason: string; matched_clauses: string[] }[];
	triggered_rule_codes: string[];
	feature_contributions: { feature_name: string; feature_value: unknown; contribution: number }[];
	attributes: Record<string, unknown>;
	status: CaseStatus;
	priority: CasePriority;
	priority_score: number;
	assigned_to: string | null;
	resolution_reason: string | null;
	resolution_summary: string | null;
	resolved_by: string | null;
	resolved_at: string | null;
	verified_label: 0 | 1 | null;
	version: number;
	created_at: string;
	updated_at: string;
}

export interface CaseKpis {
	open: number;
	in_progress: number;
	pending_customer: number;
	critical: number;
	resolved: number;
	confirmed_fraud_ratio: number | null;
}

export interface CasePage { items: Case[]; total: number; page: number; size: number; }

export interface Workbench {
	case: Case;
	subject_status: 'ACTIVE' | 'BLOCKED';
	related_cases: Case[];
	related_total: number;
	profile: {
		available: boolean;
		message?: string;
		cold_start?: boolean;
		source?: 'USER' | 'POPULATION';
		history_count?: number;
		avg_amount?: number | null;
		max_amount?: number | null;
		transactions_per_day?: number | null;
		common_hours_utc?: number[];
		comparison: { field: string; current: unknown; baseline: unknown; is_anomalous: boolean }[];
		timeline: { event_id: string; timestamp: string; amount: number; is_current: boolean }[];
		timeline_truncated?: boolean;
	};
	audit_logs: { log_id: string; action: string; actor: string; note: string | null; details: Record<string, unknown>; created_at: string }[];
}

export interface BlacklistEntry {
	blacklist_id: string;
	entity_type: EntityType;
	entity_value: string;
	status: 'ACTIVE' | 'REMOVED';
	reason: string;
	source_case_id: string | null;
	created_at: string;
	created_by: string;
	removed_at: string | null;
	removed_by: string | null;
}

export interface RuleFeedback {
	rule_id: string;
	rule_version_id: string;
	rule_code: string;
	version_number: number;
	cases_triggered: number;
	tp: number;
	fp: number;
	pending: number;
	verified_false_positive_ratio: number | null;
}

export interface RuleDraft {
	project_id?: string;
	condition: Record<string, unknown> | null;
	action: 'REVIEW';
	status: 'DRAFT';
	dataset_artifact_id: string;
	source_case_id: string;
	name: string;
	message: string;
}

export interface CaseAction {
	expected_version: number;
	summary?: string;
	assignee?: string;
	verdict?: 'FRAUD' | 'LEGITIMATE';
	reason?: string;
	block_entities?: { entity_type: EntityType; entity_value: string }[];
}