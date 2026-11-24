import { apiClient } from './client';
import type { ApiResponse } from '../types';
import type {
	BlacklistEntry,
	BulkBlacklistResult,
	BulkCaseIntakeResult,
	Case,
	CaseAction,
	CaseKpis,
	CasePage,
	EdgeTransactionsResult,
	EntityType,
	NetworkExpandResult,
	NetworkHubsResult,
	NetworkSubgraph,
	RuleDraft,
	RuleFeedback,
	Workbench,
} from '../types/investigation';

async function unwrap<Result>(request: Promise<ApiResponse<Result>>): Promise<Result> {
	const response = await request;
	if (!response.success || response.data == null) {
		throw new Error(response.error || 'Yêu cầu điều tra thất bại');
	}
	return response.data;
}

export const investigationApi = {
	list: (projectId: string, filters: Record<string, unknown>) => unwrap(apiClient.get<CasePage>('/v1/cases', { project_id: projectId, ...filters })),
	kpis: (projectId: string) => unwrap(apiClient.get<CaseKpis>('/v1/cases/kpis', { project_id: projectId })),
	workbench: (projectId: string, caseId: string, days: 30 | 90) => unwrap(apiClient.get<Workbench>(`/v1/cases/${caseId}/workbench`, { project_id: projectId, days })),
	action: (projectId: string, caseId: string, action: string, payload: CaseAction) => unwrap(apiClient.post<{ case: Case }>(`/v1/cases/${caseId}/${action}`, payload, { project_id: projectId })),
	note: (projectId: string, caseId: string, note: string) => unwrap(apiClient.post<boolean>(`/v1/cases/${caseId}/notes`, { note }, { project_id: projectId })),
	draft: (projectId: string, caseId: string) => unwrap(apiClient.get<RuleDraft>(`/v1/cases/${caseId}/rule-draft`, { project_id: projectId })),
	feedback: (projectId: string) => unwrap(apiClient.get<RuleFeedback[]>('/v1/cases/rule-feedback', { project_id: projectId })),
	blacklist: (projectId: string) => unwrap(apiClient.get<BlacklistEntry[]>('/v1/blacklist', { project_id: projectId })),
	addBlacklist: (projectId: string, entityType: EntityType, value: string, reason: string) => unwrap(apiClient.post<BlacklistEntry>('/v1/blacklist', { project_id: projectId, entity_type: entityType, entity_value: value, reason })),
	removeBlacklist: (projectId: string, entryId: string, reason: string) => unwrap(apiClient.post<BlacklistEntry>(`/v1/blacklist/${entryId}/remove`, { reason }, { project_id: projectId })),
	bulkBlacklist: (
		projectId: string,
		entities: { entity_type: EntityType; entity_value: string }[],
		reason: string,
		sourceCaseId?: string | null
	) =>
		unwrap(
			apiClient.post<BulkBlacklistResult>('/v1/blacklist/bulk', {
				project_id: projectId,
				entities,
				reason,
				source_case_id: sourceCaseId || null,
			})
		),
	bulkCaseIntake: (
		projectId: string,
		items: { detection_job_id: string; event_id: string }[],
		analystNotes?: string
	) =>
		unwrap(
			apiClient.post<BulkCaseIntakeResult>('/v1/cases/bulk-intake', {
				project_id: projectId,
				items,
				analyst_notes: analystNotes || null,
			})
		),
	networkHubs: (projectId: string, days = 90, limit = 20, caseId?: string | null) =>
		unwrap(
			apiClient.get<NetworkHubsResult>('/v1/network/hubs', {
				project_id: projectId,
				days,
				limit,
				...(caseId ? { case_id: caseId } : {}),
			})
		),
	networkSubgraph: (
		projectId: string,
		params: {
			seedType: EntityType;
			seedValue: string;
			hops: 1 | 2;
			days: number;
			entityTypes?: EntityType[];
			hideSuperNodes?: boolean;
			caseId?: string | null;
		}
	) =>
		unwrap(
			apiClient.get<NetworkSubgraph>('/v1/network/subgraph', {
				project_id: projectId,
				seed_type: params.seedType,
				seed_value: params.seedValue,
				hops: params.hops,
				days: params.days,
				...(params.entityTypes && params.entityTypes.length > 0 ? { entity_types: params.entityTypes } : {}),
				hide_super_nodes: Boolean(params.hideSuperNodes),
				...(params.caseId ? { case_id: params.caseId } : {}),
			})
		),
	networkExpand: (payload: {
		project_id: string;
		entity_type: EntityType;
		entity_value: string;
		existing_node_ids: string[];
		days: number;
		entity_types?: EntityType[];
		hide_super_nodes?: boolean;
		case_id?: string | null;
	}) => unwrap(apiClient.post<NetworkExpandResult>('/v1/network/expand', payload)),
	networkEdgeTransactions: (
		projectId: string,
		params: {
			userId: string;
			entityType: EntityType;
			entityValue: string;
			days: number;
			limit?: number;
			caseId?: string | null;
		}
	) =>
		unwrap(
			apiClient.get<EdgeTransactionsResult>('/v1/network/edge-transactions', {
				project_id: projectId,
				user_id: params.userId,
				entity_type: params.entityType,
				entity_value: params.entityValue,
				days: params.days,
				limit: params.limit ?? 100,
				...(params.caseId ? { case_id: params.caseId } : {}),
			})
		),
};