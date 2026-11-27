import { useQuery } from '@tanstack/react-query';
import { trainingApi } from '@/api/trainingApi';
import type { ComputeTargetsResponse } from '@/types/model';

export const COMPUTE_TARGETS_QUERY_KEY = 'training-compute-targets';

export interface UseComputeTargetsParams {
	projectId?: string;
	modelId?: string;
	datasetArtifactId?: string;
	enabled?: boolean;
}

export function useComputeTargets({
	projectId,
	modelId,
	datasetArtifactId,
	enabled = true,
}: UseComputeTargetsParams) {
	const query = useQuery<ComputeTargetsResponse, Error>({
		queryKey: [COMPUTE_TARGETS_QUERY_KEY, projectId, modelId ?? null, datasetArtifactId ?? null],
		enabled: Boolean(enabled && projectId),
		queryFn: async () => {
			if (!projectId) {
				throw new Error('Thiếu projectId để tải cấu hình compute.');
			}
			const res = await trainingApi.getComputeTargets({
				projectId,
				modelId: modelId || undefined,
				datasetArtifactId: datasetArtifactId || undefined,
			});
			if (!res.success || !res.data) {
				throw new Error(res.error || 'Không thể tải danh sách môi trường compute.');
			}
			return res.data;
		},
	});

	return {
		data: query.data ?? null,
		targets: query.data?.targets ?? [],
		recommendation: query.data?.recommendation ?? null,
		isLoading: query.isLoading,
		error: query.error,
		refetch: query.refetch,
	};
}
