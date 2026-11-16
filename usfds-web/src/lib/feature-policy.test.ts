import { describe, expect, it } from 'vitest';
import {
	ACTOR_FEATURE,
	canOpenActorFeature,
	getFirstAllowedModule,
	scopesOn,
	visibleProjectIds,
	type ActorContextLike,
} from './feature-policy';

const PROJECT_1 = '11111111-1111-1111-1111-111111111111';
const PROJECT_2 = '22222222-2222-2222-2222-222222222222';

const MULTI_ROLE_ACTOR: ActorContextLike = {
	user_id: 'aaaa1111-1111-1111-1111-111111111111',
	is_system_admin: false,
	system_role_keys: ['system_member'],
	system_permissions: {
		'project:create': ['SYSTEM'],
	},
	projects: [
		{
			project_id: PROJECT_1,
			role_keys: ['fraud_analyst'],
			permissions: {
				'project:read': ['PROJECT'],
				'dataset:read': ['PROJECT'],
				'rule:read': ['PROJECT'],
				'detection:read': ['PROJECT'],
				'detection:export': ['PROJECT'],
				'case:create': ['PROJECT'],
				'case:read': ['PROJECT'],
				'case:claim': ['PROJECT'],
				'case:manual_review': ['PROJECT'],
				'blacklist:manage': ['PROJECT'],
				'report:read': ['PROJECT'],
				'report:create': ['PROJECT'],
				'report:export': ['PROJECT'],
			},
		},
		{
			project_id: PROJECT_2,
			role_keys: ['data_scientist'],
			permissions: {
				'project:read': ['PROJECT'],
				'dataset:read': ['PROJECT'],
				'dataset:create': ['PROJECT'],
				'model:read': ['PROJECT'],
				'model:create': ['PROJECT'],
				'training:read': ['PROJECT'],
				'training:create': ['PROJECT'],
				'rule:read': ['PROJECT'],
				'rule:create': ['PROJECT'],
				'rule:update': ['PROJECT'],
				'rule:dry_run': ['PROJECT'],
				'rule:deploy': ['PROJECT'],
				'detection:read': ['PROJECT'],
				'report:read': ['PROJECT'],
			},
		},
	],
};

describe('feature-policy', () => {
	it('test_feature_policy_prefix_exact_and_visible_projects', () => {
		// Prefix matching: "case" matches "case:read", "case:claim", etc.
		expect(scopesOn(MULTI_ROLE_ACTOR.projects[0].permissions, 'case')).toEqual([
			'PROJECT',
			'PROJECT',
			'PROJECT',
			'PROJECT',
		]);
		// Exact action matching: "rule:create" must not match "rule:read"
		expect(scopesOn(MULTI_ROLE_ACTOR.projects[0].permissions, 'rule:create')).toEqual([]);
		expect(ACTOR_FEATURE.createRule.permission).toBe('rule:create');

		// Project 1 (fraud_analyst): investigation allowed, model & rule:create denied
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'investigation', PROJECT_1)).toBe(true);
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'modelManagement', PROJECT_1)).toBe(false);
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'createRule', PROJECT_1)).toBe(false);
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'ruleManagement', PROJECT_1)).toBe(true);

		// Project 2 (data_scientist): model & rule:create allowed, investigation & report:create denied
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'modelManagement', PROJECT_2)).toBe(true);
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'createRule', PROJECT_2)).toBe(true);
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'investigation', PROJECT_2)).toBe(false);
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'createReport', PROJECT_2)).toBe(false);

		// System feature: project:create allowed, adminUsers denied
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'createProject')).toBe(true);
		expect(canOpenActorFeature(MULTI_ROLE_ACTOR, 'adminUsers')).toBe(false);

		// visibleProjectIds
		expect(visibleProjectIds(MULTI_ROLE_ACTOR, 'createRule')).toEqual([PROJECT_2]);
		expect(visibleProjectIds(MULTI_ROLE_ACTOR, 'investigation')).toEqual([PROJECT_1]);
		expect(visibleProjectIds(MULTI_ROLE_ACTOR, 'dataManagement')).toEqual([PROJECT_1, PROJECT_2]);

		// getFirstAllowedModule respects order
		expect(getFirstAllowedModule(MULTI_ROLE_ACTOR, PROJECT_1)).toBe('data-management');

		// system_admin overrides everything and returns null for visibleProjectIds
		const sysAdmin: ActorContextLike = {
			user_id: '00000000-0000-0000-0000-000000000001',
			is_system_admin: true,
			system_role_keys: ['system_admin'],
			system_permissions: {},
			projects: [],
		};
		expect(canOpenActorFeature(sysAdmin, 'adminUsers')).toBe(true);
		expect(canOpenActorFeature(sysAdmin, 'createRule', PROJECT_1)).toBe(true);
		expect(visibleProjectIds(sysAdmin, 'createRule')).toBeNull();
	});
});
