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
  mapped_features: Record<string, any>;
  enriched_features: Record<string, any>;
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

export interface AvailableFeatureField {
  key: string;
  label: string;
  category: 'transaction' | 'device' | 'velocity' | 'merchant' | 'user';
  dataType: 'number' | 'string' | 'boolean' | 'array';
  unit?: string;
  defaultOperator: ComparisonOperator;
  sampleValues?: any[];
}
