import { apiClient } from './client';
import type { ApiResponse } from '@/types';
import type {
	BacktestRuleRequest,
	CreateRuleRequest,
	EvaluateRuleRequest,
	EvaluateRulesRequest,
	RuleBacktestResultResponse,
	RuleExecutionResultResponse,
	RuleResponse,
	RuleStatus,
	RuleVersionResponse,
	UpdateRuleRequest,
} from '../types/rule';

export const ruleApi = {
	/**
	 * List rules by project with optional status filter (SUC-18)
	 */
	listRules: async (
		projectId: string,
		status?: RuleStatus
	): Promise<ApiResponse<RuleResponse[]>> => {
		return apiClient.get<RuleResponse[]>('/v1/rules', {
			project_id: projectId,
			...(status ? { status } : {}),
		});
	},

	/**
	 * Get single rule details and current version (SUC-18)
	 */
	getRule: async (ruleId: string): Promise<ApiResponse<RuleResponse>> => {
		return apiClient.get<RuleResponse>(`/v1/rules/${ruleId}`);
	},

	/**
	 * Create new business rule with initial version v1 (SUC-11)
	 */
	createRule: async (payload: CreateRuleRequest): Promise<ApiResponse<RuleResponse>> => {
		return apiClient.post<RuleResponse>('/v1/rules', payload);
	},

	/**
	 * Update rule metadata or conditions (auto-increments RuleVersion if condition/action changed) (SUC-11)
	 */
	updateRule: async (
		ruleId: string,
		payload: UpdateRuleRequest
	): Promise<ApiResponse<RuleResponse>> => {
		return apiClient.put<RuleResponse>(`/v1/rules/${ruleId}`, payload);
	},

	/**
	 * Set rule status (ACTIVE / INACTIVE / DRAFT) (SUC-14)
	 */
	setRuleStatus: async (
		ruleId: string,
		status: RuleStatus
	): Promise<ApiResponse<RuleResponse>> => {
		return apiClient.patch<RuleResponse>(`/v1/rules/${ruleId}/status`, { status });
	},

	/**
	 * Get version history audit trail for a rule (SUC-18)
	 */
	getRuleVersions: async (ruleId: string): Promise<ApiResponse<RuleVersionResponse[]>> => {
		return apiClient.get<RuleVersionResponse[]>(`/v1/rules/${ruleId}/versions`);
	},

	/**
	 * Delete a rule and all its versions (SUC-18)
	 */
	deleteRule: async (ruleId: string): Promise<ApiResponse<boolean>> => {
		return apiClient.delete<boolean>(`/v1/rules/${ruleId}`);
	},

	/**
	 * Evaluate a single rule against a transaction payload (SUC-12)
	 */
	evaluateSingleRule: async (
		ruleId: string,
		payload: EvaluateRuleRequest,
		versionId?: string
	): Promise<ApiResponse<RuleExecutionResultResponse>> => {
		return apiClient.post<RuleExecutionResultResponse>(
			`/v1/rules/${ruleId}/evaluate`,
			payload,
			versionId ? { version_id: versionId } : undefined
		);
	},

	/**
	 * Evaluate all active rules in a project against a transaction payload (SUC-12)
	 */
	evaluateProjectRules: async (
		payload: EvaluateRulesRequest
	): Promise<ApiResponse<RuleExecutionResultResponse[]>> => {
		return apiClient.post<RuleExecutionResultResponse[]>('/v1/rules/evaluate-batch', payload);
	},

	/**
	 * Run historical dry-run/backtest on a DatasetArtifact (SUC-12)
	 */
	backtestRule: async (
		payload: BacktestRuleRequest
	): Promise<ApiResponse<RuleBacktestResultResponse>> => {
		return apiClient.post<RuleBacktestResultResponse>('/v1/rules/backtest', payload);
	},
};
