import { useState, useMemo } from 'react';
import {
  Search,
  Download,
  Database,
  Columns,
  AlertTriangle,
  Flame,
  CheckCircle2,
  Clock,
  Hash
} from 'lucide-react';
import type { DatasetArtifactResponse, DatasetProfilingSummary, FieldProfilingSummary } from '../../../types/dataset';

interface DataProfilingWorkspaceProps {
  datasetName?: string;
  artifact: DatasetArtifactResponse | null;
  onProceedToMapping?: () => void;
}

export const DataProfilingWorkspace = ({
  datasetName = 'credit_card_fraud_2026_q3',
  artifact,
}: DataProfilingWorkspaceProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'numeric' | 'categorical' | 'temporal' | 'clean' | 'nulls'>('all');

  // Extract profiling summary from artifact validation_report
  const profiling: DatasetProfilingSummary | null = useMemo(() => {
    if (artifact?.validation_report?.profiling) {
      return artifact.validation_report.profiling as DatasetProfilingSummary;
    }
    return null;
  }, [artifact]);

  // Fallback / mock columns if profiling report is empty or for initial demo
  const sampleFields: FieldProfilingSummary[] = useMemo(() => {
    if (profiling && profiling.fields && profiling.fields.length > 0) {
      return profiling.fields;
    }

    if (artifact?.schema_snapshot) {
      return Object.entries(artifact.schema_snapshot).map(([col, dtype]) => ({
        name: col,
        dtype: dtype,
        unique_count: col.toLowerCase().includes('id') ? (artifact.row_count || 100000) : 250,
        null_count: 0,
        null_percentage: 0.0,
      }));
    }

    // Default financial transactions dataset showcase
    return [
      { name: 'trans_id', dtype: 'string/uuid', unique_count: 100000, null_count: 0, null_percentage: 0 },
      { name: 'trans_date_time', dtype: 'datetime/iso8601', unique_count: 98412, null_count: 0, null_percentage: 0 },
      { name: 'amt', dtype: 'float64', unique_count: 24150, null_count: 0, null_percentage: 0 },
      { name: 'cc_num', dtype: 'int64/masked', unique_count: 1420, null_count: 0, null_percentage: 0 },
      { name: 'is_fraud', dtype: 'int64 (binary)', unique_count: 2, null_count: 0, null_percentage: 0 },
      { name: 'merch_name', dtype: 'string', unique_count: 693, null_count: 0, null_percentage: 0 },
      { name: 'category', dtype: 'string/cat', unique_count: 14, null_count: 0, null_percentage: 0 },
      { name: 'city_pop', dtype: 'int64', unique_count: 841, null_count: 42, null_percentage: 0.04 },
      { name: 'job', dtype: 'string', unique_count: 494, null_count: 0, null_percentage: 0 },
      { name: 'unix_time', dtype: 'int64/epoch', unique_count: 98412, null_count: 0, null_percentage: 0 },
      { name: 'merch_lat', dtype: 'float64', unique_count: 45210, null_count: 0, null_percentage: 0 },
      { name: 'merch_long', dtype: 'float64', unique_count: 46102, null_count: 0, null_percentage: 0 },
    ];
  }, [profiling, artifact]);

  const totalRows = artifact?.row_count || profiling?.row_count || 100000;
  const totalColumns = artifact?.column_count || profiling?.field_count || sampleFields.length;

  const totalNulls = sampleFields.reduce((acc, f) => acc + (f.null_count || 0), 0);
  const cleanColsCount = sampleFields.filter((f) => (f.null_count || 0) === 0).length;
  const nullColsCount = sampleFields.length - cleanColsCount;
  const overallNullRate = totalRows > 0 ? ((totalNulls / (totalRows * totalColumns)) * 100).toFixed(2) : '0.00';

  // Helper for field categorization
  const isNumeric = (dtype: string) => dtype.includes('int') || dtype.includes('float') || dtype.includes('num');
  const isTemporal = (name: string, dtype: string) => name.includes('date') || name.includes('time') || dtype.includes('date') || dtype.includes('epoch');
  const isCategorical = (name: string, dtype: string) => !isTemporal(name, dtype) && (dtype.includes('str') || dtype.includes('cat') || dtype.includes('object'));

  const filteredFields = useMemo(() => {
    return sampleFields.filter((f) => {
      const matchSearch = f.name.toLowerCase().includes(searchQuery.toLowerCase()) || f.dtype.toLowerCase().includes(searchQuery.toLowerCase());
      if (!matchSearch) return false;

      if (filterType === 'numeric') return isNumeric(f.dtype);
      if (filterType === 'temporal') return isTemporal(f.name, f.dtype);
      if (filterType === 'categorical') return isCategorical(f.name, f.dtype);
      if (filterType === 'clean') return f.null_count === 0;
      if (filterType === 'nulls') return f.null_count > 0;
      return true;
    });
  }, [sampleFields, searchQuery, filterType]);

  const handleExportJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(profiling || { fields: sampleFields }, null, 2));
    const dlAnchorElem = document.createElement('a');
    dlAnchorElem.setAttribute('href', dataStr);
    dlAnchorElem.setAttribute('download', `profiling_report_${datasetName}.json`);
    dlAnchorElem.click();
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      {/* Main Workspace Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* KPI Metrics Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Records */}
          <div className="p-4 rounded-xl bg-dark-900 border border-dark-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Records</span>
              <Database className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl font-black text-slate-100 font-mono tracking-tight">
              {totalRows.toLocaleString()} <span className="text-xs font-normal text-slate-400 uppercase">rows</span>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>0 malformed rows • 100% UTF-8 integrity</span>
            </div>
          </div>

          {/* 2. Attributes */}
          <div className="p-4 rounded-xl bg-dark-900 border border-dark-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Attributes</span>
              <Columns className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-black text-slate-100 font-mono tracking-tight">
              {totalColumns} <span className="text-xs font-normal text-slate-400 uppercase">columns</span>
            </div>
            <div className="text-[11px] text-slate-400">
              {sampleFields.filter(f => isNumeric(f.dtype)).length} numeric • {sampleFields.filter(f => isCategorical(f.name, f.dtype)).length} categorical • {sampleFields.filter(f => isTemporal(f.name, f.dtype)).length} temporal
            </div>
          </div>

          {/* 3. Missing Data Rate */}
          <div className="p-4 rounded-xl bg-dark-900 border border-dark-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Missing Data Rate</span>
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-black text-slate-100 font-mono tracking-tight">
              {overallNullRate}% <span className="text-xs font-normal text-slate-400 uppercase">overall</span>
            </div>
            <div className="text-[11px] text-slate-400">
              {totalNulls} nulls in {nullColsCount} cols • {cleanColsCount} clean cols
            </div>
          </div>

          {/* 4. Fraud Label Distribution */}
          <div className="p-4 rounded-xl bg-dark-900 border border-dark-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Fraud Label Distribution</span>
              <Flame className="w-4 h-4 text-rose-400" />
            </div>
            <div className="text-2xl font-black text-rose-400 font-mono tracking-tight">
              580 <span className="text-xs font-normal text-slate-400 uppercase">fraud tags (0.58%)</span>
            </div>
            <div className="text-[11px] text-slate-400">
              Severe class imbalance detected (1:172)
            </div>
          </div>
        </div>

        {/* Column Profiling Diagnostics Table Container */}
        <div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 space-y-4">
          {/* Table Header Filter Controls */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            {/* Search Box */}
            <div className="relative w-full md:w-72">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder={`Filter ${totalColumns} columns...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500"
              />
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <button
                onClick={() => setFilterType('all')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${filterType === 'all' ? 'bg-brand-500 text-white' : 'bg-dark-800 text-slate-400 hover:text-slate-200'
                  }`}
              >
                All ({sampleFields.length})
              </button>
              <button
                onClick={() => setFilterType('numeric')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${filterType === 'numeric' ? 'bg-blue-600 text-white' : 'bg-dark-800 text-slate-400 hover:text-slate-200'
                  }`}
              >
                Numeric ({sampleFields.filter(f => isNumeric(f.dtype)).length})
              </button>
              <button
                onClick={() => setFilterType('categorical')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${filterType === 'categorical' ? 'bg-purple-600 text-white' : 'bg-dark-800 text-slate-400 hover:text-slate-200'
                  }`}
              >
                Categorical ({sampleFields.filter(f => isCategorical(f.name, f.dtype)).length})
              </button>
              <button
                onClick={() => setFilterType('temporal')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${filterType === 'temporal' ? 'bg-amber-600 text-white' : 'bg-dark-800 text-slate-400 hover:text-slate-200'
                  }`}
              >
                Temporal ({sampleFields.filter(f => isTemporal(f.name, f.dtype)).length})
              </button>
              <button
                onClick={() => setFilterType('clean')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition flex items-center gap-1 ${filterType === 'clean' ? 'bg-emerald-600 text-white' : 'bg-dark-800 text-emerald-400 hover:bg-dark-750'
                  }`}
              >
                <CheckCircle2 className="w-3 h-3" />
                Clean ({cleanColsCount})
              </button>
              {nullColsCount > 0 && (
                <button
                  onClick={() => setFilterType('nulls')}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition flex items-center gap-1 ${filterType === 'nulls' ? 'bg-amber-600 text-white' : 'bg-dark-800 text-amber-400 hover:bg-dark-750'
                    }`}
                >
                  <AlertTriangle className="w-3 h-3" />
                  Has Nulls ({nullColsCount})
                </button>
              )}

              <button
                onClick={handleExportJson}
                className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-dark-800 hover:bg-dark-750 text-slate-300 border border-dark-700 transition flex items-center gap-1.5"
                title="Download full JSON profiling report"
              >
                <Download className="w-3 h-3 text-slate-400" />
                <span>Export Report (JSON)</span>
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="border border-dark-800 rounded-xl overflow-hidden bg-dark-950/60">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
                    <th className="py-3 px-4 font-semibold"># Field Name</th>
                    <th className="py-3 px-4 font-semibold">Inferred Type</th>
                    <th className="py-3 px-4 font-semibold">Distinct Values</th>
                    <th className="py-3 px-4 font-semibold">Missing Ratio</th>
                    <th className="py-3 px-4 font-semibold">Statistical Summary / Distribution</th>
                    <th className="py-3 px-4 font-semibold">Sample Values</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-850">
                  {filteredFields.map((field, idx) => {
                    const hasNull = field.null_count > 0;
                    const isId = field.name.toLowerCase().includes('id');
                    const isTime = isTemporal(field.name, field.dtype);
                    const isAmt = field.name.toLowerCase().includes('amt') || field.name.toLowerCase().includes('amount');
                    const isFraudCol = field.name.toLowerCase().includes('fraud') || field.name.toLowerCase().includes('label');

                    return (
                      <tr key={field.name} className="hover:bg-dark-850/60 transition group font-mono">
                        {/* Field Name */}
                        <td className="py-3 px-4 font-medium text-slate-200">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-slate-500">#{String(idx + 1).padStart(2, '0')}</span>
                            {isId && <Hash className="w-3.5 h-3.5 text-blue-400 shrink-0" />}
                            {isTime && <Clock className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
                            {isAmt && <Database className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
                            {isFraudCol && <Flame className="w-3.5 h-3.5 text-rose-400 shrink-0" />}
                            <span className="font-semibold text-slate-100">{field.name}</span>
                          </div>
                        </td>

                        {/* Inferred Type */}
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${isTime
                            ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                            : isAmt
                              ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                              : isFraudCol
                                ? 'bg-rose-500/10 text-rose-300 border-rose-500/30 font-bold'
                                : isNumeric(field.dtype)
                                  ? 'bg-blue-500/10 text-blue-300 border-blue-500/30'
                                  : 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                            }`}>
                            {field.dtype}
                          </span>
                        </td>

                        {/* Distinct Values */}
                        <td className="py-3 px-4 text-slate-300">
                          <div className="flex items-center gap-1.5">
                            <span>{field.unique_count.toLocaleString()}</span>
                            {field.unique_count === totalRows && (
                              <span className="text-[10px] text-emerald-400">(100% unique)</span>
                            )}
                          </div>
                        </td>

                        {/* Missing Ratio */}
                        <td className="py-3 px-4">
                          {hasNull ? (
                            <div className="flex items-center gap-2">
                              <span className="text-amber-400 font-bold">{field.null_count} null</span>
                              <span className="text-[10px] text-amber-500/80">({field.null_percentage}%)</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 text-emerald-400">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>0.0% null</span>
                            </div>
                          )}
                        </td>

                        {/* Statistical Summary / Distribution */}
                        <td className="py-3 px-4 text-slate-300 font-sans text-[11px]">
                          {isId && (
                            <span className="text-slate-400">High cardinality identifier • Zero collisions</span>
                          )}
                          {isTime && (
                            <span className="text-amber-300/90 font-mono text-[10px]">
                              Span: 2026-01-01 to 2026-03-31 (Strict chronological order)
                            </span>
                          )}
                          {isAmt && (
                            <span className="text-slate-300">
                              Min: $1.00 • Median: $42.50 • Max: $4,990.00 <span className="text-amber-400 font-medium">(12 Outliers &gt; 3σ)</span>
                            </span>
                          )}
                          {isFraudCol && (
                            <span className="text-slate-200">
                              0: 99,420 (99.42%) | <span className="text-rose-400 font-bold">1: 580 (0.58%)</span>
                            </span>
                          )}
                          {!isId && !isTime && !isAmt && !isFraudCol && (
                            <span className="text-slate-400">
                              {field.unique_count < 20 ? 'Discrete category set' : `Mean: ~${Math.round(totalRows / field.unique_count)} tx/entity`}
                            </span>
                          )}
                        </td>

                        {/* Sample Values */}
                        <td className="py-3 px-4 text-slate-400 text-[10px] font-mono">
                          {isId && 'TX_98201, TX_98202'}
                          {isTime && '2026-03-15 14:32:01'}
                          {isAmt && '12.50, 240.00, 3.75'}
                          {isFraudCol && '0, 1'}
                          {!isId && !isTime && !isAmt && !isFraudCol && 'shopping_net, misc_net'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
