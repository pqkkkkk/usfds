import { apiClient } from './client';
import type { ApiResponse } from '@/types';
import type { AuthMode, AuthUser, TokenPairResponse } from '@/types/auth';

export const authApi = {
	getMode: (): Promise<ApiResponse<{ auth_mode: AuthMode }>> =>
		apiClient.get<{ auth_mode: AuthMode }>('/v1/auth/mode'),

	login: (username: string, password: string): Promise<ApiResponse<TokenPairResponse>> =>
		apiClient.post<TokenPairResponse>('/v1/auth/login', { username, password }),

	refresh: (refreshToken: string): Promise<ApiResponse<TokenPairResponse>> =>
		apiClient.post<TokenPairResponse>('/v1/auth/refresh', { refresh_token: refreshToken }),

	logout: (refreshToken: string): Promise<ApiResponse<boolean>> =>
		apiClient.post<boolean>('/v1/auth/logout', { refresh_token: refreshToken }),

	getMe: (): Promise<ApiResponse<AuthUser>> =>
		apiClient.get<AuthUser>('/v1/auth/me'),

	updateProfile: (payload: { full_name?: string | null; email?: string | null }): Promise<ApiResponse<AuthUser>> =>
		apiClient.patch<AuthUser>('/v1/auth/me', payload),

	changePassword: (currentPassword: string, newPassword: string): Promise<ApiResponse<boolean>> =>
		apiClient.post<boolean>('/v1/auth/me/password', {
			current_password: currentPassword,
			new_password: newPassword,
		}),
};
