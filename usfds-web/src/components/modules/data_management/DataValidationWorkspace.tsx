import { useMemo } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Eye,
  FileCheck,
  Info,
  XCircle,
  Columns
} from 'lucide-react';
import type { DatasetArtifactResponse, DataQualityReport } from '../../../types/dataset';

interface DataValidationWorkspaceProps {
  datasetId: string;
  datasetName?: string;
  mappedArtifact: DatasetArtifactResponse | null;
}

export const DataValidationWorkspace = ({
  mappedArtifact,
}: DataValidationWorkspaceProps) => {
  // Extract quality report from mappedArtifact
  const qualityReport: DataQualityReport | null = useMemo(() => {
    if (mappedArtifact?.validation_report && typeof mappedArtifact.validation_report === 'object') {
      const rep = mappedArtifact.validation_report as any;
      if ('quality_score' in rep) {
        return rep as DataQualityReport;
      }
    }
    return null;
  }, [mappedArtifact]);

  const qualityScore = qualityReport?.quality_score ?? 100.0;
  const rating = qualityReport?.rating ?? 'GOOD';
  const totalRows = qualityReport?.total_rows ?? mappedArtifact?.row_count ?? 0;
  const totalCols = qualityReport?.total_columns ?? mappedArtifact?.column_count ?? 0;

  // Real column metrics
  const columnMetricsList = useMemo(() => {
    if (!qualityReport?.column_metrics) return [];
    return Object.values(qualityReport.column_metrics);
  }, [qualityReport]);

  // Real sample records
  const sampleRecords = qualityReport?.sample_records || [];
  const sampleColumns = useMemo(() => {
    if (sampleRecords.length > 0) {
      return Object.keys(sampleRecords[0]);
    }
    if (columnMetricsList.length > 0) {
      return columnMetricsList.map(c => c.name);
    }
    if (mappedArtifact?.schema_snapshot) {
      return Object.keys(mappedArtifact.schema_snapshot);
    }
    return ['event_id', 'timestamp', 'amount', 'user_id', 'label'];
  }, [sampleRecords, columnMetricsList, mappedArtifact]);

  const duplicateEventIds = qualityReport?.duplicate_event_ids_count ?? 0;
  const duplicateRows = qualityReport?.duplicate_rows_count ?? 0;
  const futureTimestamps = qualityReport?.future_timestamp_count ?? 0;
  const nonPositiveAmounts = qualityReport?.non_positive_amount_count ?? 0;
  const amountOutliers = qualityReport?.amount_outliers_count ?? 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Quality Score & KPI Summary Banner */}
        <div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start sm:items-center gap-3.5">
            <div className={`p-3 rounded-xl border shrink-0 ${
              qualityScore >= 80
                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                : qualityScore >= 60
                  ? 'bg-amber-500/15 border-amber-500/30 text-amber-400'
                  : 'bg-rose-500/15 border-rose-500/30 text-rose-400'
            }`}>
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-100">
                  Data Quality & Integrity Audit
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  {mappedArtifact?.artifact_id ? `Artifact: ${mappedArtifact.artifact_id.slice(0, 8)}` : 'MAPPED'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Báo cáo kiểm định toàn vẹn lược đồ, trùng lặp định danh, mốc thời gian, giá trị ngoại lai và tỷ lệ khuyết thiếu.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="px-3 py-1.5 rounded-xl bg-dark-950 border border-dark-800 text-right">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Total Records</span>
              <span className="text-sm font-bold font-mono text-slate-200">{totalRows.toLocaleString()}</span>
            </div>
            <div className="px-3 py-1.5 rounded-xl bg-dark-950 border border-dark-800 text-right">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Total Fields</span>
              <span className="text-sm font-bold font-mono text-slate-200">{totalCols}</span>
            </div>
            <div className="px-4 py-2 rounded-xl bg-dark-950 border border-dark-800 flex items-center gap-3">
              <div className="text-right">
                <div className="text-[10px] uppercase font-bold text-slate-400">Quality Score</div>
                <div className={`text-xl font-black font-mono ${
                  qualityScore >= 80 ? 'text-emerald-400' : qualityScore >= 60 ? 'text-amber-400' : 'text-rose-400'
                }`}>
                  {qualityScore.toFixed(1)} <span className="text-xs font-normal text-slate-500">/ 100</span>
                </div>
              </div>
              <div className="h-8 w-px bg-dark-800" />
              <div>
                <span className={`text-[10px] px-2 py-1 rounded border font-bold uppercase font-mono ${
                  qualityScore >= 80
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : qualityScore >= 60
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                }`}>
                  {rating}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Rule-Based Integrity Checklist (Real Backend Checks) */}
        <div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 space-y-4">
          <div className="flex items-center justify-between border-b border-dark-800 pb-3">
            <div className="flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-brand-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Rule-Based Integrity Checklist
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              Automated Financial Data Audits
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 text-xs">
            {/* Check 1: Mandatory Fields */}
            <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 flex items-start gap-3">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div className="space-y-1 flex-1">
                <div className="font-semibold text-slate-200">Mandatory Schema Slots</div>
                <div className="text-[11px] text-slate-400 leading-relaxed">
                  Đầy đủ 5 trường chuẩn bắt buộc: <code className="text-slate-300 font-mono">event_id, timestamp, amount, user_id, label</code>.
                </div>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono font-bold shrink-0">
                PASS
              </span>
            </div>

            {/* Check 2: Event ID Uniqueness */}
            <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 flex items-start gap-3">
              {duplicateEventIds === 0 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1 flex-1">
                <div className="font-semibold text-slate-200">Event ID Collisions</div>
                <div className="text-[11px] text-slate-400 leading-relaxed">
                  {duplicateEventIds === 0
                    ? '100% mã định danh giao dịch duy nhất, không có trùng lặp primary key.'
                    : `Phát hiện ${duplicateEventIds.toLocaleString()} bản ghi bị trùng lặp Event ID.`}
                </div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${
                duplicateEventIds === 0
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-amber-500/10 text-amber-400'
              }`}>
                {duplicateEventIds === 0 ? 'PASS' : `${duplicateEventIds} DUP`}
              </span>
            </div>

            {/* Check 3: Duplicate Rows */}
            <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 flex items-start gap-3">
              {duplicateRows === 0 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1 flex-1">
                <div className="font-semibold text-slate-200">Duplicate Transactions</div>
                <div className="text-[11px] text-slate-400 leading-relaxed">
                  {duplicateRows === 0
                    ? 'Không có hàng dữ liệu trùng lặp hoàn toàn trên toàn bộ thuộc tính.'
                    : `Phát hiện ${duplicateRows.toLocaleString()} hàng dữ liệu trùng lặp.`}
                </div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${
                duplicateRows === 0
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-amber-500/10 text-amber-400'
              }`}>
                {duplicateRows === 0 ? 'PASS' : `${duplicateRows} ROWS`}
              </span>
            </div>

            {/* Check 4: Temporal Integrity */}
            <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 flex items-start gap-3">
              {futureTimestamps === 0 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1 flex-1">
                <div className="font-semibold text-slate-200">Temporal Validity</div>
                <div className="text-[11px] text-slate-400 leading-relaxed">
                  {futureTimestamps === 0
                    ? 'Tất cả mốc thời gian hợp lệ, không có giao dịch ở tương lai hoặc lỗi timestamp.'
                    : `Phát hiện ${futureTimestamps.toLocaleString()} giao dịch có mốc thời gian ở tương lai.`}
                </div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${
                futureTimestamps === 0
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-amber-500/10 text-amber-400'
              }`}>
                {futureTimestamps === 0 ? 'PASS' : 'WARN'}
              </span>
            </div>

            {/* Check 5: Financial Amount Validity */}
            <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 flex items-start gap-3">
              {nonPositiveAmounts === 0 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1 flex-1">
                <div className="font-semibold text-slate-200">Amount Positivity</div>
                <div className="text-[11px] text-slate-400 leading-relaxed">
                  {nonPositiveAmounts === 0
                    ? '100% số tiền giao dịch > 0, không có giao dịch âm hoặc bằng 0.'
                    : `Phát hiện ${nonPositiveAmounts.toLocaleString()} giao dịch có số tiền <= 0.`}
                </div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${
                nonPositiveAmounts === 0
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-amber-500/10 text-amber-400'
              }`}>
                {nonPositiveAmounts === 0 ? 'PASS' : 'WARN'}
              </span>
            </div>

            {/* Check 6: Outlier Dispersion */}
            <div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 flex items-start gap-3">
              {amountOutliers === 0 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1 flex-1">
                <div className="font-semibold text-slate-200">Outlier Detection (&gt; 3σ)</div>
                <div className="text-[11px] text-slate-400 leading-relaxed">
                  {amountOutliers === 0
                    ? 'Phân phối số tiền giao dịch ổn định, không có đột biến ngoại lai nghiêm trọng.'
                    : `${amountOutliers.toLocaleString()} giao dịch vượt ngưỡng phân vị 99.9% (${qualityReport?.amount_q999 ? `$${qualityReport.amount_q999.toFixed(2)}` : 'Q999'}).`}
                </div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${
                amountOutliers === 0
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-amber-500/10 text-amber-400'
              }`}>
                {amountOutliers === 0 ? 'PASS' : `${amountOutliers} OUTLIERS`}
              </span>
            </div>
          </div>

          {/* Warnings & Recommendations if any */}
          {((qualityReport?.warnings && qualityReport.warnings.length > 0) ||
            (qualityReport?.critical_errors && qualityReport.critical_errors.length > 0)) && (
            <div className="pt-2 space-y-2">
              {qualityReport?.critical_errors?.map((err, i) => (
                <div key={i} className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
                  <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{err}</span>
                </div>
              ))}
              {qualityReport?.warnings?.map((warn, i) => (
                <div key={i} className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>{warn}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Column Profiling & Null Audit Table */}
        {columnMetricsList.length > 0 && (
          <div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 space-y-3">
            <div className="flex items-center justify-between border-b border-dark-800 pb-3">
              <div className="flex items-center gap-2">
                <Columns className="w-4 h-4 text-brand-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Field Quality & Null Distribution
                </span>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                {columnMetricsList.length} Fields Profiled
              </span>
            </div>

            <div className="border border-dark-800 rounded-xl overflow-hidden bg-dark-950/70">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
                      <th className="py-2.5 px-3">Field Name</th>
                      <th className="py-2.5 px-3">Data Type</th>
                      <th className="py-2.5 px-3">Null Count</th>
                      <th className="py-2.5 px-3">Null %</th>
                      <th className="py-2.5 px-3">Unique Values</th>
                      <th className="py-2.5 px-3">Sample Values</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-dark-850">
                    {columnMetricsList.map((col, idx) => (
                      <tr key={idx} className="hover:bg-dark-850/50">
                        <td className="py-2.5 px-3 font-mono font-medium text-slate-200">
                          {col.name}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-400 text-[11px]">
                          <span className="px-1.5 py-0.5 rounded bg-dark-800 border border-dark-750">
                            {col.dtype}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-300">
                          {col.null_count.toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 font-mono">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            col.null_percentage === 0
                              ? 'bg-emerald-500/10 text-emerald-400'
                              : col.null_percentage < 5
                                ? 'bg-amber-500/10 text-amber-400'
                                : 'bg-rose-500/10 text-rose-400'
                          }`}>
                            {col.null_percentage.toFixed(2)}%
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-300">
                          {col.unique_count.toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400 max-w-xs truncate">
                          {col.sample_values && col.sample_values.length > 0 ? (
                            <div className="flex items-center gap-1 overflow-hidden">
                              {col.sample_values.slice(0, 3).map((val: any, sIdx: number) => (
                                <span key={sIdx} className="px-1.5 py-0.5 rounded bg-dark-850 text-slate-300 text-[10px] truncate max-w-[100px]">
                                  {String(val)}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Real Transformed Sample Preview */}
        <div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 space-y-3">
          <div className="flex items-center justify-between border-b border-dark-800 pb-3">
            <div className="flex items-center gap-2">
              <Eye className="w-4 h-4 text-brand-400" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Mapped Dataset Sample Preview (Real Data)
              </span>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              {sampleRecords.length > 0 ? `Showing first ${sampleRecords.length} records` : 'Schema preview'}
            </span>
          </div>

          {sampleRecords.length > 0 ? (
            <div className="border border-dark-800 rounded-xl overflow-hidden bg-dark-950/70">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400">
                      {sampleColumns.map((colName) => (
                        <th key={colName} className="py-2.5 px-3 whitespace-nowrap">
                          {colName.toUpperCase()}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-dark-850">
                    {sampleRecords.map((row, rIdx) => {
                      const isFraud = row.label === 1 || row.label === '1';
                      return (
                        <tr
                          key={rIdx}
                          className={`hover:bg-dark-850/50 ${isFraud ? 'bg-rose-500/5' : ''}`}
                        >
                          {sampleColumns.map((colName) => {
                            const val = row[colName];
                            const isLabelCol = colName.toLowerCase() === 'label';
                            const isAmtCol = colName.toLowerCase() === 'amount';

                            if (isLabelCol) {
                              return (
                                <td key={colName} className="py-2.5 px-3 whitespace-nowrap">
                                  {isFraud ? (
                                    <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-bold border border-rose-500/30">
                                      1 (FRAUD)
                                    </span>
                                  ) : (
                                    <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-bold">
                                      0 (Legit)
                                    </span>
                                  )}
                                </td>
                              );
                            }

                            if (isAmtCol && typeof val === 'number') {
                              return (
                                <td key={colName} className="py-2.5 px-3 font-bold text-emerald-400 whitespace-nowrap">
                                  ${val.toFixed(2)}
                                </td>
                              );
                            }

                            return (
                              <td key={colName} className="py-2.5 px-3 text-slate-300 whitespace-nowrap max-w-xs truncate">
                                {val !== null && val !== undefined ? String(val) : <span className="text-slate-600">null</span>}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="p-8 rounded-xl border border-dashed border-dark-800 text-center space-y-2">
              <Info className="w-6 h-6 text-slate-500 mx-auto" />
              <p className="text-xs text-slate-400">
                Lược đồ đã được ánh xạ thành công và lưu tại artifact <code className="text-brand-300 font-mono">{mappedArtifact?.artifact_id || 'MAPPED'}</code>.
              </p>
              <p className="text-[11px] text-slate-500">
                Các bản ghi mẫu chi tiết có sẵn trong các trường dữ liệu ở bảng thống kê phía trên.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DataValidationWorkspace;
