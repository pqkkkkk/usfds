import { apiClient } from './client';
import { storageApi, type PresignedDownloadUrlResponse } from './storageApi';
import type {
  DatasetResponse,
  DatasetDetailResponse,
  DatasetArtifactResponse,
  ImportDatasetRequest,
  DataMappingConfig,
  FeatureEngineeringConfig,
  ExportDatasetRequest
} from '../types/dataset';
import type { ApiResponse, CursorPage } from '@/types';

export const datasetApi = {
  /**
   * Lấy danh sách dataset (tùy chọn lọc theo projectId, search, limit, cursor)
   */
  listDatasets: async (
    projectId: string,
    search?: string,
    pagination?: { limit?: number; cursor?: string }
  ): Promise<ApiResponse<CursorPage<DatasetResponse>>> => {
    return apiClient.get<CursorPage<DatasetResponse>>('/v1/datasets', {
      project_id: projectId,
      search: search,
      limit: pagination?.limit,
      cursor: pagination?.cursor,
    });
  },

  /**
   * Lấy chi tiết thông tin dataset bao gồm toàn bộ artifacts và lineage graph
   */
  getDatasetDetail: async (
    datasetId: string,
    projectId: string
  ): Promise<ApiResponse<DatasetDetailResponse>> => {
    return apiClient.get<DatasetDetailResponse>(`/v1/datasets/${datasetId}`, {
      project_id: projectId,
    });
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
    artifactId: string,
    projectId: string
  ): Promise<ApiResponse<DatasetArtifactResponse>> => {
    return apiClient.get<DatasetArtifactResponse>(`/v1/datasets/${datasetId}/artifacts/${artifactId}`, {
      project_id: projectId,
    });
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
      const useS3Presigned = await storageApi.isS3StorageBackend();
      if (useS3Presigned) {
        const presignedRes = await apiClient.post<PresignedDownloadUrlResponse>(
          `/v1/datasets/${datasetId}/artifacts/${artifactId}/export`,
          req,
          { presigned: true }
        );
        if (!presignedRes.success || !presignedRes.data?.download_url) {
          return {
            success: false,
            error: presignedRes.error || 'Xuất dữ liệu qua URL ký trước thất bại',
          };
        }
        storageApi.triggerBrowserDownload(
          presignedRes.data.download_url,
          presignedRes.data.filename || fallbackFilename
        );
        return { success: true };
      }

      const response = await apiClient.getRawAxios().post(
        `/v1/datasets/${datasetId}/artifacts/${artifactId}/export`,
        req,
        {
          responseType: 'blob',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      const filename = storageApi.extractFilenameFromDisposition(
        response.headers['content-disposition'],
        fallbackFilename
      );
      const blob = new Blob([response.data], { type: 'application/zip' });
      storageApi.triggerBlobDownload(blob, filename);

      return { success: true };
    } catch (err: any) {
      return { success: false, error: err.message || 'Export failed' };
    }
  },
};
