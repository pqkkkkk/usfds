import { apiClient } from './client';
import type { ApiResponse, CursorPage } from '@/types/api';
import type {
	CloneFeatureRequest,
	CreateFeatureRequest,
	CreateFeatureSetRequest,
	FeatureCompatibilityReport,
	FeaturePreviewRequest,
	FeaturePreviewResponse,
	FeatureResponse,
	FeatureSetResponse,
	UpdateFeatureRequest,
	UpdateFeatureSetRequest,
} from '@/types/feature';

export interface ListFeaturesParams {
	megafamily?: string;
	include_builtin?: boolean;
	status?: string;
	origin?: 'BUILTIN' | 'CUSTOM';
	search?: string;
	limit?: number;
	cursor?: string;
}

export interface ListFeatureSetsParams {
	include_builtin?: boolean;
	search?: string;
	limit?: number;
	cursor?: string;
}

export const featureApi = {
	listFeatures: async (
		projectId: string,
		params?: ListFeaturesParams
	): Promise<ApiResponse<CursorPage<FeatureResponse>>> => {
		return apiClient.get<CursorPage<FeatureResponse>>('/v1/features', {
			project_id: projectId,
			...params,
		});
	},

	getCompatibility: async (
		projectId: string,
		params?: { dataset_id?: string; artifact_id?: string }
	): Promise<ApiResponse<FeatureCompatibilityReport>> => {
		return apiClient.get<FeatureCompatibilityReport>('/v1/features/compatibility', {
			project_id: projectId,
			...params,
		});
	},

	getFeature: async (featureId: string, projectId: string): Promise<ApiResponse<FeatureResponse>> => {
		return apiClient.get<FeatureResponse>(`/v1/features/${featureId}`, {
			project_id: projectId,
		});
	},

	createFeature: async (payload: CreateFeatureRequest): Promise<ApiResponse<FeatureResponse>> => {
		return apiClient.post<FeatureResponse>('/v1/features', payload);
	},

	updateFeature: async (
		featureId: string,
		projectId: string,
		payload: UpdateFeatureRequest
	): Promise<ApiResponse<FeatureResponse>> => {
		return apiClient.patch<FeatureResponse>(`/v1/features/${featureId}`, payload, {
			project_id: projectId,
		});
	},

	deleteFeature: async (featureId: string, projectId: string): Promise<ApiResponse<boolean>> => {
		return apiClient.delete<boolean>(`/v1/features/${featureId}`, {
			project_id: projectId,
		});
	},

	cloneFeature: async (
		featureId: string,
		projectId: string,
		payload: CloneFeatureRequest = {}
	): Promise<ApiResponse<FeatureResponse>> => {
		return apiClient.post<FeatureResponse>(`/v1/features/${featureId}/clone`, payload, {
			project_id: projectId,
		});
	},

	previewFeature: async (payload: FeaturePreviewRequest): Promise<ApiResponse<FeaturePreviewResponse>> => {
		return apiClient.post<FeaturePreviewResponse>('/v1/features/preview', payload);
	},

	listFeatureSets: async (
		projectId: string,
		params?: ListFeatureSetsParams
	): Promise<ApiResponse<CursorPage<FeatureSetResponse>>> => {
		return apiClient.get<CursorPage<FeatureSetResponse>>('/v1/feature-sets', {
			project_id: projectId,
			...params,
		});
	},

	createFeatureSet: async (payload: CreateFeatureSetRequest): Promise<ApiResponse<FeatureSetResponse>> => {
		return apiClient.post<FeatureSetResponse>('/v1/feature-sets', payload);
	},

	updateFeatureSet: async (
		featureSetId: string,
		projectId: string,
		payload: UpdateFeatureSetRequest
	): Promise<ApiResponse<FeatureSetResponse>> => {
		return apiClient.patch<FeatureSetResponse>(`/v1/feature-sets/${featureSetId}`, payload, {
			project_id: projectId,
		});
	},

	deleteFeatureSet: async (featureSetId: string, projectId: string): Promise<ApiResponse<boolean>> => {
		return apiClient.delete<boolean>(`/v1/feature-sets/${featureSetId}`, {
			project_id: projectId,
		});
	},
};
