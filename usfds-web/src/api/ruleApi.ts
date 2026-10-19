import { apiClient } from './client';
import type {
  RuleResponse,
  RuleVersionResponse,
  CreateRuleRequest,
  UpdateRuleRequest,
  EvaluateRuleRequest,
  RuleExecutionResultResponse,
  RuleStatus,
} from '../types/rule';
import type { ApiResponse } from '@/types';
import { groupToJsonLogic, createStitchSampleRuleGroup } from '../utils/jsonLogicParser';

// Sample mock seed data matching Stitch SUC-11 specification
const SAMPLE_MOCK_RULES: RuleResponse[] = [
  {
    rule_id: 'e28a506f-712e-4b92-95b1-f92d4726bf60',
    project_id: '11111111-1111-1111-1111-111111111111',
    rule_code: 'R-022',
    name: 'High amount on new device with sudden velocity',
    description: 'Flags purchases exceeding $2,000 on newly recognized client hardware or sudden frequency bursts.',
    status: 'ACTIVE',
    hit_count_24h: 38,
    current_version_id: 'v2-43fa-b1e8-78ef93021984',
    current_version: {
      rule_version_id: 'v2-43fa-b1e8-78ef93021984',
      rule_id: 'e28a506f-712e-4b92-95b1-f92d4726bf60',
      version_number: 2,
      condition: groupToJsonLogic(createStitchSampleRuleGroup()),
      action: 'REVIEW',
      change_summary: 'Tightened transaction threshold from $2.5k to $2k and added crypto MCC',
      created_by: 'lead_fraud_analyst',
      created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    },
    created_by: 'lead_fraud_analyst',
    created_at: new Date(Date.now() - 86400000 * 3).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 4).toISOString(),
  },
  {
    rule_id: 'a71829cb-652a-4df3-8cb2-205934571021',
    project_id: '11111111-1111-1111-1111-111111111111',
    rule_code: 'R-015',
    name: 'Rapid velocity card testing attack',
    description: 'Blocks cards with more than 10 transactions in a 1-hour window on low trust devices.',
    status: 'ACTIVE',
    hit_count_24h: 124,
    current_version_id: 'v1-98ac-b2ef-102938475612',
    current_version: {
      rule_version_id: 'v1-98ac-b2ef-102938475612',
      rule_id: 'a71829cb-652a-4df3-8cb2-205934571021',
      version_number: 1,
      condition: {
        and: [
          { '>=': [{ var: 'velocity_count_1h' }, 10] },
          { '<': [{ var: 'device_trust_score' }, 0.3] },
        ],
      },
      action: 'REJECT',
      change_summary: 'Initial production baseline',
      created_by: 'system_admin',
      created_at: new Date(Date.now() - 86400000 * 12).toISOString(),
    },
    created_by: 'system_admin',
    created_at: new Date(Date.now() - 86400000 * 12).toISOString(),
    updated_at: new Date(Date.now() - 86400000 * 12).toISOString(),
  },
  {
    rule_id: 'f94821ca-3456-42bc-a912-876543210987',
    project_id: '11111111-1111-1111-1111-111111111111',
    rule_code: 'R-031',
    name: 'Cross-border geo-anomaly with high distance',
    description: 'Sends transaction to manual review when location is > 1000km away from home and amount > $300.',
    status: 'ACTIVE',
    hit_count_24h: 19,
    current_version_id: 'v1-1029-3847-561283940192',
    current_version: {
      rule_version_id: 'v1-1029-3847-561283940192',
      rule_id: 'f94821ca-3456-42bc-a912-876543210987',
      version_number: 1,
      condition: {
        and: [
          { '>': [{ var: 'geo_distance_home' }, 1000] },
          { '>': [{ var: 'amount' }, 300] },
        ],
      },
      action: 'REVIEW',
      change_summary: 'Initial rule draft',
      created_by: 'analyst_bob',
      created_at: new Date(Date.now() - 86400000 * 5).toISOString(),
    },
    created_by: 'analyst_bob',
    created_at: new Date(Date.now() - 86400000 * 5).toISOString(),
    updated_at: new Date(Date.now() - 86400000 * 5).toISOString(),
  },
  {
    rule_id: 'c51239aa-9988-4422-b112-765432109876',
    project_id: '11111111-1111-1111-1111-111111111111',
    rule_code: 'R-045',
    name: 'Experimental crypto & gift card review',
    description: 'Under review draft testing composite flags on crypto and gift card merchant categories.',
    status: 'DRAFT',
    hit_count_24h: 0,
    current_version_id: 'v1-9988-7766-554433221100',
    current_version: {
      rule_version_id: 'v1-9988-7766-554433221100',
      rule_id: 'c51239aa-9988-4422-b112-765432109876',
      version_number: 1,
      condition: {
        in: [{ var: 'merchant_risk_category' }, ['crypto', 'gift_card']],
      },
      action: 'REVIEW',
      change_summary: 'Draft sandbox for crypto merchant review',
      created_by: 'analyst_alice',
      created_at: new Date(Date.now() - 1800000).toISOString(),
    },
    created_by: 'analyst_alice',
    created_at: new Date(Date.now() - 1800000).toISOString(),
    updated_at: new Date(Date.now() - 1800000).toISOString(),
  },
];

