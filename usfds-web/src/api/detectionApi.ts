import { apiClient } from './client';
import { storageApi, type PresignedDownloadUrlResponse } from './storageApi';
import type { ApiResponse } from '@/types';
import type {
	DetectionJobResponse,
	DetectionJobResultsResponse,
	CaseDispatchResult,
	SendToInvestigationRequest,
	StartDetectionJobRequest,
} from '../types/detection';

export const detectionApi = {
	listJobs: async (params: {
		projectId: string;
		status?: string;
	}): Promise<ApiResponse<DetectionJobResponse[]>> => {
		return apiClient.get<DetectionJobResponse[]>('/v1/detection/jobs', {
			project_id: params.projectId,
			status: params.status,
		});
	},

	startJob: async (
		payload: StartDetectionJobRequest
	): Promise<ApiResponse<DetectionJobResponse>> => {
		return apiClient.post<DetectionJobResponse>(
			'/v1/detection/jobs',
			payload,
			undefined,
			{ timeout: 180000 }
		);
	},

	getJob: async (jobId: string): Promise<ApiResponse<DetectionJobResponse>> => {
		return apiClient.get<DetectionJobResponse>(`/v1/detection/jobs/${jobId}`);
	},

	getJobResults: async (params: {
		jobId: string;
		actionFilter?: string;
		ruleCode?: string;
		search?: string;
		minScore?: number;
		maxScore?: number;
		limit?: number;
		offset?: number;
	}): Promise<ApiResponse<DetectionJobResultsResponse>> => {
		return apiClient.get<DetectionJobResultsResponse>(
			`/v1/detection/jobs/${params.jobId}/results`,
			{
				action_filter:
					params.actionFilter && params.actionFilter !== 'ALL'
						? params.actionFilter
						: undefined,
				rule_code: params.ruleCode || undefined,
				search: params.search || undefined,
				min_score: params.minScore,
				max_score: params.maxScore,
				limit: params.limit ?? 200,
				offset: params.offset ?? 0,
			}
		);
	},

	getExportUrl: (params: {
		jobId: string;
		fileFormat?: 'csv' | 'parquet';
		onlyFlagged?: boolean;
	}): string => {
		const fmt = params.fileFormat || 'csv';
		const flagged = params.onlyFlagged ? 'true' : 'false';
		const baseUrl = apiClient.getRawAxios().defaults.baseURL || '/api';
		return `${baseUrl}/v1/detection/jobs/${params.jobId}/export?file_format=${fmt}&only_flagged=${flagged}`;
	},

	exportResults: async (params: {
		jobId: string;
		fileFormat?: 'csv' | 'parquet';
		onlyFlagged?: boolean;
	}): Promise<void> => {
		const fmt = params.fileFormat || 'csv';
		const flagged = Boolean(params.onlyFlagged);
		const useS3Presigned = await storageApi.isS3StorageBackend();
		if (useS3Presigned) {
			const res = await apiClient.get<PresignedDownloadUrlResponse>(
				`/v1/detection/jobs/${params.jobId}/export`,
				{
					file_format: fmt,
					only_flagged: flagged,
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
		const response = await apiClient.getRawAxios().get(
			`/v1/detection/jobs/${params.jobId}/export`,
			{
				params: {
					file_format: fmt,
					only_flagged: flagged,
				},
				responseType: 'blob',
			}
		);
		const fallbackName = `detection_${params.jobId}.${fmt}`;
		const filename = storageApi.extractFilenameFromDisposition(
			response.headers['content-disposition'],
			fallbackName
		);
		storageApi.triggerBlobDownload(new Blob([response.data]), filename);
	},

	sendToInvestigation: async (
		jobId: string,
		payload: SendToInvestigationRequest
	): Promise<ApiResponse<CaseDispatchResult>> => {
		return apiClient.post<CaseDispatchResult>(
			`/v1/detection/jobs/${jobId}/send-to-investigation`,
			payload
		);
	},
};
