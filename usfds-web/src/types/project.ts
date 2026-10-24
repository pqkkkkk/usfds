export type ProjectStatus = 'ACTIVE' | 'ARCHIVED';

export type LogicalDataType = 'NUMERIC' | 'STRING' | 'BOOLEAN' | 'DATETIME';

export interface ColumnSchemaSpec {
	logical_type: LogicalDataType;
	physical_dtype: string;
	nullable: boolean;
}

export interface ProjectRawSchema {
	version: number;
	locked_at: string;
	source_dataset_id?: string | null;
	columns: Record<string, ColumnSchemaSpec>;
}

export interface CreateProjectRequest {
	project_name: string;
	user_id?: string;
	description?: string;
}

export interface UpdateProjectRequest {
	project_name?: string;
	description?: string;
	status?: ProjectStatus;
}

export interface ProjectResponse {
	project_id: string;
	project_name: string;
	user_id: string;
	description?: string | null;
	status: ProjectStatus;
	is_schema_locked: boolean;
	base_dataset_id?: string | null;
	raw_schema?: ProjectRawSchema | null;
	datasets_count: number;
	rules_count: number;
	detection_jobs_count: number;
	created_at: string;
	updated_at: string;
}
