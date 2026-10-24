import { apiClient } from './client';
import type { ApiResponse } from '@/types';
import type {
	ActivateModelVersionRequest,
	ModelPluginManifest,
	ModelResponse,
	ModelVersionResponse,
	RegisterPluggedModelRequest,
	StartTrainingRunRequest,
	TrainingRunResponse,
} from '../types/model';

export const trainingApi = {
	listModels: async (projectId?: string): Promise<ApiResponse<ModelResponse[]>> => {
		return apiClient.get<ModelResponse[]>('/v1/training/models', {
			project_id: projectId,
		});
	},

	getModel: async (modelId: string): Promise<ApiResponse<ModelResponse>> => {
		return apiClient.get<ModelResponse>(`/v1/training/models/${modelId}`);
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

	listModelVersions: async (modelId: string): Promise<ApiResponse<ModelVersionResponse[]>> => {
		return apiClient.get<ModelVersionResponse[]>(`/v1/training/models/${modelId}/versions`);
	},

	getModelVersion: async (versionId: string): Promise<ApiResponse<ModelVersionResponse>> => {
		return apiClient.get<ModelVersionResponse>(`/v1/training/versions/${versionId}`);
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

	listTrainingRuns: async (params?: {
		modelId?: string;
		projectId?: string;
	}): Promise<ApiResponse<TrainingRunResponse[]>> => {
		return apiClient.get<TrainingRunResponse[]>('/v1/training/runs', {
			model_id: params?.modelId,
			project_id: params?.projectId,
		});
	},

	getTrainingRun: async (runId: string): Promise<ApiResponse<TrainingRunResponse>> => {
		return apiClient.get<TrainingRunResponse>(`/v1/training/runs/${runId}`);
	},
};
