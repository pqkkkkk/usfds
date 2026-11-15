import { apiClient } from './client';
import type { ApiResponse } from '@/types';
import type { AdminUserResponse, PermissionDto, RoleDto, RoleGrantDto } from '@/types/auth';

export const userAdminApi = {
	listUsers: (): Promise<ApiResponse<AdminUserResponse[]>> =>
		apiClient.get<AdminUserResponse[]>('/v1/users'),

	createUser: (payload: {
		username: string;
		password: string;
		email?: string | null;
		full_name?: string | null;
		system_roles?: string[];
	}): Promise<ApiResponse<AdminUserResponse>> =>
		apiClient.post<AdminUserResponse>('/v1/users', payload),

	updateUser: (userId: string, payload: { full_name?: string | null; email?: string | null }): Promise<ApiResponse<AdminUserResponse>> =>
		apiClient.patch<AdminUserResponse>(`/v1/users/${userId}`, payload),

	setUserStatus: (userId: string, status: 'ACTIVE' | 'DISABLED'): Promise<ApiResponse<AdminUserResponse>> =>
		apiClient.patch<AdminUserResponse>(`/v1/users/${userId}/status`, { status }),

	resetPassword: (userId: string, newPassword: string): Promise<ApiResponse<boolean>> =>
		apiClient.post<boolean>(`/v1/users/${userId}/reset-password`, { new_password: newPassword }),

	setSystemRoles: (userId: string, roleIds: string[]): Promise<ApiResponse<string[]>> =>
		apiClient.put<string[]>(`/v1/users/${userId}/system-roles`, { role_ids: roleIds }),

	listRoles: (scope?: 'SYSTEM' | 'PROJECT'): Promise<ApiResponse<RoleDto[]>> =>
		apiClient.get<RoleDto[]>('/v1/rbac/roles', scope ? { scope } : undefined),

	createRole: (payload: {
		name: string;
		display_name: string;
		scope: 'SYSTEM' | 'PROJECT';
		description?: string | null;
		grants?: RoleGrantDto[];
	}): Promise<ApiResponse<RoleDto>> =>
		apiClient.post<RoleDto>('/v1/rbac/roles', payload),

	setRolePermissions: (roleId: string, grants: RoleGrantDto[]): Promise<ApiResponse<RoleDto>> =>
		apiClient.put<RoleDto>(`/v1/rbac/roles/${roleId}/permissions`, { grants }),

	listPermissions: (): Promise<ApiResponse<PermissionDto[]>> =>
		apiClient.get<PermissionDto[]>('/v1/rbac/permissions'),
};
