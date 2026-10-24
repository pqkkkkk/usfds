import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Database,
  Search,
  Trash2,
  RefreshCw,
  Plus,
  CheckCircle2,
  ArrowRight,
  ShieldAlert,
  Layers
} from 'lucide-react';
import { PageHeader } from '../../layout/PageHeader';
import { ImportDatasetModal } from './ImportDatasetModal';
import { useDatasetList } from '../../../hooks/useDatasetList';
import { useProject } from '../../../hooks/useProjects';
import type { DatasetDetailResponse } from '../../../types/dataset';

export const DatasetHubView = () => {
  const navigate = useNavigate();
  const { currentProjectId } = useProject();
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);

  const {
    datasets: filteredDatasets,
    isLoading,
    searchQuery,
    setSearchQuery,
    selectedStageTab,
    setSelectedStageTab,
    selectedIds,
    isAllSelected,
    metrics,
    toggleSelectRow,
    toggleSelectAll,
    deleteDataset,
    refetch,
  } = useDatasetList(currentProjectId);

  const handleImportSuccess = (detail: DatasetDetailResponse) => {
    refetch();
    navigate(`/datasets/${detail.dataset.dataset_id}`);
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      {/* Header */}
      <PageHeader
        title="Data Management"
        breadcrumbs={[
          { label: 'Data Management' }
        ]}
        actions={
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => refetch()}
              disabled={isLoading}
              className="p-2 rounded-xl bg-dark-850 hover:bg-dark-800 border border-dark-700 text-slate-400 hover:text-slate-200 transition"
              title="Refresh Datasets"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-brand-400' : ''}`} />
            </button>
            <button
              onClick={() => setIsImportModalOpen(true)}
              className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              <span>Import Dataset</span>
            </button>
          </div>
        }
      />

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* KPI Metrics Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Card 1: Total Datasets */}
          <div className="p-4 rounded-2xl bg-dark-900 border border-dark-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-[11px] font-bold uppercase tracking-wider">Total Managed Datasets</span>
              <Database className="w-4 h-4 text-brand-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-slate-100 font-mono tracking-tight">{metrics.totalDatasetsCount}</span>
              <span className="text-xs text-slate-400">Datasets</span>
              <span className="text-slate-600">•</span>
              <span className="text-xs text-brand-400 font-mono font-bold">{metrics.totalArtifactsCount}</span>
              <span className="text-xs text-slate-400">Artifacts</span>
            </div>
          </div>

          {/* Card 2: Model-Ready Feature Sets */}
          <div className="p-4 rounded-2xl bg-dark-900 border border-dark-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-[11px] font-bold uppercase tracking-wider">Model-Ready Datasets</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-slate-100 font-mono tracking-tight">{metrics.readyDatasetsCount}</span>
              <span className="text-xs text-slate-400">Datasets Ready</span>
            </div>
            <div className="flex items-center justify-between text-[11px] pt-1 border-t border-dark-850">
              <span className="text-purple-400 font-medium">Preprocessed</span>
            </div>
          </div>

          {/* Card 3: Quality Score */}
          <div className="p-4 rounded-2xl bg-dark-900 border border-dark-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-[11px] font-bold uppercase tracking-wider">Average Data Quality</span>
              <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                OPTIMAL
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-emerald-400 font-mono tracking-tight">94.8</span>
              <span className="text-xs text-slate-400 font-mono">/ 100</span>
            </div>
            <div className="space-y-1">
              <div className="h-1.5 w-full bg-dark-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 w-[94.8%] rounded-full shadow-glow-emerald" />
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                <span>98.2% schema pass rate</span>
                <span className="text-emerald-400">0 critical drift</span>
              </div>
            </div>
          </div>
        </div>

        {/* Filter Bar Controls */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Stage Tabs */}
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-dark-900 border border-dark-800">
            <button
              onClick={() => setSelectedStageTab('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${selectedStageTab === 'all'
                ? 'bg-brand-500 text-white font-bold shadow-glow-blue'
                : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              All ({metrics.totalDatasetsCount})
            </button>
            <button
              onClick={() => setSelectedStageTab('raw')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${selectedStageTab === 'raw'
                ? 'bg-amber-600 text-white font-bold'
                : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              Raw ({metrics.rawCount})
            </button>
            <button
              onClick={() => setSelectedStageTab('mapped')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${selectedStageTab === 'mapped'
                ? 'bg-emerald-600 text-white font-bold'
                : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              Mapped ({metrics.mappedCount})
            </button>
            <button
              onClick={() => setSelectedStageTab('ready')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${selectedStageTab === 'ready'
                ? 'bg-purple-600 text-white font-bold'
                : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              Model Ready ({metrics.readyDatasetsCount})
            </button>
          </div>

          {/* Search Box */}
          <div className="relative w-full md:w-80">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Tìm kiếm dataset theo tên, mô tả..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-dark-900 border border-dark-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500"
            />
          </div>
        </div>

        {/* Datasets Catalog Table */}
        <div className="border border-dark-800 rounded-2xl overflow-hidden bg-dark-900/60 shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
                  <th className="py-3.5 px-4 w-10">
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={toggleSelectAll}
                      className="rounded border-dark-700 text-brand-500 focus:ring-brand-500"
                    />
                  </th>
                  <th className="py-3.5 px-4 font-semibold">Tên Dataset</th>
                  <th className="py-3.5 px-4 font-semibold">Phân loại dữ liệu</th>
                  <th className="py-3.5 px-4 font-semibold">PII</th>
                  <th className="py-3.5 px-4 font-semibold">Stage mới nhất</th>
                  <th className="py-3.5 px-4 font-semibold">Quality Score</th>
                  <th className="py-3.5 px-4 font-semibold">Artifacts</th>
                  <th className="py-3.5 px-4 font-semibold">Thời gian tạo</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-850">
                {filteredDatasets.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-12 text-center text-slate-500">
                      Không tìm thấy tập dữ liệu nào phù hợp.
                    </td>
                  </tr>
                ) : (
                  filteredDatasets.map((dataset) => {
                    const isChecked = selectedIds.includes(dataset.dataset_id);
                    const stage = dataset.latest_stage || 'RAW';
                    const score = dataset.quality_score;

                    return (
                      <tr
                        key={dataset.dataset_id}
                        onClick={() => navigate(`/datasets/${dataset.dataset_id}`)}
                        className={`hover:bg-dark-850/60 transition group cursor-pointer ${isChecked ? 'bg-brand-500/5' : ''
                          }`}
                      >
                        {/* Checkbox */}
                        <td className="py-3.5 px-4" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleSelectRow(dataset.dataset_id)}
                            className="rounded border-dark-700 text-brand-500 focus:ring-brand-500"
                          />
                        </td>

                        {/* Tên Dataset & Description */}
                        <td className="py-3.5 px-4">
                          <div className="space-y-0.5">
                            <div className="font-bold text-slate-100 font-mono group-hover:text-brand-300 transition">
                              {dataset.dataset_name}
                            </div>
                            <div className="text-[11px] text-slate-400 line-clamp-1">
                              {dataset.display_name || dataset.description || 'Chưa có mô tả'}
                            </div>
                          </div>
                        </td>

                        {/* Phân loại dữ liệu */}
                        <td className="py-3.5 px-4 font-mono">
                          <span className="px-2 py-0.5 rounded text-[10px] bg-dark-800 border border-dark-700 text-slate-300">
                            {dataset.data_classification || 'INTERNAL'}
                          </span>
                        </td>

                        {/* PII */}
                        <td className="py-3.5 px-4 font-mono">
                          {dataset.contains_pii ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/30 text-[10px]">
                              <ShieldAlert className="w-3 h-3 text-rose-400" />
                              PII
                            </span>
                          ) : (
                            <span className="text-[10px] text-slate-500">None</span>
                          )}
                        </td>

                        {/* Stage mới nhất */}
                        <td className="py-3.5 px-4">
                          <span className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${stage === 'PRE_PROCESSED' || stage === 'FEATURE_ENGINEERED'
                            ? 'bg-purple-500/15 text-purple-300 border-purple-500/40 shadow-glow-purple'
                            : stage === 'MAPPED'
                              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                              : 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                            }`}>
                            {stage}
                          </span>
                        </td>

                        {/* Quality Score */}
                        <td className="py-3.5 px-4 font-mono">
                          {score !== null && score !== undefined ? (
                            <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-[10px] text-emerald-300 font-bold">
                              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                              <span>{score.toFixed(1)}/100</span>
                            </div>
                          ) : (
                            <span className="text-[10px] text-slate-500">N/A</span>
                          )}
                        </td>

                        {/* Artifacts Count */}
                        <td className="py-3.5 px-4 font-mono text-slate-300">
                          <span className="flex items-center gap-1.5">
                            <Layers className="w-3.5 h-3.5 text-slate-500" />
                            {dataset.artifacts_count || 1} versions
                          </span>
                        </td>

                        {/* Thời gian tạo */}
                        <td className="py-3.5 px-4 text-slate-400 text-[11px] font-mono">
                          {dataset.created_at ? new Date(dataset.created_at).toLocaleDateString() : 'Recent'}
                        </td>

                        {/* Row Actions: Chỉ Delete và Open Detail */}
                        <td className="py-3.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-2">
                            {/* Open Detail Button */}
                            <button
                              onClick={() => navigate(`/datasets/${dataset.dataset_id}`)}
                              className="px-3 py-1.5 rounded-lg bg-brand-500/15 hover:bg-brand-500/25 border border-brand-500/40 text-brand-300 text-xs font-semibold transition flex items-center gap-1"
                            >
                              <span>Open Detail</span>
                              <ArrowRight className="w-3 h-3" />
                            </button>

                            {/* Delete Button */}
                            <button
                              onClick={(e) => deleteDataset(dataset.dataset_id, e)}
                              title="Delete Dataset"
                              className="p-1.5 rounded-lg bg-dark-800 hover:bg-rose-500/20 border border-dark-700 text-slate-400 hover:text-rose-400 transition"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Import Dataset Modal */}
      <ImportDatasetModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onSuccess={handleImportSuccess}
        defaultProjectId={currentProjectId}
      />
    </div>
  );
};
