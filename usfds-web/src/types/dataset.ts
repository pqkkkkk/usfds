/**
 * Domain entity types for Datasets, Artifacts, Lineage, and Preprocessing
 * Matched with USFDS FastAPI Backend schemas and Domain models
 */

export type PipelineStage =
  | 'RAW'
  | 'MAPPED'
  | 'FEATURE_ENGINEERED'
  | 'PRE_PROCESSED';

export type ValidationStatus =
  | 'PENDING'
  | 'PASSED'
  | 'WARNING'
  | 'FAILED'
  | 'SKIPPED';

export type DataClassification =
  | 'PUBLIC'
  | 'INTERNAL'
  | 'CONFIDENTIAL'
  | 'RESTRICTED';

export interface DatasetResponse {
  dataset_id: string;
  project_id: string;
  user_id: string;
  dataset_name: string;
  display_name?: string;
  description?: string;
  contains_pii: boolean;
  data_classification?: DataClassification | string;
  created_at: string;
  updated_at?: string;
  latest_stage?: PipelineStage | string;
  latest_validation_status?: ValidationStatus | string;
  quality_score?: number | null;
  artifacts_count: number;
}

// Backward compatibility alias
export type DatasetSummary = DatasetResponse;

export interface DatasetArtifactResponse {
  artifact_id: string;
  dataset_id: string;
  parent_artifact_id?: string | null;
  pipeline_stage: PipelineStage | string;
  change_type?: string;
  storage_path: string;
  output_paths: Record<string, string>;
  checksum_sha256?: string;
  schema_snapshot?: Record<string, string>;
  row_count?: number;
  column_count?: number;
  validation_status?: ValidationStatus | string;
  quality_score?: number | null;
  validation_report?: Record<string, any> | null;
  created_by?: string;
  created_at: string;
}

// Backward compatibility alias
export type DatasetArtifact = DatasetArtifactResponse;

export interface LineageNodeResponse {
  id: string;
  stage: string;
  created_at: string;
  parent_id?: string | null;
}

export interface LineageEdgeResponse {
  source: string;
  target: string;
}

export interface LineageGraphResponse {
  dataset_id: string;
  nodes: LineageNodeResponse[];
  edges: LineageEdgeResponse[];
}

export interface DatasetDetailResponse {
  dataset: DatasetResponse;
  artifacts: DatasetArtifactResponse[];
  lineage: LineageGraphResponse;
}

export type DatasetDetail = DatasetDetailResponse;

export interface ImportDatasetRequest {
  file_path: string;
  dataset_name?: string;
  display_name?: string;
  description?: string;
  project_id?: string;
  user_id?: string;
  contains_pii?: boolean;
  data_classification?: DataClassification | string;
}

export type ImportDatasetPayload = ImportDatasetRequest;

export interface DataMappingConfig {
  event_id_column: string;
  time_column: string;
  amount_column: string;
  user_id_column?: string;
  target_column?: string;
  optional_columns: Record<string, string>;
  time_format?: 'auto' | 'iso' | 'epoch_s' | 'epoch_ms' | string;
  max_invalid_ratio_allowed?: number;
}

export interface SplitConfig {
  time_column?: string;
  target_column: string;
  test_size: number;
  val_size?: number;
}

export interface CleansingConfig {
  drop_duplicates?: boolean;
  missing_value_strategy?: 'drop' | 'mean' | 'median' | 'constant' | 'impute' | 'none';
  fill_value?: any;
  outlier_clipping?: boolean;
  outlier_lower_percentile?: number;
  outlier_upper_percentile?: number;
  time_format?: string;
  drop_columns?: string[];
}

export interface FeatureEngineeringConfig {
  split: SplitConfig;
  cleansing: CleansingConfig;
  time_col?: string;
  amount_col?: string;
  user_id_col?: string;
  enable_amount_ratios: boolean;
  enable_hour_of_day: boolean;
  enable_velocity_features: boolean;
  velocity_windows: number[];
}

export interface ExportDatasetRequest {
  include_train: boolean;
  include_test: boolean;
  include_pipeline: boolean;
  include_schema: boolean;
  file_format: 'parquet' | 'csv' | string;
}

export interface FieldProfilingSummary {
  name: string;
  dtype: string;
  unique_count: number;
  null_count: number;
  null_percentage: number;
}

export interface DatasetProfilingSummary {
  row_count: number;
  field_count: number;
  field_names: string[];
  fields: FieldProfilingSummary[];
}

export interface ColumnQualityMetric {
  name: string;
  dtype: string;
  null_count: number;
  null_percentage: number;
  unique_count: number;
  sample_values?: any[];
}

export interface DataQualityReport {
  quality_score: number;
  rating: string;
  validation_status: ValidationStatus | string;
  total_rows: number;
  total_columns: number;
  duplicate_rows_count: number;
  duplicate_rows_ratio: number;
  duplicate_event_ids_count: number;
  duplicate_event_ids_ratio: number;
  non_positive_amount_count: number;
  non_positive_amount_ratio: number;
  future_timestamp_count: number;
  future_timestamp_ratio: number;
  amount_outliers_count: number;
  amount_outliers_ratio: number;
  amount_q999?: number | null;
  column_metrics: Record<string, ColumnQualityMetric>;
  sample_records?: Record<string, any>[];
  warnings: string[];
  critical_errors: string[];
  recommendations: string[];
}
