import { useMemo } from 'react';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { featureApi, type ListFeatureSetsParams, type ListFeaturesParams } from '@/api/featureApi';
import type {
	CloneFeatureRequest,
	CreateFeatureRequest,
	CreateFeatureSetRequest,
	FeaturePreviewRequest,
	UpdateFeatureRequest,
	UpdateFeatureSetRequest,
} from '@/types/feature';

export const featureKeys = {
	catalog: (
		projectId: string | null | undefined,
		params?: Omit<ListFeaturesParams, 'cursor'>
	) =>
		[
			'features',
			'catalog',
			projectId || '',
			params?.megafamily || 'ALL',
			params?.origin || 'ALL',
			params?.search || '',
			params?.include_builtin ?? true,
			params?.status || 'ALL',
			params?.limit ?? 50,
		] as const,
	compatibility: (projectId: string | null | undefined, datasetId?: string, artifactId?: string) =>
		['features', 'compatibility', projectId || '', datasetId || '', artifactId || ''] as const,
	sets: (
		projectId: string | null | undefined,
		params?: Omit<ListFeatureSetsParams, 'cursor'>
	) =>
		[
			'features',
			'sets',
			projectId || '',
			params?.include_builtin ?? true,
			params?.search || '',
			params?.limit ?? 50,
		] as const,
};

export function useFeatureCatalog(
	projectId: string | null | undefined,
	params?: Omit<ListFeaturesParams, 'cursor'>
) {
	const query = useInfiniteQuery({
		queryKey: featureKeys.catalog(projectId, params),
		enabled: Boolean(projectId),
		initialPageParam: undefined as string | undefined,
		queryFn: async ({ pageParam }) => {
			if (!projectId) return { items: [], nextCursor: null };
			const res = await featureApi.listFeatures(projectId, {
				...params,
				cursor: pageParam,
			});
			if (!res.success) {
				throw new Error(res.error || 'Không thể tải danh mục đặc trưng.');
			}
			return res.data ?? { items: [], nextCursor: null };
		},
		getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
	});

	const features = useMemo(
		() => query.data?.pages.flatMap((page) => page.items) ?? [],
		[query.data]
	);

	return {
		data: features,
		features,
		isLoading: query.isLoading,
		isFetching: query.isFetching,
		error: query.error,
		refetch: query.refetch,
		hasNextPage: Boolean(query.hasNextPage),
		isFetchingNextPage: query.isFetchingNextPage,
		fetchNextPage: query.fetchNextPage,
	};
}

export function useFeatureCompatibility(
	projectId: string | null | undefined,
	datasetId?: string,
	artifactId?: string
) {
	return useQuery({
		queryKey: featureKeys.compatibility(projectId, datasetId, artifactId),
		queryFn: async () => {
			if (!projectId) return null;
			const res = await featureApi.getCompatibility(projectId, {
				dataset_id: datasetId || undefined,
				artifact_id: artifactId || undefined,
			});
			if (!res.success) {
				throw new Error(res.error || 'Không thể kiểm tra độ tương thích đặc trưng.');
			}
			return res.data || null;
		},
		enabled: Boolean(projectId),
	});
}

export function useFeatureSets(
	projectId: string | null | undefined,
	paramsOrIncludeBuiltin: Omit<ListFeatureSetsParams, 'cursor'> | boolean = true
) {
	const params: Omit<ListFeatureSetsParams, 'cursor'> =
		typeof paramsOrIncludeBuiltin === 'boolean'
			? { include_builtin: paramsOrIncludeBuiltin }
			: paramsOrIncludeBuiltin;

	const query = useInfiniteQuery({
		queryKey: featureKeys.sets(projectId, params),
		enabled: Boolean(projectId),
		initialPageParam: undefined as string | undefined,
		queryFn: async ({ pageParam }) => {
			if (!projectId) return { items: [], nextCursor: null };
			const res = await featureApi.listFeatureSets(projectId, {
				...params,
				cursor: pageParam,
			});
			if (!res.success) {
				throw new Error(res.error || 'Không thể tải danh sách gói đặc trưng.');
			}
			return res.data ?? { items: [], nextCursor: null };
		},
		getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
	});

	const featureSets = useMemo(
		() => query.data?.pages.flatMap((page) => page.items) ?? [],
		[query.data]
	);

	return {
		data: featureSets,
		featureSets,
		isLoading: query.isLoading,
		isFetching: query.isFetching,
		error: query.error,
		refetch: query.refetch,
		hasNextPage: Boolean(query.hasNextPage),
		isFetchingNextPage: query.isFetchingNextPage,
		fetchNextPage: query.fetchNextPage,
	};
}

