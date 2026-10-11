/**
 * Rule Engine and Business Logic types
 */

export type RuleAction = 'APPROVE' | 'REVIEW' | 'CHALLENGE_OTP' | 'DECLINE';

export type RuleOperator = 'EQUALS' | 'NOT_EQUALS' | 'GREATER_THAN' | 'LESS_THAN' | 'IN' | 'CONTAINS';

export interface RuleCondition {
  field: string;
  operator: RuleOperator;
  value: string | number | boolean | (string | number)[];
}

export interface FraudRule {
  id: string;
  projectId: string;
  code: string;
  name: string;
  description: string;
  priority: number;
  conditions: RuleCondition[];
  action: RuleAction;
  riskScoreDelta: number;
  isEnabled: boolean;
  hitCount24h?: number;
  createdAt: string;
  updatedAt: string;
}
