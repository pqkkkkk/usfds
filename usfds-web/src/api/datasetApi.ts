import { apiClient, axios } from './client';
import type {
  DatasetResponse,
  DatasetDetailResponse,
  DatasetArtifactResponse,
  ImportDatasetRequest,
  DataMappingConfig,
  FeatureEngineeringConfig,
  ExportDatasetRequest
} from '../types/dataset';
import type { ApiResponse } from '@/types';

export const datasetApi = {
  /**
   * Lấy danh sách dataset (tùy chọn lọc theo projectId hoặc từ khóa tìm kiếm)
   */
  listDatasets: async (projectId?: string, search?: string): Promise<ApiResponse<DatasetResponse[]>> => {
    return apiClient.get<DatasetResponse[]>('/v1/datasets', {
      project_id: projectId,
      search: search,
    });
  },

  /**
   * Lấy chi tiết thông tin dataset bao gồm toàn bộ artifacts và lineage graph
   */
  getDatasetDetail: async (datasetId: string): Promise<ApiResponse<DatasetDetailResponse>> => {
    return apiClient.get<DatasetDetailResponse>(`/v1/datasets/${datasetId}`);
  },

  /**
   * Import tập dữ liệu thô vào hệ thống
   */
  importDataset: async (payload: ImportDatasetRequest): Promise<ApiResponse<DatasetDetailResponse>> => {
    return apiClient.post<DatasetDetailResponse>('/v1/datasets/import', payload);
  },

  /**
   * Xóa dataset cùng toàn bộ artifacts liên quan
   */
  deleteDataset: async (datasetId: string): Promise<ApiResponse<null>> => {
    return apiClient.delete<null>(`/v1/datasets/${datasetId}`);
  },

  /**
   * Ánh xạ schema và kiểm tra chất lượng dữ liệu
   */
  mapSchema: async (
    datasetId: string,
    mappingConfig: DataMappingConfig
  ): Promise<ApiResponse<DatasetArtifactResponse>> => {
    return apiClient.post<DatasetArtifactResponse>(`/v1/datasets/${datasetId}/schema-mapping`, mappingConfig);
  },

  /**
   * Thực thi Feature Engineering & Cleansing từ artifact MAPPED
   * POST /api/v1/datasets/{dataset_id}/feature-engineering
   * Request Body: FeatureEngineeringConfig
   * Response: ApiResponse<DatasetArtifactResponse>
   */
  executeFeatureEngineering: async (
    datasetId: string,
    config: FeatureEngineeringConfig
  ): Promise<ApiResponse<DatasetArtifactResponse>> => {
    return apiClient.post<DatasetArtifactResponse>(`/v1/datasets/${datasetId}/feature-engineering`, config);
  },

  /**
   * Lấy metadata và validation report của một artifact cụ thể
   */
  getArtifact: async (
    datasetId: string,
    artifactId: string
  ): Promise<ApiResponse<DatasetArtifactResponse>> => {
    return apiClient.get<DatasetArtifactResponse>(`/v1/datasets/${datasetId}/artifacts/${artifactId}`);
  },

  /**
   * Xuất dataset đã chuẩn hóa ra file ZIP néns
   */
  exportDataset: async (
    datasetId: string,
    artifactId: string,
    req: ExportDatasetRequest,
    fallbackFilename: string = 'usfds_dataset_export.zip'
  ): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await axios.post(
        `/api/v1/datasets/${datasetId}/artifacts/${artifactId}/export`,
        req,
        {
          responseType: 'blob',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      // Extract filename from header or fallback
      let filename = fallbackFilename;
      const disposition = response.headers['content-disposition'];
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename=(?:["']?)([^"';]+)(?:["']?)/);
        if (match && match[1]) {
          filename = match[1].trim();
        }
      }

      // Trigger browser download
      const blob = new Blob([response.data], { type: 'application/zip' });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

      return { success: true };
    } catch (err: any) {
      return { success: false, error: err.message || 'Export failed' };
    }
  },
};
