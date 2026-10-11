import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { datasetApi } from '../api/datasetApi';
import type { ImportDatasetPayload } from '../types';

export const DATASETS_QUERY_KEY = ['datasets'] as const;

/**
 * Hook truy vấn danh sách Datasets theo project
 */
export function useDatasets(projectId?: string) {
  const queryClient = useQueryClient();

  const {
    data: datasets = [],
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: [...DATASETS_QUERY_KEY, projectId],
    queryFn: async () => {
      const res = await datasetApi.listDatasets(projectId);
      if (!res.success) {
        throw new Error(res.error || 'Failed to fetch datasets');
      }
      return res.data;
    },
  });

  const importMutation = useMutation({
    mutationFn: (payload: ImportDatasetPayload) => datasetApi.importDataset(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DATASETS_QUERY_KEY });
    },
  });

  return {
    datasets,
    loading: isLoading,
    isFetching,
    error: error ? (error as Error).message : null,
    refetch,
    importDataset: importMutation.mutateAsync,
    isImporting: importMutation.isPending,
  };
}

/**
 * Hook truy vấn chi tiết 1 Dataset cùng các artifacts
 */
export function useDatasetDetail(datasetId?: string) {
  return useQuery({
    queryKey: ['dataset-detail', datasetId],
    queryFn: async () => {
      if (!datasetId) return null;
      const res = await datasetApi.getDatasetDetail(datasetId);
      if (!res.success) {
        throw new Error(res.error || 'Failed to fetch dataset detail');
      }
      return res.data;
    },
    enabled: Boolean(datasetId),
  });
}

/**
 * Hook truy vấn đồ thị DAG Lineage của Dataset
 */
export function useDatasetLineage(datasetId?: string) {
  return useQuery({
    queryKey: ['dataset-lineage', datasetId],
    queryFn: async () => {
      if (!datasetId) return null;
      const res = await datasetApi.getDatasetLineage(datasetId);
      if (!res.success) {
        throw new Error(res.error || 'Failed to fetch dataset lineage');
      }
      return res.data;
    },
    enabled: Boolean(datasetId),
  });
}
