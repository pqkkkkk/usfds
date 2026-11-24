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
	dataset_artifact_id: string | null;
	detection_job_id: string | null;
	model_version_id: string | null;
	triggered_rules: { rule_id: string; rule_version_id: string; rule_code: string; version_number: number; rule_name: string; action: string; trigger_reason: string; matched_clauses: string[] }[];
	triggered_rule_codes: string[];
	feature_contributions: { feature_name: string; feature_value: unknown; contribution: number }[];
	attributes: Record<string, unknown>;
	status: CaseStatus;
	priority: CasePriority;
	priority_score: number;
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
	dataset_artifact_id: string | null;
	detection_job_id?: string | null;
	source_case_id: string;
	name: string;
	message: string;
}

export interface CaseAction {
	expected_version: number;
	summary?: string;
	verdict?: 'FRAUD' | 'LEGITIMATE';
	reason?: string;
	block_entities?: { entity_type: EntityType; entity_value: string }[];
}

export type NetworkRiskStatus = 'CRITICAL' | 'WARNING' | 'NORMAL';
export type NetworkPatternType = 'DEVICE_IP_CARD_HUB' | 'MERCHANT_RING';

export interface NetworkNode {
	id: string;
	entity_type: EntityType;
	entity_value: string;
	label: string;
	tx_count: number;
	flagged_tx_count: number;
	total_amount: number;
	max_model_score: number;
	distinct_users: number;
	merchant_category: string | null;
	risk_status: NetworkRiskStatus;
	is_blacklisted: boolean;
	open_case_count: number;
	resolved_fraud_count: number;
	case_ids: string[];
	is_super_node: boolean;
	is_seed: boolean;
	pattern_tags: string[];
}

export interface NetworkEdge {
	id: string;
	source: string;
	target: string;
	rel_type: string;
	entity_type: EntityType;
	entity_value: string;
	user_id: string;
	tx_count: number;
	flagged_tx_count: number;
	total_amount: number;
	max_model_score: number;
	first_tx_at: string;
	last_tx_at: string;
}

export interface NetworkPattern {
	pattern_type: NetworkPatternType;
	node_id: string;
	entity_type: EntityType;
	entity_value: string;
	distinct_users: number;
	flagged_users: number;
	tx_count: number;
	flagged_tx_count: number;
	flagged_rate: number;
	summary: string;
	involved_node_ids: string[];
}

export interface NetworkHub {
	id: string;
	entity_type: EntityType;
	entity_value: string;
	label: string;
	distinct_users: number;
	tx_count: number;
	flagged_tx_count: number;
	flagged_users: number;
	max_model_score: number;
	risk_status: NetworkRiskStatus;
	is_blacklisted: boolean;
	is_super_node: boolean;
	pattern_type: NetworkPatternType | null;
	merchant_category: string | null;
}

export interface NetworkHubsResult {
	available: boolean;
	message: string | null;
	days: number;
	hubs: NetworkHub[];
	total_nodes: number;
	total_edges: number;
}

export interface NetworkSubgraph {
	available: boolean;
	message: string | null;
	seed_node_id: string;
	hops: number;
	days: number;
	nodes: NetworkNode[];
	edges: NetworkEdge[];
	patterns: NetworkPattern[];
	stats: {
		node_count: number;
		edge_count: number;
		pattern_count: number;
		flagged_node_count: number;
	};
	truncated_neighbors: boolean;
	total_neighbors: number;
	canvas_limit_reached: boolean;
	notice: string | null;
}

export interface NetworkExpandResult {
	available: boolean;
	message: string | null;
	center_node_id: string;
	added_nodes: NetworkNode[];
	added_edges: NetworkEdge[];
	patterns: NetworkPattern[];
	truncated_neighbors: boolean;
	total_neighbors: number;
	canvas_limit_reached: boolean;
	notice: string | null;
}

export interface EdgeTransaction {
	event_id: string;
	job_id: string;
	user_id: string;
	tx_timestamp: string;
	amount: number;
	model_score: number;
	final_action: string;
	is_flagged: boolean;
	rule_codes: string[];
	case_id: string | null;
}

export interface EdgeTransactionsResult {
	available: boolean;
	message: string | null;
	user_id: string;
	entity_type: EntityType;
	entity_value: string;
	total: number;
	transactions: EdgeTransaction[];
}

export interface BulkBlacklistResult {
	added: BlacklistEntry[];
	skipped: { entity_type: EntityType; entity_value: string; reason: string }[];
	added_count: number;
	skipped_count: number;
}

export interface BulkCaseIntakeResult {
	created_case_ids: string[];
	accepted_count: number;
	skipped_event_ids: string[];
}