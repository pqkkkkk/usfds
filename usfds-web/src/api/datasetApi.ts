import { apiClient } from './client';
import type { 
  ApiResponse, 
  DatasetSummary, 
  DatasetDetail, 
  DatasetArtifact,
  ImportDatasetPayload 
} from '../types';

export const datasetApi = {
  /**
   * Lấy danh sách dataset (tùy chọn lọc theo projectId)
   */
  listDatasets: async (projectId?: string): Promise<ApiResponse<DatasetSummary[]>> => {
    return apiClient.get<DatasetSummary[]>('/v1/datasets', {
      project_id: projectId,
    });
  },

  /**
   * Lấy chi tiết thông tin dataset bao gồm toàn bộ artifacts
   */
  getDatasetDetail: async (datasetId: string): Promise<ApiResponse<DatasetDetail>> => {
    return apiClient.get<DatasetDetail>(`/v1/datasets/${datasetId}`);
  },

  /**
   * Lấy biểu đồ quan hệ DAG Lineage của Dataset
   */
  getDatasetLineage: async (datasetId: string): Promise<ApiResponse<any>> => {
    return apiClient.get(`/v1/datasets/${datasetId}/lineage`);
  },

  /**
   * Import dữ liệu thô vào hệ thống
   */
  importDataset: async (payload: ImportDatasetPayload): Promise<ApiResponse<DatasetSummary>> => {
    return apiClient.post<DatasetSummary>('/v1/datasets/import', {
      project_id: payload.projectId,
      dataset_name: payload.datasetName,
      display_name: payload.displayName,
      description: payload.description,
      file_path: payload.filePath,
      contains_pii: payload.containsPii ?? false,
      data_classification: payload.dataClassification ?? 'CONFIDENTIAL',
    });
  },

  /**
   * Kích hoạt pipeline làm sạch dữ liệu (Data Cleaning)
   */
  cleanDataset: async (datasetId: string, artifactId?: string, config?: Record<string, any>): Promise<ApiResponse<DatasetArtifact>> => {
    return apiClient.post<DatasetArtifact>(`/v1/datasets/${datasetId}/clean`, {
      artifact_id: artifactId,
      cleaning_config: config,
    });
  },

  /**
   * Kích hoạt pipeline biến đổi dữ liệu (Data Transformation)
   */
  transformDataset: async (datasetId: string, artifactId?: string, config?: Record<string, any>): Promise<ApiResponse<DatasetArtifact>> => {
    return apiClient.post<DatasetArtifact>(`/v1/datasets/${datasetId}/transform`, {
      artifact_id: artifactId,
      mapping_config: config,
    });
  },

  /**
   * Xuất dataset artifact ra định dạng mong muốn
   */
  exportDataset: async (datasetId: string, artifactId: string, outputDir: string, format: string = 'parquet'): Promise<ApiResponse<{ export_path: string }>> => {
    return apiClient.post<{ export_path: string }>(`/v1/datasets/${datasetId}/export`, {
      artifact_id: artifactId,
      output_dir: outputDir,
      export_format: format,
    });
  },
};