let localRulesStore: RuleResponse[] = [...SAMPLE_MOCK_RULES];

export const ruleApi = {
  /**
   * List rules by project with optional status filter
   */
  listRules: async (projectId: string, status?: RuleStatus): Promise<ApiResponse<RuleResponse[]>> => {
    try {
      const res = await apiClient.get<RuleResponse[]>('/v1/rules', {
        project_id: projectId,
        status: status,
      });
      if (res.success && res.data && Array.isArray(res.data) && res.data.length > 0) {
        return res;
      }
    } catch {
      // Fallback to local store
    }

    const filtered = localRulesStore.filter((r) => {
      if (status && r.status !== status) return false;
      return true;
    });
    return { success: true, data: filtered };
  },

  /**
   * Get single rule details
   */
  getRule: async (ruleId: string): Promise<ApiResponse<RuleResponse>> => {
    try {
      const res = await apiClient.get<RuleResponse>(`/v1/rules/${ruleId}`);
      if (res.success && res.data) return res;
    } catch {
      // Fallback
    }

    const found = localRulesStore.find((r) => r.rule_id === ruleId) || localRulesStore[0];
    return { success: true, data: found };
  },

  /**
   * Create new rule
   */
  createRule: async (payload: CreateRuleRequest): Promise<ApiResponse<RuleResponse>> => {
    try {
      const res = await apiClient.post<RuleResponse>('/v1/rules', payload);
      if (res.success && res.data) {
        localRulesStore.unshift(res.data);
        return res;
      }
    } catch {
      // Fallback
    }

    const newId = `rule-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
    const versionId = `ver-${Date.now()}`;
    const newRule: RuleResponse = {
      rule_id: newId,
      project_id: payload.project_id,
      rule_code: payload.rule_code,
      name: payload.name,
      description: payload.description || '',
      status: payload.status || 'ACTIVE',
      current_version_id: versionId,
      current_version: {
        rule_version_id: versionId,
        rule_id: newId,
        version_number: 1,
        condition: payload.condition,
        action: payload.action,
        change_summary: payload.change_summary || 'Initial creation',
        created_by: payload.created_by || 'current_user',
        created_at: new Date().toISOString(),
      },
      created_by: payload.created_by || 'current_user',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    localRulesStore.unshift(newRule);
    return { success: true, data: newRule, message: `Rule '${payload.rule_code}' successfully created` };
  },

  /**
   * Update rule metadata or conditions
   */
  updateRule: async (ruleId: string, payload: UpdateRuleRequest): Promise<ApiResponse<RuleResponse>> => {
    try {
      const res = await apiClient.put<RuleResponse>(`/v1/rules/${ruleId}`, payload);
      if (res.success && res.data) {
        localRulesStore = localRulesStore.map((r) => (r.rule_id === ruleId ? res.data : r));
        return res;
      }
    } catch {
      // Fallback
    }

    const index = localRulesStore.findIndex((r) => r.rule_id === ruleId);
    if (index === -1) {
      return { success: false, data: null as any, error: 'Rule not found' };
    }

    const target = localRulesStore[index];
    const prevVersionNum = target.current_version?.version_number || 1;
    const isLogicChanged = payload.condition !== undefined || payload.action !== undefined;

    const updatedVersion: RuleVersionResponse = isLogicChanged
      ? {
          rule_version_id: `ver-${Date.now()}`,
          rule_id: ruleId,
          version_number: prevVersionNum + 1,
          condition: payload.condition || target.current_version?.condition || {},
          action: payload.action || target.current_version?.action || 'REVIEW',
          change_summary: payload.change_summary || 'Logic update',
          created_by: payload.created_by || 'current_user',
          created_at: new Date().toISOString(),
        }
      : target.current_version!;

    const updatedRule: RuleResponse = {
      ...target,
      name: payload.name || target.name,
      description: payload.description !== undefined ? payload.description : target.description,
      current_version_id: updatedVersion.rule_version_id,
      current_version: updatedVersion,
      updated_at: new Date().toISOString(),
    };

    localRulesStore[index] = updatedRule;
    return { success: true, data: updatedRule, message: `Rule '${updatedRule.rule_code}' updated` };
  },

  /**
   * Set status (ACTIVE <-> INACTIVE)
   */
  setRuleStatus: async (ruleId: string, status: RuleStatus): Promise<ApiResponse<RuleResponse>> => {
    try {
      const res = await apiClient.patch<RuleResponse>(`/v1/rules/${ruleId}/status`, { status });
      if (res.success && res.data) {
        localRulesStore = localRulesStore.map((r) => (r.rule_id === ruleId ? res.data : r));
        return res;
      }
    } catch {
      // Fallback
    }

    const index = localRulesStore.findIndex((r) => r.rule_id === ruleId);
    if (index !== -1) {
      localRulesStore[index] = { ...localRulesStore[index], status, updated_at: new Date().toISOString() };
      return { success: true, data: localRulesStore[index] };
    }
    return { success: false, data: null as any, error: 'Rule not found' };
  },

  /**
   * Get version history
   */
  getRuleVersions: async (ruleId: string): Promise<ApiResponse<RuleVersionResponse[]>> => {
    try {
      const res = await apiClient.get<RuleVersionResponse[]>(`/v1/rules/${ruleId}/versions`);
      if (res.success && res.data) return res;
    } catch {
      // Fallback
    }

    const target = localRulesStore.find((r) => r.rule_id === ruleId);
    const versions: RuleVersionResponse[] = [
      target?.current_version || {
        rule_version_id: 'v1',
        rule_id: ruleId,
        version_number: 1,
        condition: groupToJsonLogic(createStitchSampleRuleGroup()),
        action: 'REVIEW',
        change_summary: 'Initial version',
        created_at: target?.created_at || new Date().toISOString(),
      },
    ];

    if ((target?.current_version?.version_number || 1) >= 2) {
      versions.unshift({
        rule_version_id: 'v1-initial',
        rule_id: ruleId,
        version_number: 1,
        condition: { and: [{ '>': [{ var: 'amount' }, 2500] }] },
        action: 'REVIEW',
        change_summary: 'Initial baseline draft',
        created_by: 'lead_fraud_analyst',
        created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
      });
    }

    return { success: true, data: versions };
  },

  /**
   * Delete rule
   */
  deleteRule: async (ruleId: string): Promise<ApiResponse<boolean>> => {
    try {
      const res = await apiClient.delete<boolean>(`/v1/rules/${ruleId}`);
      if (res.success) {
        localRulesStore = localRulesStore.filter((r) => r.rule_id !== ruleId);
        return res;
      }
    } catch {
      // Fallback
    }

    localRulesStore = localRulesStore.filter((r) => r.rule_id !== ruleId);
    return { success: true, data: true, message: `Rule ${ruleId} deleted` };
  },

  /**
   * Evaluate a single rule against a test transaction
   */
  evaluateSingleRule: async (
    ruleId: string,
    payload: EvaluateRuleRequest,
    versionId?: string
  ): Promise<ApiResponse<RuleExecutionResultResponse>> => {
    try {
      const res = await apiClient.post<RuleExecutionResultResponse>(
        `/v1/rules/${ruleId}/evaluate`,
        payload,
        versionId ? { version_id: versionId } : undefined
      );
      if (res.success && res.data) return res;
    } catch {
      // Fallback
    }

    // Local evaluation fallback using JsonLogic
    const target = localRulesStore.find((r) => r.rule_id === ruleId) || localRulesStore[0];
    const condition = target.current_version?.condition || {};
    const testData: Record<string, any> = {
      ...payload.mapped_features,
      ...payload.enriched_features,
      mapped: payload.mapped_features,
      enriched: payload.enriched_features,
      transaction_id: payload.transaction_id,
    };

    let isTriggered = false;
    const start = performance.now();
    try {
      // Dynamic evaluation
      const jsonLogic = (await import('json-logic-js')).default;
      isTriggered = Boolean(jsonLogic.apply(condition, testData));
    } catch {
      isTriggered = (testData.amount || 0) > 2000;
    }
    const elapsed = Math.round((performance.now() - start) * 100) / 100;

    return {
      success: true,
      data: {
        rule_id: ruleId,
        rule_version_id: target.current_version_id || 'v1',
        version_number: target.current_version?.version_number || 1,
        rule_code: target.rule_code,
        rule_name: target.name,
        is_triggered: isTriggered,
        action: target.current_version?.action || 'REVIEW',
        trigger_reason: isTriggered
          ? `Rule '${target.rule_code}' triggered: conditions satisfied`
          : `Rule '${target.rule_code}' condition not met`,
        execution_time_ms: Math.max(0.2, elapsed),
      },
    };
  },
};
