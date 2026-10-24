import { apiClient } from './client';
import type { ApiResponse } from '@/types';
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
	}): Promise<ApiResponse<ProjectResponse[]>> => {
		return apiClient.get<ProjectResponse[]>('/v1/projects', {
			user_id: params?.userId,
			status: params?.status,
			search: params?.search,
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
