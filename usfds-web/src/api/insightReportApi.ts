import { apiClient } from './client';
import { storageApi, type PresignedDownloadUrlResponse } from './storageApi';
import type {
	ApiResponse,
	EffectivenessAnalysisData,
	ExecutiveAuditReportData,
	ExecutiveOverviewData,
	ReportScopeFilter,
	SarDossierData,
	TypologiesPatternsData,
} from '@/types';

async function unwrap<Result>(request: Promise<ApiResponse<Result>>): Promise<Result> {
	const response = await request;
	if (!response.success || response.data == null) {
		throw new Error(response.error || 'Yêu cầu phân tích & báo cáo thất bại');
	}
	return response.data;
}

function toScopeParams(projectId: string, scope?: ReportScopeFilter): Record<string, unknown> {
	const labelSource =
		scope?.useDatasetFallback ?? true ? 'VERIFIED_WITH_DATASET_FALLBACK' : 'VERIFIED_ONLY';
	return {
		project_id: projectId,
		job_ids: scope?.detectionJobId || undefined,
		date_from: scope?.dateFrom ? `${scope.dateFrom}T00:00:00Z` : undefined,
		date_to: scope?.dateTo ? `${scope.dateTo}T23:59:59Z` : undefined,
		label_source: labelSource,
	};
}

export const insightReportApi = {
	getOverview: (projectId: string, scope?: ReportScopeFilter) =>
		unwrap(apiClient.get<ExecutiveOverviewData>('/v1/reports/overview', toScopeParams(projectId, scope))),

	getEffectiveness: (projectId: string, scope?: ReportScopeFilter) =>
		unwrap(apiClient.get<EffectivenessAnalysisData>('/v1/reports/effectiveness', toScopeParams(projectId, scope))),

	getPatterns: (projectId: string, scope?: ReportScopeFilter) =>
		unwrap(apiClient.get<TypologiesPatternsData>('/v1/reports/patterns', toScopeParams(projectId, scope))),

	getSarDossier: (projectId: string, caseId: string, preparedBy = 'local-analyst', reviewerNotes = '') =>
		unwrap(
			apiClient.get<SarDossierData>(`/v1/reports/sar/${caseId}`, {
				project_id: projectId,
				prepared_by: preparedBy,
				reviewer_notes: reviewerNotes,
			})
		),

	getExecutiveSummary: (projectId: string, scope?: ReportScopeFilter, preparedBy = 'local-analyst', reviewerNotes = '') =>
		unwrap(
			apiClient.get<ExecutiveAuditReportData>('/v1/reports/executive-summary', {
				...toScopeParams(projectId, scope),
				prepared_by: preparedBy,
				reviewer_notes: reviewerNotes,
			})
		),

	getExportUrl: (params: {
		projectId: string;
		template: 'SAR_DOSSIER' | 'EXECUTIVE_AUDIT_REPORT';
		format: 'md' | 'json' | 'csv' | 'html';
		caseId?: string;
		scope?: ReportScopeFilter;
		preparedBy?: string;
		reviewerNotes?: string;
	}): string => {
		const baseUrl = apiClient.getRawAxios().defaults.baseURL || '/api';
		const search = new URLSearchParams();
		search.set('project_id', params.projectId);
		search.set('report_type', params.template === 'SAR_DOSSIER' ? 'sar' : 'executive');
		search.set('file_format', params.format);
		if (params.caseId) {
			search.set('case_id', params.caseId);
		}
		if (params.scope?.detectionJobId) {
			search.set('job_ids', params.scope.detectionJobId);
		}
		if (params.scope?.dateFrom) {
			search.set('date_from', `${params.scope.dateFrom}T00:00:00Z`);
		}
		if (params.scope?.dateTo) {
			search.set('date_to', `${params.scope.dateTo}T23:59:59Z`);
		}
		search.set(
			'label_source',
			params.scope?.useDatasetFallback ?? true ? 'VERIFIED_WITH_DATASET_FALLBACK' : 'VERIFIED_ONLY'
		);
		if (params.preparedBy) {
			search.set('prepared_by', params.preparedBy);
		}
		if (params.reviewerNotes) {
			search.set('reviewer_notes', params.reviewerNotes);
		}
		return `${baseUrl.replace(/\/$/, '')}/v1/reports/export?${search.toString()}`;
	},

	exportReport: async (params: {
		projectId: string;
		template: 'SAR_DOSSIER' | 'EXECUTIVE_AUDIT_REPORT';
		format: 'md' | 'json' | 'csv' | 'html';
		caseId?: string;
		scope?: ReportScopeFilter;
		preparedBy?: string;
		reviewerNotes?: string;
	}): Promise<void> => {
		const useS3Presigned = await storageApi.isS3StorageBackend();
		if (useS3Presigned && params.format !== 'html') {
			const res = await apiClient.get<PresignedDownloadUrlResponse>(
				'/v1/reports/export',
				{
					...toScopeParams(params.projectId, params.scope),
					report_type: params.template === 'SAR_DOSSIER' ? 'sar' : 'executive',
					file_format: params.format,
					case_id: params.caseId,
					prepared_by: params.preparedBy,
					reviewer_notes: params.reviewerNotes,
					presigned: true,
				}
			);
			if (res.success && res.data?.download_url) {
				storageApi.triggerBrowserDownload(
					res.data.download_url,
					res.data.filename
				);
				return;
			}
		}
		const url = insightReportApi.getExportUrl(params);
		window.open(url, '_blank', 'noopener,noreferrer');
	},
};
