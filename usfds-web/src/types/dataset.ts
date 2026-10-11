/**
 * Domain entity types for Datasets, Artifacts, Lineage, and Preprocessing
 */

export type PipelineStage = 
  | 'RAW' 
  | 'CLEANED' 
  | 'TRANSFORMED' 
  | 'FEATURE_STORE' 
  | 'TRAIN_SPLIT' 
  | 'TEST_SPLIT';

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

export interface DatasetSummary {
  dataset_id: string;
  project_id: string;
  user_id: string;
  dataset_name: string;
  display_name: string;
  description?: string;
  contains_pii: boolean;
  data_classification?: DataClassification | string;
  created_at: string;
  updated_at: string;
  latest_stage?: PipelineStage | string;
  latest_validation_status?: ValidationStatus | string;
  quality_score?: number | null;
  artifacts_count: number;
}

export interface DatasetArtifact {
  artifact_id: string;
  dataset_id: string;
  parent_artifact_id?: string | null;
  version_tag: string;
  pipeline_stage: PipelineStage | string;
  file_format: string;
  storage_uri: string;
  row_count?: number;
  column_count?: number;
  file_size_bytes?: number;
  checksum_sha256?: string;
  validation_status: ValidationStatus | string;
  validation_report?: Record<string, any> | null;
  schema_metadata?: Record<string, any> | null;
  profiling_summary?: Record<string, any> | null;
  created_at: string;
}

export interface DatasetDetail extends DatasetSummary {
  artifacts: DatasetArtifact[];
}

export interface LineageGraphData {
  dataset_id: string;
  nodes: LineageGraphNode[];
  edges: LineageGraphEdge[];
}

export interface LineageGraphNode {
  id: string;
  label: string;
  stage: PipelineStage | string;
  version: string;
  rows?: number;
  status: ValidationStatus | string;
  qualityScore?: number;
  createdAt?: string;
}

export interface LineageGraphEdge {
  from: string;
  to: string;
  transformationType?: string;
}

export interface ImportDatasetPayload {
  projectId: string;
  datasetName: string;
  displayName: string;
  description?: string;
  filePath: string;
  containsPii?: boolean;
  dataClassification?: DataClassification;
}