export function useFeatureMutations(projectId: string | null | undefined) {
	const queryClient = useQueryClient();

	const invalidateAll = () => {
		queryClient.invalidateQueries({ queryKey: ['features'] });
	};

	const createFeature = useMutation({
		mutationFn: async (payload: CreateFeatureRequest) => {
			const res = await featureApi.createFeature(payload);
			if (!res.success || !res.data) {
				throw new Error(res.error || res.message || 'Không thể tạo đặc trưng.');
			}
			return res.data;
		},
		onSuccess: invalidateAll,
	});

	const updateFeature = useMutation({
		mutationFn: async ({ featureId, payload }: { featureId: string; payload: UpdateFeatureRequest }) => {
			if (!projectId) throw new Error('Thiếu project_id');
			const res = await featureApi.updateFeature(featureId, projectId, payload);
			if (!res.success || !res.data) {
				throw new Error(res.error || res.message || 'Không thể cập nhật đặc trưng.');
			}
			return res.data;
		},
		onSuccess: invalidateAll,
	});

	const deleteFeature = useMutation({
		mutationFn: async (featureId: string) => {
			if (!projectId) throw new Error('Thiếu project_id');
			const res = await featureApi.deleteFeature(featureId, projectId);
			if (!res.success) {
				throw new Error(res.error || res.message || 'Không thể xóa đặc trưng.');
			}
			return true;
		},
		onSuccess: invalidateAll,
	});

	const cloneFeature = useMutation({
		mutationFn: async ({ featureId, payload }: { featureId: string; payload?: CloneFeatureRequest }) => {
			if (!projectId) throw new Error('Thiếu project_id');
			const res = await featureApi.cloneFeature(featureId, projectId, payload || {});
			if (!res.success || !res.data) {
				throw new Error(res.error || res.message || 'Không thể nhân bản đặc trưng.');
			}
			return res.data;
		},
		onSuccess: invalidateAll,
	});

	const previewFeature = useMutation({
		mutationFn: async (payload: FeaturePreviewRequest) => {
			const res = await featureApi.previewFeature(payload);
			if (!res.success || !res.data) {
				throw new Error(res.error || res.message || 'Chạy thử đặc trưng thất bại.');
			}
			return res.data;
		},
	});

	const createFeatureSet = useMutation({
		mutationFn: async (payload: CreateFeatureSetRequest) => {
			const res = await featureApi.createFeatureSet(payload);
			if (!res.success || !res.data) {
				throw new Error(res.error || res.message || 'Không thể tạo gói đặc trưng.');
			}
			return res.data;
		},
		onSuccess: invalidateAll,
	});

	const updateFeatureSet = useMutation({
		mutationFn: async ({ featureSetId, payload }: { featureSetId: string; payload: UpdateFeatureSetRequest }) => {
			if (!projectId) throw new Error('Thiếu project_id');
			const res = await featureApi.updateFeatureSet(featureSetId, projectId, payload);
			if (!res.success || !res.data) {
				throw new Error(res.error || res.message || 'Không thể cập nhật gói đặc trưng.');
			}
			return res.data;
		},
		onSuccess: invalidateAll,
	});

	const deleteFeatureSet = useMutation({
		mutationFn: async (featureSetId: string) => {
			if (!projectId) throw new Error('Thiếu project_id');
			const res = await featureApi.deleteFeatureSet(featureSetId, projectId);
			if (!res.success) {
				throw new Error(res.error || res.message || 'Không thể xóa gói đặc trưng.');
			}
			return true;
		},
		onSuccess: invalidateAll,
	});

	return {
		createFeature,
		updateFeature,
		deleteFeature,
		cloneFeature,
		previewFeature,
		createFeatureSet,
		updateFeatureSet,
		deleteFeatureSet,
	};
}
