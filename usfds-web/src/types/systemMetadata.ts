export type ColumnCategory = 'CORE' | 'DOMAIN';

export type ColumnMlRole = 'FEATURE' | 'IDENTIFIER' | 'TIMESTAMP' | 'LABEL';

export type LogicalDataType = 'NUMERIC' | 'STRING' | 'BOOLEAN' | 'DATETIME';

export interface SystemColumnMetadata {
	metadata_id: string;
	column_key: string;
	display_name: string;
	category: ColumnCategory;
	logical_type: LogicalDataType;
	is_required: boolean;
	ml_role: ColumnMlRole;
	aliases: string[];
	description?: string | null;
	is_active: boolean;
	display_order: number;
	created_at?: string | null;
	updated_at?: string | null;
}

export interface CreateSystemColumnPayload {
	column_key: string;
	display_name: string;
	logical_type: LogicalDataType;
	is_required: boolean;
	ml_role: ColumnMlRole;
	aliases: string[];
	description?: string | null;
	is_active?: boolean;
	display_order?: number;
}

export interface UpdateSystemColumnPayload {
	column_key?: string;
	display_name?: string;
	logical_type?: LogicalDataType;
	is_required?: boolean;
	ml_role?: ColumnMlRole;
	aliases?: string[];
	description?: string | null;
	is_active?: boolean;
	display_order?: number;
}
