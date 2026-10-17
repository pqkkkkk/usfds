import { useState, useMemo, useEffect, useCallback } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { datasetApi } from '../api/datasetApi';
import { buildLineageTree, computeCanvasLayout } from '../utils/lineageLayout';
import type { DatasetDetailResponse, DatasetArtifactResponse, ExportDatasetRequest } from '../types/dataset';
import type { LineageTreeNode, LineageDataResponse, LineageCanvasNode, LineageCanvasEdge } from '../types/navigation';

export const DATASET_DETAIL_QUERY_KEY = ['dataset-detail'] as const;

export function useDatasetDetail(datasetId: string | undefined) {
  const [viewMode, setViewMode] = useState<'canvas' | 'tree'>('canvas');
  const [selectedNodeId, setSelectedNodeId] = useState<string>('');
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  // Fetch detail dataset
  const {
    data: datasetDetail = null,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery<DatasetDetailResponse | null>({
    queryKey: [...DATASET_DETAIL_QUERY_KEY, datasetId],
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

  // Auto-select initial node once data is loaded
  useEffect(() => {
    if (datasetDetail?.lineage?.nodes && datasetDetail.lineage.nodes.length > 0 && !selectedNodeId) {
      setSelectedNodeId(datasetDetail.lineage.nodes[0].id);
      setExpandedNodes({ [datasetDetail.lineage.nodes[0].id]: true });
    }
  }, [datasetDetail, selectedNodeId]);

  // Combine real backend lineage data or empty fallback
  const lineageData: LineageDataResponse = useMemo(() => {
    if (datasetDetail?.lineage && datasetDetail.lineage.nodes && datasetDetail.lineage.nodes.length > 0) {
      return {
        dataset_id: datasetDetail.dataset.dataset_id,
        nodes: datasetDetail.lineage.nodes.map(n => ({
          id: n.id,
          stage: n.stage,
          created_at: n.created_at,
          parent_id: n.parent_id || null,
        })),
        edges: datasetDetail.lineage.edges || [],
      };
    }
    return {
      dataset_id: datasetId || '',
      nodes: [],
      edges: [],
    };
  }, [datasetDetail, datasetId]);

  // Auto-select first node if none selected
  useEffect(() => {
    if (!selectedNodeId && lineageData.nodes && lineageData.nodes.length > 0) {
      setSelectedNodeId(lineageData.nodes[0].id);
    }
  }, [lineageData, selectedNodeId]);

  // Hierarchical tree structure for Tree View
  const treeRoots: LineageTreeNode[] = useMemo(() => {
    return buildLineageTree(lineageData.nodes || []);
  }, [lineageData.nodes]);

  // Dynamic layered coordinates for Canvas View
  const { canvasNodes, canvasEdges, width, height } = useMemo<{
    canvasNodes: LineageCanvasNode[];
    canvasEdges: LineageCanvasEdge[];
    width: number;
    height: number;
  }>(() => {
    return computeCanvasLayout(lineageData.nodes || [], lineageData.edges || []);
  }, [lineageData.nodes, lineageData.edges]);

  // Currently selected node object
  const selectedNode = useMemo(() => {
    return (lineageData.nodes || []).find(n => n.id === selectedNodeId) || lineageData.nodes?.[0] || null;
  }, [lineageData.nodes, selectedNodeId]);

  // Matching real artifact object if available
  const selectedArtifactObj: DatasetArtifactResponse | null = useMemo(() => {
    if (!datasetDetail || !selectedNode) return null;
    return datasetDetail.artifacts.find(a => a.artifact_id === selectedNode.id) || null;
  }, [datasetDetail, selectedNode]);

  // Expand / collapse tree item
  const toggleExpand = useCallback((nodeId: string) => {
    setExpandedNodes(prev => ({
      ...prev,
      [nodeId]: !prev[nodeId]
    }));
  }, []);

  const getStageBadge = useCallback((stage: string) => {
    switch (stage) {
      case 'RAW':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      case 'MAPPED':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      case 'PRE_PROCESSED':
      case 'FEATURE_ENGINEERED':
      default:
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
    }
  }, []);

  // Export Dataset handler
  const exportMutation = useMutation({
    mutationFn: async ({
      artifactId,
      payload,
      fallbackFilename,
    }: {
      artifactId: string;
      payload: ExportDatasetRequest;
      fallbackFilename?: string;
    }) => {
      if (!datasetId) throw new Error('Dataset ID is missing');
      const res = await datasetApi.exportDataset(datasetId, artifactId, payload, fallbackFilename);
      if (!res.success) {
        throw new Error(res.error || 'Xuất dữ liệu thất bại');
      }
      return res;
    },
  });

  const datasetName = datasetDetail?.dataset.dataset_name || 'Dataset Lineage';

  return {
    datasetDetail,
    datasetName,
    isLoading: isLoading || isFetching,
    error: error ? (error as Error).message : null,
    viewMode,
    setViewMode,
    selectedNodeId,
    setSelectedNodeId,
    selectedNode,
    selectedArtifactObj,
    expandedNodes,
    toggleExpand,
    isExportModalOpen,
    setIsExportModalOpen,
    lineageData,
    treeRoots,
    canvasNodes,
    canvasEdges,
    width,
    height,
    getStageBadge,
    refetch,

    // Export dataset action & status
    exportDataset: exportMutation.mutateAsync,
    isExporting: exportMutation.isPending,
    exportError: exportMutation.error ? (exportMutation.error as Error).message : null,
  };
}

export default useDatasetDetail;
