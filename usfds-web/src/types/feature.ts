/**
 * Domain types for Feature Management, Dynamic 2-Tier Builder & Feature Sets (ISS-040)
 */
import type { ResourceOwner } from './api';

export type FeatureMegafamily =
	| 'ORDERS'
	| 'MONETARY'
	| 'IDENTITY'
	| 'PAYMENT'
	| 'LOCATIONS'
	| 'NETWORK';

export type FeatureComputeKind =
	| 'VELOCITY'
	| 'EXPRESSION'
	| 'TARGET_RATE'
	| 'PYTHON_CODE';

export type FeatureOutputType = 'NUMERIC' | 'STRING' | 'BOOLEAN';

export type FeatureStatus = 'ACTIVE' | 'DRAFT' | 'ARCHIVED';

export type FeatureCompatibilityStatus =
	| 'AVAILABLE'
	| 'MISSING_INPUTS'
	| 'MISSING_DEPENDENCY';

export interface FeatureResponse {
	feature_id: string;
	project_id?: string | null;
	user_id?: string | null;
	owner?: ResourceOwner | null;
	is_builtin: boolean;
	feature_key: string;
	display_name: string;
	description?: string | null;
	megafamily: FeatureMegafamily;
	compute_kind: FeatureComputeKind;
	output_type: FeatureOutputType;
	is_stateful: boolean;
	requires_label: boolean;
	config_json: Record<string, unknown>;
	source_code?: string | null;
	compiled_sql_preview?: string | null;
	required_inputs: string[];
	depends_on_feature_ids: string[];
	status: FeatureStatus;
	created_by?: string | null;
	created_at: string;
	updated_at: string;
}

export interface CreateFeatureRequest {
	project_id: string;
	feature_key: string;
	display_name: string;
	description?: string | null;
	megafamily: FeatureMegafamily;
	compute_kind: FeatureComputeKind;
	output_type: FeatureOutputType;
	is_stateful?: boolean;
	requires_label?: boolean;
	config_json?: Record<string, unknown>;
	source_code?: string | null;
	required_inputs: string[];
	depends_on_feature_ids?: string[];
	status?: FeatureStatus;
}

export interface UpdateFeatureRequest {
	display_name?: string;
	description?: string | null;
	megafamily?: FeatureMegafamily;
	output_type?: FeatureOutputType;
	is_stateful?: boolean;
	requires_label?: boolean;
	config_json?: Record<string, unknown>;
	source_code?: string | null;
	required_inputs?: string[];
	depends_on_feature_ids?: string[];
	status?: FeatureStatus;
}

export interface CloneFeatureRequest {
	new_feature_key?: string;
	new_display_name?: string;
}

export interface FeatureCompatibilityItem {
	feature_id: string;
	feature_key: string;
	display_name: string;
	megafamily: FeatureMegafamily | string;
	compute_kind: FeatureComputeKind | string;
	output_type: FeatureOutputType | string;
	is_builtin: boolean;
	requires_label: boolean;
	status: FeatureCompatibilityStatus | string;
	missing_inputs: string[];
	missing_dependencies: string[];
	missing_packages: string[];
}

export interface FeatureCompatibilityReport {
	available_columns: string[];
	items: FeatureCompatibilityItem[];
	available_count: number;
	unavailable_count: number;
}

export interface FeaturePreviewRequest {
	project_id: string;
	artifact_id: string;
	feature_id?: string;
	feature_spec?: Record<string, unknown>;
}

export interface FeaturePreviewResponse {
	feature_key: string;
	output_type: FeatureOutputType | string;
	sample_rows: Array<Record<string, unknown>>;
	stats: Record<string, unknown>;
	warnings: string[];
	execution_time_ms: number;
}

export interface FeatureSetResponse {
	feature_set_id: string;
	project_id?: string | null;
	user_id?: string | null;
	owner?: ResourceOwner | null;
	is_builtin: boolean;
	set_key: string;
	name: string;
	description?: string | null;
	domain_tag: string;
	default_config: Record<string, unknown>;
	feature_ids: string[];
	created_by?: string | null;
	created_at: string;
	updated_at: string;
}

export interface CreateFeatureSetRequest {
	project_id: string;
	set_key: string;
	name: string;
	description?: string | null;
	domain_tag?: string;
	default_config?: Record<string, unknown>;
	feature_ids: string[];
}

export interface UpdateFeatureSetRequest {
	name?: string;
	description?: string | null;
	domain_tag?: string;
	default_config?: Record<string, unknown>;
	feature_ids?: string[];
}
