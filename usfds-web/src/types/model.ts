/**
 * Model Training and Evaluation types
 */

export type ModelFramework = 'LIGHTGBM' | 'XGBOOST' | 'CATBOOST' | 'ISOLATION_FOREST' | 'AUTOENCODER' | 'ENSEMBLE';

export type JobStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'STOPPED';

export interface ModelMetrics {
  roc_auc: number;
  pr_auc: number;
  f1_score: number;
  precision: number;
  recall: number;
  ks_statistic?: number;
  inference_latency_ms?: number;
}

export interface ModelTrainingJob {
  id: string;
  projectId: string;
  modelName: string;
  version: string;
  framework: ModelFramework;
  datasetArtifactId: string;
  hyperparameters: Record<string, any>;
  status: JobStatus;
  metrics?: ModelMetrics;
  createdAt: string;
  completedAt?: string;
}
