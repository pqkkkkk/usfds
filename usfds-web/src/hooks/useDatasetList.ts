import { useState, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { datasetApi } from '../api/datasetApi';
import { PROJECTS_QUERY_KEY } from './useProjects';
import type { DatasetResponse } from '../types/dataset';

export type StageFilterTab = 'all' | 'raw' | 'mapped' | 'ready';
export const DATASETS_QUERY_KEY = ['datasets'] as const;

export function useDatasetList(projectId?: string) {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStageTab, setSelectedStageTab] = useState<StageFilterTab>('all');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const {
    data: datasets = [],
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery<DatasetResponse[]>({
    queryKey: [...DATASETS_QUERY_KEY, projectId],
    queryFn: async () => {
      const res = await datasetApi.listDatasets(projectId);
      if (!res.success) {
        throw new Error(res.error || 'Failed to fetch datasets');
      }
      return res.data || [];
    },
  });

  // 2. TanStack Mutation for deleting dataset
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await datasetApi.deleteDataset(id);
      if (!res.success) {
        throw new Error(res.error || 'Delete dataset failed');
      }
      return id;
    },
    onSuccess: (deletedId) => {
      setSelectedIds(prev => prev.filter(x => x !== deletedId));
      queryClient.invalidateQueries({ queryKey: DATASETS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
    },
  });

  // Aggregate KPI metrics
  const metrics = useMemo(() => {
    const totalDatasetsCount = datasets.length;
    const readyDatasetsCount = datasets.filter(
      d => d.latest_stage === 'PRE_PROCESSED' || d.latest_stage === 'FEATURE_ENGINEERED'
    ).length;
    const mappedCount = datasets.filter(d => d.latest_stage === 'MAPPED').length;
    const rawCount = datasets.filter(d => (d.latest_stage || 'RAW') === 'RAW').length;
    const totalArtifactsCount = datasets.reduce((sum, d) => sum + (d.artifacts_count || 1), 0);

    return {
      totalDatasetsCount,
      readyDatasetsCount,
      mappedCount,
      rawCount,
      totalArtifactsCount,
    };
  }, [datasets]);

  // Filter datasets by search query and stage tab
  const filteredDatasets = useMemo(() => {
    return datasets.filter((d) => {
      // 1. Search filter
      const matchSearch =
        d.dataset_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (d.display_name && d.display_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (d.description && d.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
        d.dataset_id.toLowerCase().includes(searchQuery.toLowerCase());
      if (!matchSearch) return false;

      // 2. Stage filter tab
      const stage = d.latest_stage || 'RAW';
      if (selectedStageTab === 'raw') return stage === 'RAW';
      if (selectedStageTab === 'mapped') return stage === 'MAPPED';
      if (selectedStageTab === 'ready') {
        return stage === 'PRE_PROCESSED' || stage === 'FEATURE_ENGINEERED';
      }
      return true;
    });
  }, [datasets, searchQuery, selectedStageTab]);

  // Checkbox selection
  const toggleSelectRow = useCallback((id: string) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.length === filteredDatasets.length && filteredDatasets.length > 0) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredDatasets.map(d => d.dataset_id));
    }
  }, [selectedIds.length, filteredDatasets]);

  const clearSelection = useCallback(() => {
    setSelectedIds([]);
  }, []);

  const isAllSelected = filteredDatasets.length > 0 && selectedIds.length === filteredDatasets.length;

  // Delete single dataset
  const deleteDataset = useCallback(async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!window.confirm(`Bạn có chắc muốn xóa dataset "${id}" cùng toàn bộ artifacts liên quan?`)) {
      return false;
    }
    try {
      await deleteMutation.mutateAsync(id);
      return true;
    } catch (err) {
      console.error('Delete dataset error:', err);
      return false;
    }
  }, [deleteMutation]);

  return {
    datasets: filteredDatasets,
    rawDatasets: datasets,
    isLoading: isLoading || isFetching,
    isDeleting: deleteMutation.isPending,
    error: error ? (error as Error).message : null,
    searchQuery,
    setSearchQuery,
    selectedStageTab,
    setSelectedStageTab,
    selectedIds,
    isAllSelected,
    metrics,
    toggleSelectRow,
    toggleSelectAll,
    clearSelection,
    deleteDataset,
    refetch,
  };
}

export default useDatasetList;
