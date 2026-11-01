import { apiClient } from './client';
import type { ApiResponse } from '../types';
import type { BlacklistEntry, Case, CaseAction, CaseKpis, CasePage, EntityType, RuleDraft, RuleFeedback, Workbench } from '../types/investigation';

async function unwrap<Result>(request: Promise<ApiResponse<Result>>): Promise<Result> {
	const response = await request;
	if (!response.success || response.data == null) {
		throw new Error(response.error || 'Investigation request failed');
	}
	return response.data;
}

export const investigationApi = {
	list: (projectId: string, filters: Record<string, unknown>) => unwrap(apiClient.get<CasePage>('/v1/cases', { project_id: projectId, ...filters })),
	kpis: (projectId: string) => unwrap(apiClient.get<CaseKpis>('/v1/cases/kpis', { project_id: projectId })),
	workbench: (projectId: string, caseId: string, days: 30 | 90) => unwrap(apiClient.get<Workbench>(`/v1/cases/${caseId}/workbench`, { project_id: projectId, days })),
	action: (projectId: string, caseId: string, action: string, payload: CaseAction) => unwrap(apiClient.post<{ case: Case; related_assignees: string[] }>(`/v1/cases/${caseId}/${action}`, payload, { project_id: projectId })),
	note: (projectId: string, caseId: string, note: string) => unwrap(apiClient.post<boolean>(`/v1/cases/${caseId}/notes`, { note }, { project_id: projectId })),
	draft: (projectId: string, caseId: string) => unwrap(apiClient.get<RuleDraft>(`/v1/cases/${caseId}/rule-draft`, { project_id: projectId })),
	feedback: (projectId: string) => unwrap(apiClient.get<RuleFeedback[]>('/v1/cases/rule-feedback', { project_id: projectId })),
	blacklist: (projectId: string) => unwrap(apiClient.get<BlacklistEntry[]>('/v1/blacklist', { project_id: projectId })),
	addBlacklist: (projectId: string, entityType: EntityType, value: string, reason: string) => unwrap(apiClient.post<BlacklistEntry>('/v1/blacklist', { project_id: projectId, entity_type: entityType, entity_value: value, reason })),
	removeBlacklist: (projectId: string, entryId: string, reason: string) => unwrap(apiClient.post<BlacklistEntry>(`/v1/blacklist/${entryId}/remove`, { reason }, { project_id: projectId })),
};