import { useQuery } from '@tanstack/react-query';
import { trainingApi } from '../api/trainingApi';
import type { ModelLineageGraph } from '../types/model';

export const MODEL_LINEAGE_QUERY_KEY = {
	byVersion: (versionId?: string) => ['training', 'lineage', 'version', versionId] as const,
	byRun: (runId?: string) => ['training', 'lineage', 'run', runId] as const,
};

interface UseModelLineageParams {
	versionId?: string;
	runId?: string;
	enabled?: boolean;
}

export const useModelLineage = ({
	versionId,
	runId,
	enabled = true,
}: UseModelLineageParams) => {
	const targetId = versionId || runId;
	const queryKey = versionId
		? MODEL_LINEAGE_QUERY_KEY.byVersion(versionId)
		: MODEL_LINEAGE_QUERY_KEY.byRun(runId);

	const query = useQuery<ModelLineageGraph>({
		queryKey,
		enabled: Boolean(enabled && targetId),
		queryFn: async () => {
			const res = versionId
				? await trainingApi.getModelVersionLineage(versionId)
				: await trainingApi.getTrainingRunLineage(runId as string);
			if (!res.success || !res.data) {
				throw new Error(res.message || 'Không thể tải phả hệ dữ liệu.');
			}
			return res.data;
		},
	});

	return {
		lineage: query.data ?? null,
		isLoading: query.isLoading,
		errorMessage: query.error
			? query.error instanceof Error
				? query.error.message
				: 'Không thể tải phả hệ dữ liệu.'
			: null,
		refetch: query.refetch,
	};
};
