import { useQuery } from '@tanstack/react-query';
import { trainingApi } from '../api/trainingApi';
import type { ModelLineageGraph } from '../types/model';

export const MODEL_LINEAGE_QUERY_KEY = {
	byVersion: (versionId?: string, projectId?: string) =>
		['training', 'lineage', 'version', versionId, projectId] as const,
	byRun: (runId?: string, projectId?: string) =>
		['training', 'lineage', 'run', runId, projectId] as const,
};

interface UseModelLineageParams {
	versionId?: string;
	runId?: string;
	projectId?: string;
	enabled?: boolean;
}

export const useModelLineage = ({
	versionId,
	runId,
	projectId,
	enabled = true,
}: UseModelLineageParams) => {
	const targetId = versionId || runId;
	const queryKey = versionId
		? MODEL_LINEAGE_QUERY_KEY.byVersion(versionId, projectId)
		: MODEL_LINEAGE_QUERY_KEY.byRun(runId, projectId);

	const query = useQuery<ModelLineageGraph>({
		queryKey,
		enabled: Boolean(enabled && targetId && projectId),
		queryFn: async () => {
			if (!projectId) {
				throw new Error('Thiếu project_id.');
			}
			const res = versionId
				? await trainingApi.getModelVersionLineage(versionId, projectId)
				: await trainingApi.getTrainingRunLineage(runId as string, projectId);
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
