import { useState, useEffect, useMemo, useRef } from 'react';
import {
  Sparkles,
  AlertTriangle,
  Clock,
  DollarSign,
  Activity,
  Database,
  Info
} from 'lucide-react';
import type {
  DatasetArtifactResponse,
  FeatureEngineeringConfig
} from '../../../types/dataset';

interface FeatureEngineeringWorkspaceProps {
  mappedArtifact: DatasetArtifactResponse | null;
  feArtifact: DatasetArtifactResponse | null;
  onConfigChange?: (config: FeatureEngineeringConfig) => void;
  executionError?: string | null;
}

export const FeatureEngineeringWorkspace = ({
  mappedArtifact,
  feArtifact,
  onConfigChange,
  executionError = null,
}: FeatureEngineeringWorkspaceProps) => {
  // Generator toggles
  const [enableHourOfDay, setEnableHourOfDay] = useState(true);
  const [enableAmountRatios, setEnableAmountRatios] = useState(true);
  const [enableVelocity, setEnableVelocity] = useState(true);
  const [velocity1h, setVelocity1h] = useState(true);
  const [velocity24h, setVelocity24h] = useState(true);
  const [velocity168h, setVelocity168h] = useState(true);

  const onConfigChangeRef = useRef(onConfigChange);
  useEffect(() => {
    onConfigChangeRef.current = onConfigChange;
  }, [onConfigChange]);

  // Sync config with parent on change
  useEffect(() => {
    const activeWindows: number[] = [];
    if (velocity1h) activeWindows.push(1);
    if (velocity24h) activeWindows.push(24);
    if (velocity168h) activeWindows.push(168);

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
      enable_amount_ratios: enableAmountRatios,
      enable_hour_of_day: enableHourOfDay,
      enable_velocity_features: enableVelocity && activeWindows.length > 0,
      velocity_windows: activeWindows.length > 0 ? activeWindows : [1, 24, 168],
    };

    onConfigChangeRef.current?.(payload);
  }, [
    enableHourOfDay,
    enableAmountRatios,
    enableVelocity,
    velocity1h,
    velocity24h,
    velocity168h,
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

  const activeGeneratorsCount =
    (enableHourOfDay ? 1 : 0) +
    (enableAmountRatios ? 1 : 0) +
    (enableVelocity ? 1 : 0);

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
              <span className="font-semibold text-slate-200 block">Làm giàu đặc trưng hành vi (Feature Engineering)</span>
              <span className="text-slate-400 text-[11px]">
                Chọn các bộ trích xuất đặc trưng phù hợp bên dưới, sau đó nhấn nút <strong>&ldquo;Run Feature Engineering&rdquo;</strong> trên thanh tiêu đề để thực thi.
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded-full text-[11px] font-mono font-medium bg-purple-500/15 text-purple-300 border border-purple-500/30">
              {activeGeneratorsCount} Bộ đặc trưng kích hoạt
            </span>
          </div>
        </div>

        {/* Feature Engineering Generators Configuration */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Generator 1: Temporal / Hour of Day */}
          <div className={`p-5 rounded-2xl border transition flex flex-col justify-between ${enableHourOfDay ? 'bg-dark-900 border-purple-500/30 shadow-lg' : 'bg-dark-900/60 border-dark-800 opacity-70'
            }`}>
            <div className="space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-purple-500/15 text-purple-400 border border-purple-500/30">
                    <Clock className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-slate-100">Temporal & Diurnal</h3>
                    <span className="text-[10px] text-slate-400 font-mono">Time cyclicity signals</span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={enableHourOfDay}
                  onChange={(e) => setEnableHourOfDay(e.target.checked)}
                  className="rounded border-dark-700 bg-dark-950 text-purple-500 focus:ring-purple-500 h-4 w-4 mt-0.5 cursor-pointer"
                />
              </div>

              <p className="text-xs text-slate-400 leading-relaxed">
                Trích xuất chu kỳ thời gian từ trường timestamp. Phát hiện các hành vi gian lận phát sinh bất thường vào ban đêm hoặc ngoài giờ hành chính.
              </p>

              <div className="p-2.5 rounded-xl bg-dark-950 border border-dark-800 text-[11px] font-mono text-purple-300/90 space-y-1">
                <div className="flex items-center justify-between">
                  <span>trans_hour</span>
                  <span className="text-[10px] text-slate-500">Giờ (0 - 23)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>is_weekend</span>
                  <span className="text-[10px] text-slate-500">Cuối tuần (0/1)</span>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-dark-800/80 mt-4 flex items-center justify-between text-[11px]">
              <span className="text-slate-500">Trạng thái:</span>
              <span className={enableHourOfDay ? 'text-purple-400 font-medium' : 'text-slate-500'}>
                {enableHourOfDay ? 'Kích hoạt' : 'Bỏ qua'}
              </span>
            </div>
          </div>

          {/* Generator 2: Amount Ratios */}
          <div className={`p-5 rounded-2xl border transition flex flex-col justify-between ${enableAmountRatios ? 'bg-dark-900 border-purple-500/30 shadow-lg' : 'bg-dark-900/60 border-dark-800 opacity-70'
            }`}>
            <div className="space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                    <DollarSign className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-slate-100">Financial Relative Amounts</h3>
                    <span className="text-[10px] text-slate-400 font-mono">Normalized spending ratio</span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={enableAmountRatios}
                  onChange={(e) => setEnableAmountRatios(e.target.checked)}
                  className="rounded border-dark-700 bg-dark-950 text-purple-500 focus:ring-purple-500 h-4 w-4 mt-0.5 cursor-pointer"
                />
              </div>

              <p className="text-xs text-slate-400 leading-relaxed">
                Chuẩn hóa số tiền giao dịch so với trung bình quá khứ của người dùng và log-transform để kiểm soát độ lệch phân phối giá trị.
              </p>

              <div className="p-2.5 rounded-xl bg-dark-950 border border-dark-800 text-[11px] font-mono text-emerald-300/90 space-y-1">
                <div className="flex items-center justify-between">
                  <span>amt_to_user_avg_ratio</span>
                  <span className="text-[10px] text-slate-500">Tỷ lệ chi tiêu</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>log_amount</span>
                  <span className="text-[10px] text-slate-500">Log1p(Amount)</span>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-dark-800/80 mt-4 flex items-center justify-between text-[11px]">
              <span className="text-slate-500">Trạng thái:</span>
              <span className={enableAmountRatios ? 'text-emerald-400 font-medium' : 'text-slate-500'}>
                {enableAmountRatios ? 'Kích hoạt' : 'Bỏ qua'}
              </span>
            </div>
          </div>

          {/* Generator 3: Velocity & Frequency Windows */}
          <div className={`p-5 rounded-2xl border transition flex flex-col justify-between ${enableVelocity ? 'bg-dark-900 border-purple-500/30 shadow-lg' : 'bg-dark-900/60 border-dark-800 opacity-70'
            }`}>
            <div className="space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-blue-500/15 text-blue-400 border border-blue-500/30">
                    <Activity className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-slate-100">Velocity & Burst Signals</h3>
                    <span className="text-[10px] text-slate-400 font-mono">Rolling window aggregations</span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={enableVelocity}
                  onChange={(e) => setEnableVelocity(e.target.checked)}
                  className="rounded border-dark-700 bg-dark-950 text-purple-500 focus:ring-purple-500 h-4 w-4 mt-0.5 cursor-pointer"
                />
              </div>

              <p className="text-xs text-slate-400 leading-relaxed">
                Đo đếm tần suất giao dịch dồn dập (Burst Attack) và biến động số tiền trên các cửa sổ thời gian trượt theo user_id.
              </p>

              {enableVelocity && (
                <div className="space-y-2 pt-1">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Cửa sổ trượt hỗ trợ:</span>
                  <div className="grid grid-cols-3 gap-2">
                    <label className="flex items-center gap-1.5 p-2 rounded-lg bg-dark-950 border border-dark-800 text-[11px] font-mono text-slate-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={velocity1h}
                        onChange={(e) => setVelocity1h(e.target.checked)}
                        className="rounded border-dark-700 bg-dark-900 text-purple-500 h-3.5 w-3.5"
                      />
                      <span>1h</span>
                    </label>
                    <label className="flex items-center gap-1.5 p-2 rounded-lg bg-dark-950 border border-dark-800 text-[11px] font-mono text-slate-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={velocity24h}
                        onChange={(e) => setVelocity24h(e.target.checked)}
                        className="rounded border-dark-700 bg-dark-900 text-purple-500 h-3.5 w-3.5"
                      />
                      <span>24h</span>
                    </label>
                    <label className="flex items-center gap-1.5 p-2 rounded-lg bg-dark-950 border border-dark-800 text-[11px] font-mono text-slate-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={velocity168h}
                        onChange={(e) => setVelocity168h(e.target.checked)}
                        className="rounded border-dark-700 bg-dark-900 text-purple-500 h-3.5 w-3.5"
                      />
                      <span>7d (168h)</span>
                    </label>
                  </div>
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-dark-800/80 mt-4 flex items-center justify-between text-[11px]">
              <span className="text-slate-500">Trạng thái:</span>
              <span className={enableVelocity ? 'text-blue-400 font-medium' : 'text-slate-500'}>
                {enableVelocity ? 'Kích hoạt' : 'Bỏ qua'}
              </span>
            </div>
          </div>
        </div>

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
                    Enriched Dataset Artifact Generated
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
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Total Records</span>
                  <span className="text-xs font-bold font-mono text-slate-200">
                    {feArtifact.row_count?.toLocaleString() || mappedArtifact?.row_count?.toLocaleString() || '100,000'}
                  </span>
                </div>
                <div className="px-3 py-1.5 rounded-xl bg-dark-950 border border-dark-800 text-right">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Total Features</span>
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
              Chưa có Feature Engineered Artifact nào cho phiên bản hiện tại.
            </p>
            <p className="text-[11px] text-slate-500 max-w-md mx-auto">
              Kiểm tra cấu hình các bộ trích xuất đặc trưng phía trên và nhấn nút <strong>&ldquo;Run Feature Engineering&rdquo;</strong> ở góc trên bên phải để tạo đặc trưng mới.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default FeatureEngineeringWorkspace;
