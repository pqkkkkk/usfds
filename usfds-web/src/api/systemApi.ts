import { apiClient } from './client';
import type { ApiResponse } from '../types';

export interface HealthCheckResponse {
  status: string;
  app: string;
  version: string;
  database: {
    status: string;
    type: string;
    path: string;
    journal_mode: string;
  };
  storage: {
    status: string;
    type: string;
    base_dir: string;
  };
}

export const systemApi = {
  /**
   * Kiểm tra trạng thái hệ thống backend (SQLite & Storage)
   */
  checkHealth: async (): Promise<ApiResponse<HealthCheckResponse>> => {
    return apiClient.get<HealthCheckResponse>('/health');
  },
};
