/**
 * Rule Engine and Business Logic Types
 * Matching FastAPI backend (api/v1/rules) & Core JsonLogic Engine
 */

export type RuleStatus = 'ACTIVE' | 'INACTIVE' | 'DRAFT';

export type RuleAction = 'ALLOW' | 'REVIEW' | 'REJECT';

export type LogicalCombinator = 'ALL' | 'ANY' | 'NONE';

export type ComparisonOperator = 
  | '>'
  | '>='
  | '<'
  | '<='
  | '=='
  | '!='
  | 'in'
  | 'not_in'
  | 'regex';

export interface RuleClause {
  id: string;
  field: string;
  operator: ComparisonOperator;
  value: any;
  unit?: string;
}

export interface RuleGroup {
  id: string;
  combinator: LogicalCombinator; // ALL = AND, ANY = OR, NONE = NOT
  clauses: (RuleClause | RuleGroup)[];
}

export interface RuleVersionResponse {
  rule_version_id: string;
  rule_id: string;
  version_number: number;
  condition: Record<string, any>;
  action: RuleAction;
  change_summary?: string;
  created_by?: string;
  created_at: string;
}

export interface RuleResponse {
  rule_id: string;
  project_id: string;
  rule_code: string;
  name: string;
  description: string;
  status: RuleStatus;
  current_version_id?: string;
  current_version?: RuleVersionResponse;
  created_by?: string;
  created_at: string;
  updated_at: string;
  hit_count_24h?: number;
}

export interface CreateRuleRequest {
  project_id: string;
  rule_code: string;
  name: string;
  description?: string;
  condition: Record<string, any>;
  action: RuleAction;
  status?: RuleStatus;
  change_summary?: string;
  created_by?: string;
}

export interface UpdateRuleRequest {
  name?: string;
  description?: string;
  condition?: Record<string, any>;
  action?: RuleAction;
  change_summary?: string;
  created_by?: string;
}

export interface SetRuleStatusRequest {
  status: RuleStatus;
}

export interface EvaluateRuleRequest {
	transaction_id: string;
	raw_features?: Record<string, any>;
	mapped_features?: Record<string, any>;
	enriched_features?: Record<string, any>;
}

export interface EvaluateRulesRequest {
	project_id: string;
	transaction_id: string;
	raw_features?: Record<string, any>;
	mapped_features?: Record<string, any>;
	enriched_features?: Record<string, any>;
}

export interface RuleExecutionResultResponse {
	rule_id: string;
	rule_version_id: string;
	version_number: number;
	rule_code: string;
	rule_name: string;
	is_triggered: boolean;
	action: RuleAction;
	trigger_reason: string;
	execution_time_ms: number;
}

export interface BacktestRuleRequest {
	project_id: string;
	dataset_artifact_id: string;
	rule_id?: string;
	version_id?: string;
	condition?: Record<string, any>;
	action?: RuleAction;
	rule_code?: string;
	rule_name?: string;
	target_column?: string;
	amount_column?: string;
	max_samples?: number;
}

export interface RuleBacktestSampleHit {
	event_id: string;
	timestamp: string;
	amount: number;
	user_id: string;
	ground_truth?: number | null;
	matched_clauses: string[];
	features: Record<string, any>;
}

export interface RuleBacktestResultResponse {
	rule_id?: string | null;
	rule_version_id?: string | null;
	version_number: number;
	rule_code: string;
	rule_name: string;
	action: RuleAction;
	dataset_artifact_id: string;
	total_transactions: number;
	total_hits: number;
	hit_rate: number;
	has_ground_truth: boolean;
	target_column?: string | null;
	tp: number;
	fp: number;
	tn: number;
	fn: number;
	precision: number;
	recall: number;
	fpr: number;
	fraud_amount_caught: number;
	execution_time_ms: number;
	avg_execution_time_ms: number;
	sample_hits: RuleBacktestSampleHit[];
}

export interface AvailableFeatureField {
  key: string;
  label: string;
  category: 'transaction' | 'device' | 'velocity' | 'merchant' | 'user';
  dataType: 'number' | 'string' | 'boolean' | 'array';
  unit?: string;
  defaultOperator: ComparisonOperator;
  sampleValues?: any[];
}
