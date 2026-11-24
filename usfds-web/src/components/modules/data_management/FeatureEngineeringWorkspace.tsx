import { useState, useEffect, useMemo, useRef } from 'react';
import {
  Sparkles,
  AlertTriangle,
  Database,
  Info,
  Layers,
} from 'lucide-react';
import {
  useFeatureCatalog,
  useFeatureCompatibility,
  useFeatureSets,
} from '@/hooks/useFeatures';
import type {
  DatasetArtifactResponse,
  FeatureEngineeringConfig
} from '../../../types/dataset';

interface FeatureEngineeringWorkspaceProps {
  projectId?: string;
  datasetId?: string;
  mappedArtifact: DatasetArtifactResponse | null;
  feArtifact: DatasetArtifactResponse | null;
  onConfigChange?: (config: FeatureEngineeringConfig) => void;
  executionError?: string | null;
}

export const FeatureEngineeringWorkspace = ({
  projectId,
  datasetId,
  mappedArtifact,
  feArtifact,
  onConfigChange,
  executionError = null,
}: FeatureEngineeringWorkspaceProps) => {
  const [selectedFeatureSetIds, setSelectedFeatureSetIds] = useState<string[]>([]);
  const [selectedFeatureIds, setSelectedFeatureIds] = useState<string[]>([]);

  const { data: featureSets = [] } = useFeatureSets(projectId, true);
  const { data: featureCatalog = [] } = useFeatureCatalog(projectId, { include_builtin: true });
  const { data: compatibilityReport } = useFeatureCompatibility(
    projectId,
    datasetId,
    mappedArtifact?.artifact_id
  );

  const compatByFeatureId = useMemo(() => {
    const map = new Map<string, { status: string; missing_inputs: string[] }>();
    (compatibilityReport?.items || []).forEach((item) => {
      map.set(item.feature_id, { status: item.status, missing_inputs: item.missing_inputs || [] });
    });
    return map;
  }, [compatibilityReport]);

  const onConfigChangeRef = useRef(onConfigChange);
  useEffect(() => {
    onConfigChangeRef.current = onConfigChange;
  }, [onConfigChange]);

  // Sync config with parent on change
  useEffect(() => {
    const payload: FeatureEngineeringConfig = {
      split: {
        time_column: 'timestamp',
        target_column: 'label',
        test_size: 0.2,
      },
      cleansing: {
        drop_duplicates: true,
        missing_value_strategy: 'drop',
        outlier_clipping: false,
      },
      time_col: 'timestamp',
      amount_col: 'amount',
      user_id_col: 'user_id',
      enable_amount_ratios: false,
      enable_hour_of_day: false,
      enable_velocity_features: false,
      velocity_windows: [],
      ...(selectedFeatureSetIds.length > 0 ? { feature_set_ids: selectedFeatureSetIds } : {}),
      ...(selectedFeatureIds.length > 0 ? { feature_ids: selectedFeatureIds } : {}),
    };

    onConfigChangeRef.current?.(payload);
  }, [
    selectedFeatureSetIds,
    selectedFeatureIds,
  ]);

  // Extract generated columns from schema snapshot
  const generatedFeatureColumns = useMemo(() => {
    if (!feArtifact?.schema_snapshot) return [];
    const baseCols = new Set(
      mappedArtifact?.schema_snapshot
        ? Object.keys(mappedArtifact.schema_snapshot)
        : ['event_id', 'timestamp', 'amount', 'user_id', 'label']
    );

    return Object.entries(feArtifact.schema_snapshot).map(([col, dtype]) => ({
      name: col,
      dtype: String(dtype),
      isNew: !baseCols.has(col),
    }));
  }, [feArtifact, mappedArtifact]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Error notification */}
        {executionError && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{executionError}</span>
          </div>
        )}

        {/* Informational Guidance Banner */}
        <div className="p-4 rounded-2xl bg-dark-900 border border-dark-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <span className="font-semibold text-slate-200 block">Làm giàu đặc trưng hành vi</span>
              <span className="text-slate-400 text-[11px]">
                Chọn các bộ trích xuất đặc trưng phù hợp bên dưới, sau đó nhấn nút <strong>&ldquo;Chạy kỹ nghệ đặc trưng&rdquo;</strong> trên thanh tiêu đề để thực thi.
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded-full text-[11px] font-mono font-medium bg-purple-500/15 text-purple-300 border border-purple-500/30">
              {selectedFeatureSetIds.length} gói • {selectedFeatureIds.length} đặc trưng lẻ
            </span>
          </div>
        </div>

        {/* Feature Store: Feature Sets + Individual Features Selection */}
        {projectId && (
          <div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-dark-800 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-brand-400" />
                <div>
                  <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                    Kho đặc trưng &amp; Gói đặc trưng (Feature Store)
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Chọn 0..N gói đặc trưng hoặc các đặc trưng riêng lẻ từ Kho đặc trưng để biên dịch tự động.
                  </p>
                </div>
              </div>
              <div className="text-[11px] font-mono text-slate-400">
                Đã chọn: <span className="text-brand-300">{selectedFeatureSetIds.length} gói</span> •{' '}
                <span className="text-purple-300">{selectedFeatureIds.length} đặc trưng lẻ</span>
              </div>
            </div>

            {featureSets.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] font-semibold text-slate-300">Gói đặc trưng theo miền (Feature Sets)</div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {featureSets.map((fs) => {
                    const checked = selectedFeatureSetIds.includes(fs.feature_set_id);
                    return (
                      <label
                        key={fs.feature_set_id}
                        className={`p-3 rounded-xl border cursor-pointer flex items-start gap-2.5 text-xs transition ${
                          checked
                            ? 'bg-brand-500/10 border-brand-500/40'
                            : 'bg-dark-950 border-dark-800 hover:border-dark-700'
                        }`}
                      >
                        <input
                          type="checkbox"
                          aria-label={`Chọn gói ${fs.set_key}`}
                          checked={checked}
                          onChange={() =>
                            setSelectedFeatureSetIds((prev) =>
                              prev.includes(fs.feature_set_id)
                                ? prev.filter((id) => id !== fs.feature_set_id)
                                : [...prev, fs.feature_set_id]
                            )
                          }
                          className="mt-0.5"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-semibold text-slate-100 truncate">{fs.set_key}</span>
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-dark-900 border border-dark-700 text-slate-400 font-mono">
                              {fs.feature_ids.length}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 truncate mt-0.5">{fs.name}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            {featureCatalog.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] font-semibold text-slate-300">Đặc trưng chọn lẻ (Individual Features)</div>
                <div className="max-h-48 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-2 pr-1">
                  {featureCatalog.map((feat) => {
                    const checked = selectedFeatureIds.includes(feat.feature_id);
                    const compat = compatByFeatureId.get(feat.feature_id);
                    const isAvailable = !compat || compat.status === 'AVAILABLE';
                    return (
                      <label
                        key={feat.feature_id}
                        className={`p-2.5 rounded-xl border cursor-pointer flex items-center justify-between gap-2 text-xs transition ${
                          checked
                            ? 'bg-purple-500/10 border-purple-500/40'
                            : 'bg-dark-950 border-dark-800 hover:border-dark-700'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <input
                            type="checkbox"
                            aria-label={`Chọn đặc trưng ${feat.feature_key}`}
                            checked={checked}
                            onChange={() =>
                              setSelectedFeatureIds((prev) =>
                                prev.includes(feat.feature_id)
                                  ? prev.filter((id) => id !== feat.feature_id)
                                  : [...prev, feat.feature_id]
                              )
                            }
                          />
                          <div className="min-w-0">
                            <div className="font-mono text-slate-200 truncate">{feat.feature_key}</div>
                            <div className="text-[10px] text-slate-500 truncate">{feat.display_name}</div>
                          </div>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] shrink-0 border ${
                            isAvailable
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                              : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                          }`}
                        >
                          {isAvailable
                            ? 'Khả dụng'
                            : `Thiếu cột: ${(compat?.missing_inputs || []).join(', ')}`}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Execution Result / Artifact Summary (Displayed when feature engineering output is available) */}
        {feArtifact ? (
          <div className="p-5 rounded-2xl bg-dark-900 border border-purple-500/30 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-dark-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-purple-500/15 border border-purple-500/30 text-purple-400">
                  <Database className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-100 flex items-center gap-2">
                    Đã tạo artifact tập dữ liệu đã làm giàu
                    <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 text-[10px] font-mono font-bold">
                      {feArtifact.pipeline_stage}
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Artifact ID: <span className="text-slate-200">{feArtifact.artifact_id}</span>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="px-3 py-1.5 rounded-xl bg-dark-950 border border-dark-800 text-right">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Tổng số bản ghi</span>
                  <span className="text-xs font-bold font-mono text-slate-200">
                    {feArtifact.row_count?.toLocaleString() || mappedArtifact?.row_count?.toLocaleString() || '100,000'}
                  </span>
                </div>
                <div className="px-3 py-1.5 rounded-xl bg-dark-950 border border-dark-800 text-right">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Tổng số đặc trưng</span>
                  <span className="text-xs font-bold font-mono text-purple-300">
                    {feArtifact.column_count || generatedFeatureColumns.length}
                  </span>
                </div>
              </div>
            </div>

            {/* Generated Features Grid */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold uppercase text-slate-400 block tracking-wider">
                Danh sách đặc trưng trong Artifact:
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                {generatedFeatureColumns.map((col, idx) => (
                  <div
                    key={idx}
                    className={`p-2 rounded-xl border text-xs font-mono flex flex-col justify-between ${col.isNew
                        ? 'bg-purple-500/10 border-purple-500/30 text-purple-300'
                        : 'bg-dark-950 border-dark-800 text-slate-300'
                      }`}
                  >
                    <span className="font-semibold truncate">{col.name}</span>
                    <span className="text-[10px] text-slate-500 mt-1">{col.dtype}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 rounded-2xl bg-dark-900 border border-dashed border-dark-800 text-center space-y-2">
            <Info className="w-6 h-6 text-slate-500 mx-auto" />
            <p className="text-xs text-slate-300 font-medium">
              Chưa có artifact kỹ nghệ đặc trưng nào cho phiên bản hiện tại.
            </p>
            <p className="text-[11px] text-slate-500 max-w-md mx-auto">
              Kiểm tra cấu hình các bộ trích xuất đặc trưng phía trên và nhấn nút <strong>&ldquo;Chạy kỹ nghệ đặc trưng&rdquo;</strong> ở góc trên bên phải để tạo đặc trưng mới.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default FeatureEngineeringWorkspace;
