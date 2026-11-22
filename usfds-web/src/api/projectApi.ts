import { apiClient } from './client';
import type { ApiResponse, CursorPage } from '@/types';
import type {
	CreateProjectRequest,
	ProjectResponse,
	ProjectStatus,
	UpdateProjectRequest,
} from '../types/project';

export const projectApi = {
	listProjects: async (params?: {
		userId?: string;
		status?: ProjectStatus;
		search?: string;
		limit?: number;
		cursor?: string;
	}): Promise<ApiResponse<CursorPage<ProjectResponse>>> => {
		return apiClient.get<CursorPage<ProjectResponse>>('/v1/projects', {
			user_id: params?.userId,
			status: params?.status,
			search: params?.search,
			limit: params?.limit,
			cursor: params?.cursor,
		});
	},

	getProject: async (projectId: string): Promise<ApiResponse<ProjectResponse>> => {
		return apiClient.get<ProjectResponse>(`/v1/projects/${projectId}`);
	},

	createProject: async (payload: CreateProjectRequest): Promise<ApiResponse<ProjectResponse>> => {
		return apiClient.post<ProjectResponse>('/v1/projects', payload);
	},

	updateProject: async (
		projectId: string,
		payload: UpdateProjectRequest
	): Promise<ApiResponse<ProjectResponse>> => {
		return apiClient.patch<ProjectResponse>(`/v1/projects/${projectId}`, payload);
	},

	resetProjectSchema: async (projectId: string): Promise<ApiResponse<ProjectResponse>> => {
		return apiClient.post<ProjectResponse>(`/v1/projects/${projectId}/schema/reset`);
	},

	deleteProject: async (projectId: string): Promise<ApiResponse<boolean>> => {
		return apiClient.delete<boolean>(`/v1/projects/${projectId}`);
	},
};
