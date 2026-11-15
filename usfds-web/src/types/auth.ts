export type AuthMode = 'local_auto' | 'required';

export interface ProjectPermissionsDto {
	project_id: string;
	role_keys: string[];
	permissions: Record<string, string[]>;
}

export interface AuthUser {
	user_id: string;
	username: string;
	email: string | null;
	full_name: string | null;
	status: string;
	last_login_at: string | null;
	is_system_admin: boolean;
	system_role_keys: string[];
	system_permissions: Record<string, string[]>;
	projects: ProjectPermissionsDto[];
}

export interface TokenPairResponse {
	access_token: string;
	refresh_token: string;
	token_type: string;
	expires_in: number;
	user: AuthUser;
}

export interface AdminUserResponse {
	user_id: string;
	username: string;
	email: string | null;
	full_name: string | null;
	status: string;
	last_login_at: string | null;
	created_at: string;
	system_role_ids: string[];
}

export interface RoleGrantDto {
	permission_id?: string | null;
	permission_code?: string | null;
	grant_scope: string;
}

export interface RoleDto {
	role_id: string;
	name: string;
	display_name: string;
	scope: string;
	is_system: boolean;
	description: string | null;
	grants: RoleGrantDto[];
}

export interface PermissionDto {
	permission_id: string;
	code: string;
	resource: string;
	action: string;
	scope: string;
	description: string | null;
}

export interface ProjectRoleSummaryDto {
	role_id: string;
	name: string;
	display_name: string;
}

export interface ProjectMemberDto {
	project_id: string;
	user_id: string;
	username: string;
	full_name: string | null;
	email: string | null;
	status: string;
	roles: ProjectRoleSummaryDto[];
	role_keys: string[];
	permissions: Record<string, string[]>;
	added_by: string | null;
	created_at: string | null;
}
