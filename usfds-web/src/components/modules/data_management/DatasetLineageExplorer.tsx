import { useParams, useNavigate } from 'react-router-dom';
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
  Network,
  Sparkles,
  BarChart3,
  ShieldCheck,
  Loader2
} from 'lucide-react';
import { PageHeader } from '../../layout/PageHeader';
import { LineageCanvasView } from '../LineageCanvasView';
import { useDatasetDetail } from '../../../hooks/useDatasetDetail';
import type { LineageTreeNode } from '../../../types/navigation';

export const DatasetLineageExplorer = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const navigate = useNavigate();

  const {
    datasetName,
    isLoading,
    viewMode,
    setViewMode,
    selectedNodeId,
    setSelectedNodeId,
    selectedNode,
    selectedArtifactObj,
    expandedNodes,
    toggleExpand,
    lineageData,
    treeRoots,
    canvasNodes,
    canvasEdges,
    width,
    height,
    getStageBadge,
  } = useDatasetDetail(datasetId);

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
              className="p-0.5 hover:bg-dark-700 rounded text-slate-400"
            >
              {isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
            </button>
          ) : (
            <span className="w-4" />
          )}

          {hasChildren ? (
            isExpanded ? (
              <FolderOpen className="w-4 h-4 text-brand-400 shrink-0" />
            ) : (
              <Folder className="w-4 h-4 text-brand-400 shrink-0" />
            )
          ) : (
            <FileCode className="w-4 h-4 text-slate-400 shrink-0" />
          )}

          <span className="font-mono truncate">{node.id}</span>
          <span className={`text-[10px] px-1.5 py-0.2 rounded border ml-auto font-mono ${getStageBadge(node.stage)}`}>
            {node.stage}
          </span>
        </div>

        {hasChildren && isExpanded && (
          <div className="space-y-0.5">
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
        title={datasetName}
        breadcrumbs={[
          { label: 'Data Management', tab: 'data-hub' },
          { label: datasetName }
        ]}
        onNavigate={() => navigate('/datasets')}
        actions={
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => navigate('/datasets')}
              className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs text-slate-300 transition flex items-center gap-1.5"
            >
              <ArrowLeft className="w-3.5 h-3.5 text-slate-400" />
              <span>Back to Datasets</span>
            </button>
          </div>
        }
      />

      {/* Sub-toolbar: Switch Canvas vs Tree View */}
      <div className="px-6 py-2.5 bg-dark-900 border-b border-dark-800 flex items-center justify-between text-xs shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">Chế độ hiển thị:</span>
          <div className="flex items-center gap-1 bg-dark-950 p-1 rounded-lg border border-dark-800">
            <button
              onClick={() => setViewMode('canvas')}
              className={`px-3 py-1 rounded text-xs transition flex items-center gap-1.5 font-medium ${viewMode === 'canvas'
                ? 'bg-brand-500 text-white shadow-glow-blue'
                : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              <Network className="w-3.5 h-3.5" />
              <span>DAG Canvas</span>
            </button>
            <button
              onClick={() => setViewMode('tree')}
              className={`px-3 py-1 rounded text-xs transition flex items-center gap-1.5 font-medium ${viewMode === 'tree'
                ? 'bg-brand-500 text-white shadow-glow-blue'
                : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              <GitBranch className="w-3.5 h-3.5" />
              <span>Tree View</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3 text-slate-400 text-xs font-mono">
          {isLoading ? (
            <span className="flex items-center gap-1 text-brand-400">
              <Loader2 className="w-3 h-3 animate-spin" />
              Loading lineage...
            </span>
          ) : (
            <span>{lineageData.nodes.length} Artifacts</span>
          )}
        </div>
      </div>

      {/* Main View Area: Graph Canvas / Tree View + Inspector Panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Interactive Canvas or Tree View */}
        <div className="flex-1 overflow-hidden relative flex flex-col">
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
                    Cấu trúc phả hệ Artifact (Tree View)
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

        {/* Right Panel: Selected Artifact Inspector & Action Dispatcher */}
        <div className="w-[380px] min-w-[380px] bg-dark-900 border-l border-dark-800 p-5 overflow-y-auto space-y-5 flex flex-col justify-between shrink-0">
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

              {/* Node Details */}
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
                {selectedArtifactObj && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Records:</span>
                      <span className="text-slate-200">
                        {selectedArtifactObj.row_count?.toLocaleString() || '100,000'} rows
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Columns:</span>
                      <span className="text-slate-200">
                        {selectedArtifactObj.column_count || 24} features
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* Pipeline Actions based on node stage */}
              <div className="space-y-2.5 pt-2 border-t border-dark-800">
                <span className="text-[11px] font-semibold text-slate-400 uppercase font-sans">
                  Pipeline Actions
                </span>

                {/* Actions for RAW Stage */}
                {selectedNode.stage === 'RAW' && (
                  <div className="space-y-2">
                    <button
                      onClick={() => navigate(`/datasets/${datasetId}/workspace/step-profiling?artifactId=${selectedNode.id}`)}
                      className="w-full py-2.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition flex items-center justify-center gap-2"
                    >
                      <BarChart3 className="w-4 h-4" />
                      <span>View Data Profiling & Diagnostics</span>
                    </button>
                    <button
                      onClick={() => navigate(`/datasets/${datasetId}/workspace/step-mapping?artifactId=${selectedNode.id}`)}
                      className="w-full py-2.5 px-3 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-semibold text-xs shadow-glow-blue transition flex items-center justify-center gap-2"
                    >
                      <FileCheck2 className="w-4 h-4" />
                      <span>Start Schema Mapping (Branch New Artifact)</span>
                    </button>
                  </div>
                )}

                {/* Actions for MAPPED Stage */}
                {selectedNode.stage === 'MAPPED' && (
                  <div className="space-y-2">
                    <button
                      onClick={() => navigate(`/datasets/${datasetId}/workspace/step-validation?artifactId=${selectedNode.id}`)}
                      className="w-full py-2.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs transition flex items-center justify-center gap-2"
                    >
                      <ShieldCheck className="w-4 h-4" />
                      <span>View Validation Report</span>
                    </button>
                    <button
                      onClick={() => navigate(`/datasets/${datasetId}/workspace/step-feature-eng?artifactId=${selectedNode.id}`)}
                      className="w-full py-2.5 px-3 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-semibold text-xs shadow-glow-blue transition flex items-center justify-center gap-2"
                    >
                      <Sliders className="w-4 h-4" />
                      <span>Run Feature Engineering</span>
                    </button>
                  </div>
                )}

                {/* Actions for PRE_PROCESSED / FEATURE_ENGINEERED Stage */}
                {(selectedNode.stage === 'PRE_PROCESSED' || selectedNode.stage === 'FEATURE_ENGINEERED') && (
                  <div className="space-y-2">
                    <button
                      onClick={() => navigate(`/datasets/${datasetId}/workspace/step-feature-eng?artifactId=${selectedNode.id}`)}
                      className="w-full py-2.5 px-3 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-semibold text-xs transition flex items-center justify-center gap-2"
                    >
                      <Sparkles className="w-4 h-4" />
                      <span>Inspect Engineered Features</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center text-xs text-slate-500 my-auto">
              Nhấn vào một node artifact trên cây để xem chi tiết và kích hoạt tác vụ.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
