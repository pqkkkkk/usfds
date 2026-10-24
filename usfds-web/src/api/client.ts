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
      return 'http://127.0.0.1:8000/api';
    }
  }
  return '/api';
};

const DEFAULT_BASE_URL = getBaseUrl();

class ApiClient {
  private instance: AxiosInstance;

  constructor(baseURL: string = DEFAULT_BASE_URL) {
    this.instance = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    });

    // Request Interceptor (đính kèm auth header hoặc trace ID nếu có)
    this.instance.interceptors.request.use(
      (config) => {
        // Ví dụ: const token = localStorage.getItem('token');
        // if (token) config.headers.Authorization = `Bearer ${token}`;
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response Interceptor (chuẩn hóa response & error)
    this.instance.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error: AxiosError<any>) => {
        const errorMsg =
          error.response?.data?.detail ||
          error.response?.data?.error ||
          error.response?.data?.message ||
          error.message ||
          'Network request failed';

        return Promise.reject(new Error(errorMsg));
      }
    );
  }

  public async get<T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    try {
      const response = await this.instance.get<ApiResponse<T> | T>(url, { ...config, params });
      return this.normalizeResponse<T>(response.data);
    } catch (err: any) {
      return { success: false, data: null as unknown as T, error: err.message };
    }
  }

  public async post<T = any>(url: string, data?: unknown, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    try {
      const response = await this.instance.post<ApiResponse<T> | T>(url, data, { ...config, params });
      return this.normalizeResponse<T>(response.data);
    } catch (err: any) {
      return { success: false, data: null as unknown as T, error: err.message };
    }
  }

  public async put<T = any>(url: string, data?: unknown, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    try {
      const response = await this.instance.put<ApiResponse<T> | T>(url, data, { ...config, params });
      return this.normalizeResponse<T>(response.data);
    } catch (err: any) {
      return { success: false, data: null as unknown as T, error: err.message };
    }
  }

  public async patch<T = any>(url: string, data?: unknown, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    try {
      const response = await this.instance.patch<ApiResponse<T> | T>(url, data, { ...config, params });
      return this.normalizeResponse<T>(response.data);
    } catch (err: any) {
      return { success: false, data: null as unknown as T, error: err.message };
    }
  }

  public async delete<T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    try {
      const response = await this.instance.delete<ApiResponse<T> | T>(url, { ...config, params });
      return this.normalizeResponse<T>(response.data);
    } catch (err: any) {
      return { success: false, data: null as unknown as T, error: err.message };
    }
  }

  private normalizeResponse<T>(data: ApiResponse<T> | T): ApiResponse<T> {
    if (data && typeof data === 'object' && 'success' in data) {
      return data as ApiResponse<T>;
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
