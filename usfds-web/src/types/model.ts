/**
 * Model Training, Registry, and Evaluation Types
 */

export type ExecutionType = 'BUILTIN' | 'SCRIPT' | 'DOCKER_IMAGE';

export type ModelVersionStatus = 'DRAFT' | 'CANDIDATE' | 'APPROVED' | 'DEPRECATED' | 'ARCHIVED';

export type TrainingRunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export type ModelFramework = 'scikit-learn' | 'xgboost' | 'lightgbm' | 'pytorch' | 'pyg' | 'onnx' | string;

export type DataModality = 'tabular' | 'sequence' | 'matrix_2d' | 'graph';

export type DataFormat = 'parquet' | 'csv';

export interface HyperparameterPropertySchema {
	type?: 'integer' | 'number' | 'string' | 'boolean' | 'int' | 'float';
	default?: any;
	minimum?: number;
	maximum?: number;
	min?: number;
	max?: number;
	enum?: any[];
	description?: string;
}

export interface ModelPluginManifest {
	model_name: string;
	display_name?: string | null;
	description?: string | null;
	framework?: ModelFramework;
	data_modality?: DataModality;
	data_format?: DataFormat;
	entrypoint?: string;
	required_columns?: string[];
	default_hyperparameters?: Record<string, any>;
	dry_run_hyperparameters?: Record<string, any>;
	hyperparameter_schema?: Record<string, any>;
}

export interface ModelResponse {
	model_id: string;
	project_id?: string | null;
	user_id: string;
	model_name: string;
	display_name?: string | null;
	description?: string | null;
	execution_type: ExecutionType | string;
	entrypoint_uri?: string | null;
	hyperparameter_schema?: Record<string, any> | null;
	default_hyperparameters?: Record<string, any> | null;
	risk_level?: string | null;
	github_repo?: string | null;
	created_at: string;
	updated_at?: string | null;
}

export interface ModelVersionResponse {
	version_id: string;
	model_id: string;
	project_id?: string | null;
	run_id?: string | null;
	semver: string;
	artifact_uri: string;
	description?: string | null;
	artifact_size_mb?: number | null;
	checksum_sha256?: string | null;
	framework?: string | null;
	decision_threshold: number;
	status: ModelVersionStatus | string;
	registered_by?: string | null;
	registered_at: string;
}

import type { RecommendedThresholds } from './metrics';

export interface ConfusionMatrixData {
	tn: number;
	fp: number;
	fn: number;
	tp: number;
}

export interface ThresholdGridPoint {
	threshold: number;
	precision: number;
	recall: number;
	f1_score: number;
	f2_score: number;
	accuracy: number;
	tp: number;
	fp: number;
	fn: number;
	tn: number;
}

export interface RocCurveData {
	fpr: number[];
	tpr: number[];
	thresholds: number[];
}

export interface PrCurveData {
	precision: number[];
	recall: number[];
}

export interface ScoreDistributionData {
	bin_edges: number[];
	legit_counts: number[];
	fraud_counts: number[];
}

export interface TrainingCustomMetrics {
	accuracy?: number;
	precision?: number;
	recall?: number;
	f1_score?: number;
	f2_score?: number;
	roc_auc?: number | null;
	pr_auc?: number | null;
	confusion_matrix?: ConfusionMatrixData;
	threshold_tuning_grid?: ThresholdGridPoint[];
	recommended_thresholds?: RecommendedThresholds;
	roc_curve?: RocCurveData | null;
	pr_curve?: PrCurveData | null;
	score_distribution?: ScoreDistributionData | null;
	[key: string]: any;
}

export interface TrainingRunResponse {
	run_id: string;
	project_id?: string | null;
	model_id?: string | null;
	version_id?: string | null;
	dataset_artifact_id?: string | null;
	run_name: string;
	status: TrainingRunStatus | string;
	accuracy?: number | null;
	precision_score?: number | null;
	recall_score?: number | null;
	f1_score?: number | null;
	loss?: number | null;
	default_threshold: number;
	recommended_threshold?: number | null;
	hyperparameters?: Record<string, any> | null;
	custom_metrics?: TrainingCustomMetrics | null;
	compute_target?: string | null;
	error_message?: string | null;
	created_by?: string | null;
	started_at?: string | null;
	completed_at?: string | null;
	duration_seconds?: number | null;
	logs_path?: string | null;
	metrics_path?: string | null;
	eval_predictions_path?: string | null;
	created_at: string;
}

export interface RegisterPluggedModelRequest {
	model_artifact_path?: string;
	zip_base64?: string;
	user_id?: string;
	project_id?: string;
	manifest_override?: ModelPluginManifest;
}

export interface StartTrainingRunRequest {
	model_id: string;
	dataset_artifact_id: string;
	project_id?: string;
	hyperparameters?: Record<string, any>;
	compute_target?: string;
	run_name?: string;
	created_by?: string;
}

export interface ActivateModelVersionRequest {
	decision_threshold?: number;
	description?: string;
}

// Legacy compatibility exports
export type JobStatus = TrainingRunStatus;
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
