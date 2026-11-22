import { apiClient } from './client';
import type { ApiResponse, CursorPage } from '@/types';
import type {
	ActivateModelVersionRequest,
	ModelLineageGraph,
	ModelPluginManifest,
	ModelResponse,
	ModelVersionResponse,
	RegisterPluggedModelRequest,
	StartTrainingRunRequest,
	TrainingRunResponse,
} from '../types/model';

export const trainingApi = {
	listModels: async (
		projectId: string,
		pagination?: { limit?: number; cursor?: string }
	): Promise<ApiResponse<CursorPage<ModelResponse>>> => {
		return apiClient.get<CursorPage<ModelResponse>>('/v1/training/models', {
			project_id: projectId,
			limit: pagination?.limit,
			cursor: pagination?.cursor,
		});
	},

	getModel: async (modelId: string, projectId: string): Promise<ApiResponse<ModelResponse>> => {
		return apiClient.get<ModelResponse>(`/v1/training/models/${modelId}`, {
			project_id: projectId,
		});
	},

	registerPluggedModel: async (
		payload: RegisterPluggedModelRequest
	): Promise<ApiResponse<ModelResponse>> => {
		return apiClient.post<ModelResponse>(
			'/v1/training/models/plugins',
			payload,
			undefined,
			{ timeout: 120000 }
		);
	},

	uploadPluggedModelZip: async (params: {
		file: File;
		projectId?: string;
		userId?: string;
		manifestOverride?: ModelPluginManifest;
	}): Promise<ApiResponse<ModelResponse>> => {
		const formData = new FormData();
		formData.append('file', params.file);
		if (params.projectId) {
			formData.append('project_id', params.projectId);
		}
		if (params.userId) {
			formData.append('user_id', params.userId);
		}
		if (params.manifestOverride) {
			formData.append('manifest_override_json', JSON.stringify(params.manifestOverride));
		}

		return apiClient.post<ModelResponse>(
			'/v1/training/models/plugins/upload',
			formData,
			undefined,
			{
				timeout: 120000,
				headers: {
					'Content-Type': 'multipart/form-data',
				},
			}
		);
	},

	listModelVersions: async (
		modelId: string,
		projectId: string,
		pagination?: { limit?: number; cursor?: string }
	): Promise<ApiResponse<CursorPage<ModelVersionResponse>>> => {
		return apiClient.get<CursorPage<ModelVersionResponse>>(
			`/v1/training/models/${modelId}/versions`,
			{
				project_id: projectId,
				limit: pagination?.limit,
				cursor: pagination?.cursor,
			}
		);
	},

	getModelVersion: async (
		versionId: string,
		projectId: string
	): Promise<ApiResponse<ModelVersionResponse>> => {
		return apiClient.get<ModelVersionResponse>(`/v1/training/versions/${versionId}`, {
			project_id: projectId,
		});
	},

	activateModelVersion: async (
		versionId: string,
		payload?: ActivateModelVersionRequest
	): Promise<ApiResponse<ModelVersionResponse>> => {
		return apiClient.post<ModelVersionResponse>(
			`/v1/training/versions/${versionId}/activate`,
			payload || {}
		);
	},

	startTrainingRun: async (
		payload: StartTrainingRunRequest
	): Promise<ApiResponse<TrainingRunResponse>> => {
		return apiClient.post<TrainingRunResponse>(
			'/v1/training/runs',
			payload,
			undefined,
			{ timeout: 180000 }
		);
	},

	listTrainingRuns: async (params: {
		projectId: string;
		modelId?: string;
		limit?: number;
		cursor?: string;
	}): Promise<ApiResponse<CursorPage<TrainingRunResponse>>> => {
		return apiClient.get<CursorPage<TrainingRunResponse>>('/v1/training/runs', {
			model_id: params.modelId,
			project_id: params.projectId,
			limit: params.limit,
			cursor: params.cursor,
		});
	},

	getTrainingRun: async (
		runId: string,
		projectId: string
	): Promise<ApiResponse<TrainingRunResponse>> => {
		return apiClient.get<TrainingRunResponse>(`/v1/training/runs/${runId}`, {
			project_id: projectId,
		});
	},

	getModelVersionLineage: async (
		versionId: string,
		projectId: string
	): Promise<ApiResponse<ModelLineageGraph>> => {
		return apiClient.get<ModelLineageGraph>(`/v1/training/versions/${versionId}/lineage`, {
			project_id: projectId,
		});
	},

	getTrainingRunLineage: async (
		runId: string,
		projectId: string
	): Promise<ApiResponse<ModelLineageGraph>> => {
		return apiClient.get<ModelLineageGraph>(`/v1/training/runs/${runId}/lineage`, {
			project_id: projectId,
		});
	},
};
