import axios, { AxiosError } from 'axios';
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import type { ApiResponse } from '@/types';

const getBaseUrl = (): string => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof window !== 'undefined') {
    const isFileProtocol = window.location.protocol === 'file:';
    const isElectron = Boolean(
      (window as any).electronAPI ||
      (window as any).process?.versions?.electron ||
      navigator.userAgent.toLowerCase().includes('electron')
    );
    if (isFileProtocol || isElectron) {
      return 'http://127.0.0.1:8200/api';
    }
  }
  return '/api';
};

const DEFAULT_BASE_URL = getBaseUrl();

export const ACCESS_TOKEN_KEY = 'usfds_access_token';
export const REFRESH_TOKEN_KEY = 'usfds_refresh_token';

export class ApiClientError extends Error {
	public readonly statusCode?: number;
	public readonly details?: unknown;

	constructor(message: string, statusCode?: number, details?: unknown) {
		super(message);
		this.name = 'ApiClientError';
		this.statusCode = statusCode;
		this.details = details;
	}
}

class ApiClient {
  private instance: AxiosInstance;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(baseURL: string = DEFAULT_BASE_URL) {
    this.instance = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    });

    // Request Interceptor (đính kèm Bearer token nếu có)
    this.instance.interceptors.request.use(
      (config) => {
        const token = typeof window !== 'undefined' ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response Interceptor (single-flight 401 refresh + chuẩn hóa error)
    this.instance.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error: AxiosError<any>) => {
        const originalRequest = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined;
        const reqUrl = originalRequest?.url || '';
        const isAuthEndpoint = reqUrl.includes('/auth/login') || reqUrl.includes('/auth/refresh');

        if (error.response?.status === 401 && originalRequest && !originalRequest._retry && !isAuthEndpoint) {
          originalRequest._retry = true;
          const newToken = await this.refreshAccessToken();
          if (newToken) {
            originalRequest.headers = {
              ...(originalRequest.headers || {}),
              Authorization: `Bearer ${newToken}`,
            };
            return this.instance.request(originalRequest);
          }
        }

        const errorMsg =
          error.response?.data?.detail ||
          error.response?.data?.error ||
          error.response?.data?.message ||
          error.message ||
          'Yêu cầu mạng thất bại';

        return Promise.reject(
          new ApiClientError(errorMsg, error.response?.status, error.response?.data)
        );
      }
    );
  }

  private async refreshAccessToken(): Promise<string | null> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }
    const refreshToken = typeof window !== 'undefined' ? localStorage.getItem(REFRESH_TOKEN_KEY) : null;
    if (!refreshToken) {
      return null;
    }
    this.refreshPromise = (async () => {
      try {
        const resp = await this.instance.post<any>('/v1/auth/refresh', { refresh_token: refreshToken });
        const payload = resp.data?.data ?? resp.data;
        if (payload?.access_token && payload?.refresh_token) {
          localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
          localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
          return payload.access_token as string;
        }
        return null;
      } catch {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new Event('usfds:auth-expired'));
        }
        return null;
      } finally {
        this.refreshPromise = null;
      }
    })();
    return this.refreshPromise;
  }

  public async get<T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.get<ApiResponse<T> | T>(url, { ...config, params });
    return this.normalizeResponse<T>(response.data, response.status);
  }

  public async post<T = any>(url: string, data?: unknown, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.post<ApiResponse<T> | T>(url, data, { ...config, params });
    return this.normalizeResponse<T>(response.data, response.status);
  }

  public async put<T = any>(url: string, data?: unknown, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.put<ApiResponse<T> | T>(url, data, { ...config, params });
    return this.normalizeResponse<T>(response.data, response.status);
  }

  public async patch<T = any>(url: string, data?: unknown, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.patch<ApiResponse<T> | T>(url, data, { ...config, params });
    return this.normalizeResponse<T>(response.data, response.status);
  }

  public async delete<T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.delete<ApiResponse<T> | T>(url, { ...config, params });
    return this.normalizeResponse<T>(response.data, response.status);
  }

  private normalizeResponse<T>(data: ApiResponse<T> | T, statusCode?: number): ApiResponse<T> {
    if (data && typeof data === 'object' && 'success' in data) {
      const apiResp = data as ApiResponse<T>;
      if (!apiResp.success) {
        throw new ApiClientError(
          apiResp.error || apiResp.message || 'Yêu cầu thất bại',
          apiResp.code ?? statusCode,
          apiResp
        );
      }
      return apiResp;
    }
    return {
      success: true,
      data: data as T,
    };
  }

  public getRawAxios(): AxiosInstance {
    return this.instance;
  }
}

export const apiClient = new ApiClient();
export { axios };
