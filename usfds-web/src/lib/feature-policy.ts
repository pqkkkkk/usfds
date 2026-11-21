import type { AppModule } from '@/types/navigation';

export type PermissionMap = Record<string, readonly string[]>;

export interface ProjectPermissionsLike {
	project_id: string;
	role_keys: string[];
	permissions: PermissionMap;
}

export interface ActorContextLike {
	user_id: string;
	is_system_admin: boolean;
	system_role_keys: string[];
	system_permissions: PermissionMap;
	projects: ProjectPermissionsLike[];
}

export type FeatureScope = 'system' | 'project';

export interface FeaturePolicyEntry {
	permission: string | readonly string[];
	path: string;
	scope: FeatureScope;
	moduleId?: AppModule;
}

/**
 * Centralized feature policy registry driven by ActorContext.
 * - Resource prefix (e.g. "dataset") matches "dataset" and every "dataset:*" action.
 * - Exact action key (e.g. "rule:create") matches only that action.
 */
export const ACTOR_FEATURE = {
	// System / portal features
	adminUsers: { permission: ['user:read', 'role:read', 'system_metadata:manage'], path: '/admin/users', scope: 'system' },
	createProject: { permission: 'project:create', path: '/projects', scope: 'system' },
	manageBuiltinModels: { permission: 'model_builtin:manage', path: '/models', scope: 'system' },
	manageSystemMetadata: { permission: 'system_metadata:manage', path: '/admin/users', scope: 'system' },
	createUser: { permission: 'user:create', path: '/admin/users', scope: 'system' },
	updateUser: { permission: 'user:update', path: '/admin/users', scope: 'system' },
	resetUserPassword: { permission: 'user:reset_password', path: '/admin/users', scope: 'system' },
	viewRoles: { permission: 'role:read', path: '/admin/users', scope: 'system' },
	manageRoles: { permission: 'role:manage', path: '/admin/users', scope: 'system' },

	// Workspace sidebar modules
	dataManagement: { permission: 'dataset', path: '/datasets', scope: 'project', moduleId: 'data-management' },
	modelManagement: { permission: ['model:read', 'training:read'], path: '/models', scope: 'project', moduleId: 'model-management' },
	ruleManagement: { permission: 'rule:read', path: '/rules', scope: 'project', moduleId: 'rule-management' },
	detection: { permission: 'detection:read', path: '/detection', scope: 'project', moduleId: 'detection' },
	investigation: { permission: ['case:read', 'blacklist:manage'], path: '/investigation', scope: 'project', moduleId: 'investigation' },
	insightReport: { permission: 'report:read', path: '/reports', scope: 'project', moduleId: 'insight-report' },
	projectSettings: { permission: 'project:read', path: '/settings', scope: 'project', moduleId: 'project-settings' },

	// Project management actions
	updateProject: { permission: 'project:update', path: '/settings', scope: 'project' },
	deleteProject: { permission: 'project:delete', path: '/projects', scope: 'project' },
	resetProjectSchema: { permission: 'project:reset_schema', path: '/settings', scope: 'project' },
	viewProjectMembers: { permission: ['project_member:read', 'project_member:manage'], path: '/settings', scope: 'project' },
	manageProjectMembers: { permission: 'project_member:manage', path: '/settings', scope: 'project' },

	// Data management actions
	createDataset: { permission: 'dataset:create', path: '/datasets', scope: 'project' },
	updateDataset: { permission: 'dataset:update', path: '/datasets', scope: 'project' },
	deleteDataset: { permission: 'dataset:delete', path: '/datasets', scope: 'project' },
	exportDataset: { permission: 'dataset:export', path: '/datasets', scope: 'project' },

	// Model & training actions
	createModel: { permission: 'model:create', path: '/models', scope: 'project' },
	createTraining: { permission: 'training:create', path: '/models/train', scope: 'project' },
	deployModel: { permission: 'deployment:deploy', path: '/models', scope: 'project' },
	undeployModel: { permission: 'deployment:undeploy', path: '/models', scope: 'project' },

	// Rule engine actions (PA-A: exact action keys, no rule:propose)
	createRule: { permission: 'rule:create', path: '/rules/new', scope: 'project' },
	updateRule: { permission: 'rule:update', path: '/rules', scope: 'project' },
	deleteRule: { permission: 'rule:delete', path: '/rules', scope: 'project' },
	dryRunRule: { permission: 'rule:dry_run', path: '/rules', scope: 'project' },
	deployRule: { permission: 'rule:deploy', path: '/rules', scope: 'project' },
	undeployRule: { permission: 'rule:undeploy', path: '/rules', scope: 'project' },

	// Detection actions
	createDetection: { permission: 'detection:create', path: '/detection/new', scope: 'project' },
	exportDetection: { permission: 'detection:export', path: '/detection', scope: 'project' },
	sendToInvestigation: { permission: 'case:create', path: '/detection', scope: 'project' },

	// Investigation actions
	claimCase: { permission: 'case:claim', path: '/investigation', scope: 'project' },
	assignCase: { permission: 'case:assign', path: '/investigation', scope: 'project' },
	reviewCase: { permission: 'case:manual_review', path: '/investigation', scope: 'project' },
	escalateCase: { permission: 'case:escalate', path: '/investigation', scope: 'project' },
	reopenCase: { permission: 'case:reopen', path: '/investigation', scope: 'project' },
	manageBlacklist: { permission: 'blacklist:manage', path: '/investigation/policies', scope: 'project' },

	// Insight & report actions
	createReport: { permission: 'report:create', path: '/reports', scope: 'project' },
	exportReport: { permission: 'report:export', path: '/reports', scope: 'project' },
} as const satisfies Record<string, FeaturePolicyEntry>;

