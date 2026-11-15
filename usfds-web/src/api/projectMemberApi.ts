import { apiClient } from './client';
import type { ApiResponse } from '@/types';
import type { ProjectMemberDto } from '@/types/auth';

export const projectMemberApi = {
	listMembers: (projectId: string): Promise<ApiResponse<ProjectMemberDto[]>> =>
		apiClient.get<ProjectMemberDto[]>(`/v1/projects/${projectId}/members`),

	createMember: (
		projectId: string,
		payload: {
			username: string;
			password: string;
			full_name?: string | null;
			email?: string | null;
			role_id: string;
		}
	): Promise<ApiResponse<ProjectMemberDto>> =>
		apiClient.post<ProjectMemberDto>(`/v1/projects/${projectId}/members`, payload),

	removeMember: (projectId: string, userId: string): Promise<ApiResponse<number>> =>
		apiClient.delete<number>(`/v1/projects/${projectId}/members/${userId}`),

	assignRole: (projectId: string, userId: string, roleId: string): Promise<ApiResponse<ProjectMemberDto>> =>
		apiClient.post<ProjectMemberDto>(`/v1/projects/${projectId}/members/${userId}/roles`, { role_id: roleId }),

	setMemberRoles: (projectId: string, userId: string, roleIds: string[]): Promise<ApiResponse<ProjectMemberDto[]>> =>
		apiClient.put<ProjectMemberDto[]>(`/v1/projects/${projectId}/members/${userId}/roles`, { role_ids: roleIds }),

	revokeRole: (projectId: string, userId: string, roleId: string): Promise<ApiResponse<boolean>> =>
		apiClient.delete<boolean>(`/v1/projects/${projectId}/members/${userId}/roles/${roleId}`),
};
