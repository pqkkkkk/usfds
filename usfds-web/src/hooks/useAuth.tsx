import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { authApi } from '@/api/authApi';
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '@/api/client';
import type { AuthMode, AuthUser } from '@/types/auth';

interface AuthContextValue {
	user: AuthUser | null;
	authMode: AuthMode;
	isLoading: boolean;
	isAuthenticated: boolean;
	login: (username: string, password: string) => Promise<{ ok: boolean; error?: string }>;
	logout: () => Promise<void>;
	refreshMe: () => Promise<void>;
	hasPermission: (permission: string, projectId?: string | null) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
	const [user, setUser] = useState<AuthUser | null>(null);
	const [authMode, setAuthMode] = useState<AuthMode>('local_auto');
	const [isLoading, setIsLoading] = useState(true);

	const refreshMe = useCallback(async () => {
		let mode: AuthMode = 'local_auto';
		try {
			const modeRes = await authApi.getMode();
			if (modeRes.data?.auth_mode) {
				mode = modeRes.data.auth_mode;
			}
		} catch {
			mode = 'local_auto';
		}
		setAuthMode(mode);

		const hasToken = typeof window !== 'undefined' && Boolean(localStorage.getItem(ACCESS_TOKEN_KEY));
		if (mode === 'required' && !hasToken) {
			setUser(null);
			setIsLoading(false);
			return;
		}

		try {
			const meRes = await authApi.getMe();
			setUser(meRes.data ?? null);
		} catch {
			setUser(null);
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refreshMe();
		const handleExpired = () => {
			setUser(null);
		};
		window.addEventListener('usfds:auth-expired', handleExpired);
		return () => window.removeEventListener('usfds:auth-expired', handleExpired);
	}, [refreshMe]);

	const login = useCallback(async (username: string, password: string) => {
		try {
			const res = await authApi.login(username, password);
			if (res.data) {
				localStorage.setItem(ACCESS_TOKEN_KEY, res.data.access_token);
				localStorage.setItem(REFRESH_TOKEN_KEY, res.data.refresh_token);
				if (res.data.user) {
					setUser(res.data.user);
					return { ok: true };
				}
				try {
					const meRes = await authApi.getMe();
					if (meRes.data) {
						setUser(meRes.data);
						return { ok: true };
					}
				} catch (meErr: any) {
					localStorage.removeItem(ACCESS_TOKEN_KEY);
					localStorage.removeItem(REFRESH_TOKEN_KEY);
					return { ok: false, error: meErr?.message || 'Không thể tải thông tin tài khoản' };
				}
				localStorage.removeItem(ACCESS_TOKEN_KEY);
				localStorage.removeItem(REFRESH_TOKEN_KEY);
				return { ok: false, error: 'Không thể tải thông tin tài khoản' };
			}
			return { ok: false, error: 'Đăng nhập thất bại' };
		} catch (err: any) {
			return { ok: false, error: err?.message || 'Đăng nhập thất bại' };
		}
	}, []);

	const logout = useCallback(async () => {
		const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
		if (refreshToken) {
			try {
				await authApi.logout(refreshToken);
			} catch {
				// Ignore logout API error when clearing local session
			}
		}
		localStorage.removeItem(ACCESS_TOKEN_KEY);
		localStorage.removeItem(REFRESH_TOKEN_KEY);
		setUser(null);
	}, []);

	const hasPermission = useCallback(
		(permission: string, projectId?: string | null) => {
			if (!user) {
				return false;
			}
			if (user.is_system_admin) {
				return true;
			}
			if (user.system_permissions[permission]?.length) {
				return true;
			}
			if (projectId) {
				const proj = user.projects.find((p) => p.project_id === projectId);
				if (proj && proj.permissions[permission]?.length) {
					return true;
				}
			}
			return false;
		},
		[user]
	);

	return (
		<AuthContext.Provider
			value={{
				user,
				authMode,
				isLoading,
				isAuthenticated: Boolean(user),
				login,
				logout,
				refreshMe,
				hasPermission,
			}}
		>
			{children}
		</AuthContext.Provider>
	);
}

export function useAuth(): AuthContextValue {
	const ctx = useContext(AuthContext);
	if (!ctx) {
		throw new Error('useAuth must be used within AuthProvider');
	}
	return ctx;
}