export type ActorFeatureKey = keyof typeof ACTOR_FEATURE;

export const MODULE_FEATURE_MAP: Record<AppModule, ActorFeatureKey> = {
	'data-management': 'dataManagement',
	'model-management': 'modelManagement',
	'rule-management': 'ruleManagement',
	'detection': 'detection',
	'investigation': 'investigation',
	'insight-report': 'insightReport',
	'project-settings': 'projectSettings',
};

const ORDERED_MODULES: readonly AppModule[] = [
	'data-management',
	'model-management',
	'rule-management',
	'detection',
	'investigation',
	'insight-report',
	'project-settings',
];

function toPermissionList(permission: string | readonly string[]): readonly string[] {
	return typeof permission === 'string' ? [permission] : permission;
}

/**
 * Collect granted scopes on a permission map.
 * A resource key (e.g. "case") matches both "case" and every "case:*" action.
 */
export function scopesOn(permissions: PermissionMap | undefined, permission: string | readonly string[]): string[] {
	if (!permissions) {
		return [];
	}
	const wanted = toPermissionList(permission);
	const scopes: string[] = [];
	for (const target of wanted) {
		const prefix = `${target}:`;
		for (const [key, values] of Object.entries(permissions)) {
			if (key === target || key.startsWith(prefix)) {
				scopes.push(...values);
			}
		}
	}
	return scopes;
}

/** Collect granted scopes for a permission across system_permissions and (optionally one) project. */
export function scopesFor(
	actor: ActorContextLike,
	permission: string | readonly string[],
	projectId?: string | null
): string[] {
	const scopes = scopesOn(actor.system_permissions, permission);
	if (projectId !== undefined) {
		if (projectId) {
			const proj = actor.projects.find((p) => p.project_id === projectId);
			if (proj) {
				scopes.push(...scopesOn(proj.permissions, permission));
			}
		}
		return scopes;
	}
	for (const proj of actor.projects) {
		scopes.push(...scopesOn(proj.permissions, permission));
	}
	return scopes;
}

/** Return true if the actor is allowed to open or execute the given feature (optionally scoped to projectId). */
export function canOpenActorFeature(
	actor: ActorContextLike | null | undefined,
	feature: ActorFeatureKey,
	projectId?: string | null
): boolean {
	if (!actor) {
		return false;
	}
	if (actor.is_system_admin) {
		return true;
	}
	const entry = ACTOR_FEATURE[feature];
	if (entry.scope === 'system') {
		return scopesOn(actor.system_permissions, entry.permission).length > 0;
	}
	return scopesFor(actor, entry.permission, projectId).length > 0;
}

/**
 * Project IDs where the actor holds the given feature.
 * Returns null if unrestricted (is_system_admin or granted in system_permissions).
 */
export function visibleProjectIds(
	actor: ActorContextLike | null | undefined,
	feature: ActorFeatureKey
): string[] | null {
	if (!actor) {
		return [];
	}
	if (actor.is_system_admin) {
		return null;
	}
	const entry = ACTOR_FEATURE[feature];
	const sysScopes = scopesOn(actor.system_permissions, entry.permission);
	if (sysScopes.includes('SYSTEM')) {
		return null;
	}
	if (entry.scope === 'system') {
		return [];
	}
	const granted = actor.projects.filter((proj) => scopesOn(proj.permissions, entry.permission).length > 0);
	return [...new Set(granted.map((proj) => proj.project_id))];
}

/** Return the first workspace module the actor can access inside projectId, or null if none. */
export function getFirstAllowedModule(
	actor: ActorContextLike | null | undefined,
	projectId?: string | null
): AppModule | null {
	for (const mod of ORDERED_MODULES) {
		if (canOpenActorFeature(actor, MODULE_FEATURE_MAP[mod], projectId)) {
			return mod;
		}
	}
	return null;
}
