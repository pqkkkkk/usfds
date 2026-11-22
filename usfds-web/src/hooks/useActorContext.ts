import { useCallback, useMemo } from 'react';
import { useAuth } from '@/hooks/useAuth';
import {
	ACTOR_FEATURE,
	canAccessRecordFeature,
	canOpenActorFeature,
	visibleProjectIds,
	type ActorContextLike,
	type ActorFeatureKey,
} from '@/lib/feature-policy';

export type { ActorFeatureKey };

export const actorContextKeys = {
	all: ['actor-context'] as const,
	current: (userId: string) => ['actor-context', userId] as const,
};

export interface FeatureAccess {
	allowed: boolean;
	projectIds: string[] | null;
}

function featureAccess(
	actor: ActorContextLike | null,
	feature: ActorFeatureKey,
	ready: boolean,
	projectId?: string | null
): FeatureAccess {
	return {
		allowed: ready && canOpenActorFeature(actor, feature, projectId),
		projectIds: actor ? visibleProjectIds(actor, feature) : null,
	};
}

/**
 * One actor context derived from useAuth() (/api/v1/auth/me), plus the feature map every page reads.
 * Pass projectId for project-scoped workspace views, or use can(feature, targetProjectId) per row.
 */
export function useActorContext(projectId?: string | null) {
	const { user, isLoading } = useAuth();
	const actor = user ?? null;
	const ready = !isLoading && Boolean(actor);

	const features = useMemo(() => {
		const map = {} as Record<ActorFeatureKey, FeatureAccess>;
		for (const key of Object.keys(ACTOR_FEATURE) as ActorFeatureKey[]) {
			map[key] = featureAccess(actor, key, ready, projectId);
		}
		return map;
	}, [actor, ready, projectId]);

	const canOpenFeature = useCallback(
		(feature: ActorFeatureKey, targetProjectId?: string | null) => {
			if (!ready) {
				return false;
			}
			return canOpenActorFeature(actor, feature, targetProjectId !== undefined ? targetProjectId : projectId);
		},
		[actor, ready, projectId]
	);

	const canAccessRecord = useCallback(
		(feature: ActorFeatureKey, ownerId?: string | null, targetProjectId?: string | null) => {
			if (!ready) {
				return false;
			}
			return canAccessRecordFeature(
				actor,
				feature,
				ownerId,
				targetProjectId !== undefined ? targetProjectId : projectId
			);
		},
		[actor, ready, projectId]
	);

	return {
		actor,
		loading: isLoading,
		error: null as Error | null,
		features,
		canOpenFeature,
		canAccessRecord,
	};
}
