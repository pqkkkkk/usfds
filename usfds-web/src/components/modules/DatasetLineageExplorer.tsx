import { useState, useMemo } from 'react';
import {
  GitBranch,
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileCode,
  ArrowLeft,
  Sliders,
  FileCheck2,
  Network
} from 'lucide-react';
import { PageHeader } from '../layout/PageHeader';
import { LineageCanvasView } from './LineageCanvasView';
import { buildLineageTree, computeCanvasLayout } from '../../utils/lineageLayout';
import type {
  LineageRawNode,
  LineageTreeNode,
  LineageDataResponse
} from '../../types/navigation';
import sampleLineageData from '../../data/sample_lineage.json';

interface DatasetLineageExplorerProps {
  datasetId?: string;
  datasetName?: string;
  onBackToDatasets: () => void;
  onSelectArtifactForPipeline?: (artifact: LineageRawNode, stepHint: string) => void;
}

export const DatasetLineageExplorer = ({
  datasetId,
  datasetName = 'E-Commerce Transactions 2026',
  onBackToDatasets,
  onSelectArtifactForPipeline,
}: DatasetLineageExplorerProps) => {
  // Load data from sample_lineage.json
  const lineageData: LineageDataResponse = sampleLineageData as LineageDataResponse;

  const [selectedNodeId, setSelectedNodeId] = useState<string>(
    lineageData.nodes[0]?.id || ''
  );
  const [viewMode, setViewMode] = useState<'canvas' | 'tree'>('canvas');
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({
    [lineageData.nodes[0]?.id || '']: true
  });

  // 1. Build hierarchical tree for Tree View
  const treeRoots = useMemo(() => {
    return buildLineageTree(lineageData.nodes);
  }, [lineageData.nodes]);

  // 2. Compute dynamic layered coordinates for Canvas View
  const { canvasNodes, canvasEdges, width, height } = useMemo(() => {
    return computeCanvasLayout(lineageData.nodes, lineageData.edges);
  }, [lineageData.nodes, lineageData.edges]);

  // Find the currently selected node
  const selectedNode = useMemo(() => {
    return lineageData.nodes.find(n => n.id === selectedNodeId) || lineageData.nodes[0];
  }, [lineageData.nodes, selectedNodeId]);

  const toggleExpand = (nodeId: string) => {
    setExpandedNodes(prev => ({
      ...prev,
      [nodeId]: !prev[nodeId]
    }));
  };

  const getStageBadge = (stage: string) => {
    switch (stage) {
      case 'RAW':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      case 'MAPPED':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      case 'PRE_PROCESSED':
      default:
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
    }
  };

  // Render recursive tree item
  const renderTreeItem = (node: LineageTreeNode, depth: number = 0) => {
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedNodes[node.id] ?? true;
    const isSelected = selectedNodeId === node.id;

    return (
      <div key={node.id} className="select-none">
        <div
          onClick={() => setSelectedNodeId(node.id)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs cursor-pointer transition border ${isSelected
            ? 'bg-brand-500/15 border-brand-500/50 text-white font-medium shadow-sm'
            : 'hover:bg-dark-800/60 border-transparent text-slate-300'
            }`}
          style={{ marginLeft: `${depth * 20}px` }}
        >
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(node.id);
              }}
              className="p-0.5 text-slate-400 hover:text-slate-200 rounded"
            >
              {isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
            </button>
          ) : (
            <div className="w-3.5" />
          )}

          <div className="p-1 rounded bg-dark-800 border border-dark-700 text-slate-300">
            {hasChildren ? (
              isExpanded ? <FolderOpen className="w-3.5 h-3.5 text-brand-400" /> : <Folder className="w-3.5 h-3.5 text-brand-400" />
            ) : (
              <FileCode className="w-3.5 h-3.5 text-emerald-400" />
            )}
          </div>

          <div className="flex-1 truncate">
            <span className="font-mono text-xs">{node.id.slice(0, 16)}...</span>
          </div>

          <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${getStageBadge(node.stage)}`}>
            {node.stage}
          </span>
        </div>

        {hasChildren && isExpanded && (
          <div className="border-l border-dark-800 ml-4 mt-1 space-y-1">
            {node.children.map(child => renderTreeItem(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      {/* Header */}
      <PageHeader
        title={`Lineage Explorer: ${datasetName}`}
        subtitle={`Dataset ID: ${datasetId || lineageData.dataset_id} | Đang render từ sample_lineage.json với ${lineageData.nodes.length} nodes & ${lineageData.edges.length} edges`}
        badge={`${lineageData.nodes.length} Artifacts`}
        badgeColor="blue"
        breadcrumbs={[
          { label: 'Data Management' },
          { label: 'Datasets' },
          { label: 'Lineage Explorer' }
        ]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={onBackToDatasets}
              className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs text-slate-300 transition flex items-center gap-1.5 focus-ring"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Datasets</span>
            </button>

            <div className="border-l border-dark-700 h-5 mx-1" />

            {/* Toggle View Mode: Canvas (DAG) vs Tree */}
            <div className="flex items-center bg-dark-900 border border-dark-700 p-0.5 rounded-lg">
              <button
                onClick={() => setViewMode('canvas')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5 ${viewMode === 'canvas'
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
                  }`}
              >
                <Network className="w-3.5 h-3.5" />
                <span>Canvas View (DAG)</span>
              </button>
              <button
                onClick={() => setViewMode('tree')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5 ${viewMode === 'tree'
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
                  }`}
              >
                <GitBranch className="w-3.5 h-3.5" />
                <span>Tree View (Cha - Con)</span>
              </button>
            </div>
          </div>
        }
      />

      {/* Main Area: Left (Canvas or Tree) + Right (Inspector) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Viewport (Canvas / Tree) */}
        <div className="flex-1 flex flex-col overflow-hidden relative">
          {viewMode === 'canvas' ? (
            <LineageCanvasView
              canvasNodes={canvasNodes}
              canvasEdges={canvasEdges}
              selectedNodeId={selectedNodeId}
              onSelectNode={(node) => setSelectedNodeId(node.id)}
              width={width}
              height={height}
            />
          ) : (
            <div className="flex-1 p-6 overflow-y-auto bg-dark-950/80">
              <div className="max-w-2xl bg-dark-900 border border-dark-700/80 rounded-xl p-4 shadow-xl space-y-3">
                <div className="flex items-center justify-between pb-3 border-b border-dark-800 text-xs text-slate-400">
                  <span className="font-semibold text-slate-200 flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-brand-400" />
                    Cấu trúc thư mục cha - con (File / Folder Tree)
                  </span>
                  <span className="font-mono text-[11px] text-slate-500">
                    {lineageData.nodes.length} nodes
                  </span>
                </div>

                <div className="space-y-1.5 pt-1">
                  {treeRoots.map(root => renderTreeItem(root))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel: Selected Artifact Inspector (400px) */}
        <div className="w-[380px] min-w-[380px] bg-dark-900 border-l border-dark-700/80 p-5 overflow-y-auto space-y-5 flex flex-col justify-between">
          {selectedNode ? (
            <div className="space-y-5">
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 font-mono">
                  Artifact Inspector
                </span>
                <h3 className="text-sm font-bold text-slate-100 mt-1 font-mono break-all">
                  {selectedNode.id}
                </h3>
              </div>

              {/* Node Details from sample_lineage.json */}
              <div className="bg-dark-950 p-3.5 rounded-xl border border-dark-800 space-y-2.5 text-xs font-mono">
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Pipeline Stage:</span>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getStageBadge(selectedNode.stage)}`}>
                    {selectedNode.stage}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Parent Artifact:</span>
                  <span className="text-slate-300 truncate max-w-[200px]" title={selectedNode.parent_id || 'Root'}>
                    {selectedNode.parent_id ? `${selectedNode.parent_id.slice(0, 12)}...` : 'None (Root Node)'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Created At:</span>
                  <span className="text-slate-200">
                    {new Date(selectedNode.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Dataset Context:</span>
                  <span className="text-slate-400 text-[11px] truncate max-w-[190px]">
                    {lineageData.dataset_id.slice(0, 14)}...
                  </span>
                </div>
              </div>

              {/* Actions based on node stage */}
              <div className="space-y-2 pt-2 border-t border-dark-800">
                <span className="text-[11px] font-semibold text-slate-400 uppercase font-sans">
                  Pipeline Actions
                </span>

                {selectedNode.stage === 'RAW' && (
                  <button
                    onClick={() => onSelectArtifactForPipeline && onSelectArtifactForPipeline(selectedNode, 'step-mapping')}
                    className="w-full py-2.5 px-3 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-semibold text-xs shadow-glow-blue transition flex items-center justify-center gap-2"
                  >
                    <FileCheck2 className="w-4 h-4" />
                    <span>Map Data Schema</span>
                  </button>
                )}

                {selectedNode.stage === 'MAPPED' && (
                  <>
                    <button
                      onClick={() => onSelectArtifactForPipeline && onSelectArtifactForPipeline(selectedNode, 'step-feature-eng')}
                      className="w-full py-2.5 px-3 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-semibold text-xs shadow-glow-blue transition flex items-center justify-center gap-2"
                    >
                      <Sliders className="w-4 h-4" />
                      <span>Feature Engineering</span>
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center text-xs text-slate-500 my-auto">
              Select a node on canvas or tree to inspect details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
