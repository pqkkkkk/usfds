import { useState, useMemo, useEffect, useRef } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Plus,
  Trash2,
  Clock,
  DollarSign,
  User,
  Hash,
  Flame,
  Layers
} from 'lucide-react';
import type {
  DatasetArtifactResponse,
  DataMappingConfig
} from '../../../types/dataset';

interface SchemaMappingWorkspaceProps {
  rawArtifact: DatasetArtifactResponse | null;
  mappedArtifact: DatasetArtifactResponse | null;
  onConfigChange?: (config: DataMappingConfig, isValid: boolean) => void;
  saveError?: string | null;
}

export const SchemaMappingWorkspace = ({
  rawArtifact,
  mappedArtifact,
  onConfigChange,
  saveError: externalSaveError = null,
}: SchemaMappingWorkspaceProps) => {
  // Available raw columns from schema_snapshot or fallback
  const rawColumns = useMemo<string[]>(() => {
    if (rawArtifact?.schema_snapshot) {
      return Object.keys(rawArtifact.schema_snapshot);
    }
    return [
      'trans_id',
      'trans_date_time',
      'amt',
      'cc_num',
      'is_fraud',
      'merch_name',
      'category',
      'city_pop',
      'job',
      'unix_time'
    ];
  }, [rawArtifact]);

  // Form states matching DataMappingConfig
  const [eventIdCol, setEventIdCol] = useState(() => {
    return rawColumns.find(c => c.toLowerCase().includes('trans_id') || c.toLowerCase().includes('event_id')) || rawColumns[0] || 'trans_id';
  });

  const [timeCol, setTimeCol] = useState(() => {
    return rawColumns.find(c => c.toLowerCase().includes('date') || c.toLowerCase().includes('time')) || 'trans_date_time';
  });

  const [timeFormat, setTimeFormat] = useState<'auto' | 'iso' | 'epoch_s' | 'epoch_ms'>('auto');

  const [amountCol, setAmountCol] = useState(() => {
    return rawColumns.find(c => c.toLowerCase() === 'amt' || c.toLowerCase().includes('amount')) || 'amt';
  });

  const [userIdCol, setUserIdCol] = useState(() => {
    return rawColumns.find(c => c.toLowerCase().includes('cc_num') || c.toLowerCase().includes('user_id') || c.toLowerCase().includes('customer')) || 'cc_num';
  });

  const [targetCol, setTargetCol] = useState(() => {
    return rawColumns.find(c => c.toLowerCase().includes('fraud') || c.toLowerCase().includes('label') || c.toLowerCase().includes('class')) || 'is_fraud';
  });

  // Optional columns mapping { raw_col: canonical_col }
  const [optionalMappings, setOptionalMappings] = useState<Array<{ raw: string; target: string }>>([
    { raw: 'merch_name', target: 'merchant' },
    { raw: 'category', target: 'category' }
  ]);

  const displayError = externalSaveError;

  // Check how many mandatory slots are satisfied
  const mandatoryCount = [eventIdCol, timeCol, amountCol, userIdCol, targetCol].filter(Boolean).length;
  const isAllMandatorySatisfied = mandatoryCount === 5;

  const handleAddOptional = () => {
    const unmapped = rawColumns.find(
      c => c !== eventIdCol && c !== timeCol && c !== amountCol && c !== userIdCol && c !== targetCol &&
        !optionalMappings.some(m => m.raw === c)
    );
    if (unmapped) {
      setOptionalMappings([...optionalMappings, { raw: unmapped, target: unmapped.toLowerCase() }]);
    } else {
      setOptionalMappings([...optionalMappings, { raw: rawColumns[0] || '', target: 'custom_field' }]);
    }
  };

  const handleRemoveOptional = (index: number) => {
    setOptionalMappings(optionalMappings.filter((_, i) => i !== index));
  };

  const handleUpdateOptional = (index: number, key: 'raw' | 'target', value: string) => {
    const copy = [...optionalMappings];
    copy[index][key] = value;
    setOptionalMappings(copy);
  };

  const onConfigChangeRef = useRef(onConfigChange);
  useEffect(() => {
    onConfigChangeRef.current = onConfigChange;
  }, [onConfigChange]);

  // Notify parent container of configuration changes
  useEffect(() => {
    const optionalObj: Record<string, string> = {};
    optionalMappings.forEach(m => {
      if (m.raw && m.target) {
        optionalObj[m.raw] = m.target;
      }
    });

    const payload: DataMappingConfig = {
      event_id_column: eventIdCol,
      time_column: timeCol,
      amount_column: amountCol,
      user_id_column: userIdCol,
      target_column: targetCol,
      optional_columns: optionalObj,
      time_format: timeFormat,
    };

    onConfigChangeRef.current?.(payload, isAllMandatorySatisfied);
  }, [
    eventIdCol,
    timeCol,
    amountCol,
    userIdCol,
    targetCol,
    optionalMappings,
    timeFormat,
    isAllMandatorySatisfied,
  ]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      {/* Main Workspace Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {displayError && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{displayError}</span>
            </div>
          </div>
        )}

        {/* Lineage Branching Information */}
        <div className="p-3 rounded-xl bg-dark-900 border border-dark-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-slate-300">
            <Layers className="w-4 h-4 text-brand-400 shrink-0" />
            <span>
              {mappedArtifact ? (
                <>
                  <span className="text-slate-400">Phiên bản hiện tại:</span>{' '}
                  <code className="text-brand-300 font-mono bg-dark-950 px-1.5 py-0.5 rounded border border-dark-800">
                    {mappedArtifact.artifact_id}
                  </code>
                  . Bạn có thể điều chỉnh cấu hình và nhấn &ldquo;Validate Data&rdquo; trên thanh tiêu đề để xác thực và tạo artifact mới.
                </>
              ) : (
                <>
                  <span className="text-emerald-400 font-medium">Nhánh ánh xạ mới:</span>{' '}
                  Đang khởi tạo cấu hình từ Raw dataset{' '}
                  <code className="text-slate-300 font-mono bg-dark-950 px-1.5 py-0.5 rounded border border-dark-800">
                    {rawArtifact?.artifact_id || 'Raw Input'}
                  </code>
                  . Nhấn nút &ldquo;Validate Data&rdquo; trên thanh tiêu đề để xác thực và chuyển sang bước Validation Report.
                </>
              )}
            </span>
          </div>
        </div>

        {/* UNIFIED SCHEMA MAPPING TABLE */}
        <div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-dark-800 pb-3">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                Schema Field Mapping
                <span className="text-[10px] font-normal normal-case text-slate-500">
                  (Bind raw transaction fields to canonical targets and optional domain signals)
                </span>
              </h2>
            </div>
            <div className="flex items-center gap-3">
              <div className={`px-2.5 py-1 rounded-full text-[11px] font-mono font-medium border flex items-center gap-1.5 ${
                isAllMandatorySatisfied
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                  : 'bg-amber-500/15 text-amber-300 border-amber-500/40'
              }`}>
                <CheckCircle2 className="w-3 h-3" />
                <span>{mandatoryCount} / 5 Mandatory Slots</span>
              </div>
              <button
                type="button"
                onClick={handleAddOptional}
                className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-slate-300 border border-dark-700 text-xs font-medium transition flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5 text-brand-400" />
                <span>Add Optional Attribute</span>
              </button>
            </div>
          </div>

          {/* Unified Table */}
          <div className="border border-dark-800 rounded-xl overflow-hidden bg-dark-950/70">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
                    <th className="py-3 px-4 font-semibold w-1/4">Target Field (Canonical)</th>
                    <th className="py-3 px-4 font-semibold w-1/4">Source Column (RAW)</th>
                    <th className="py-3 px-4 font-semibold w-1/4">Parsing / Configuration</th>
                    <th className="py-3 px-4 font-semibold w-1/6">Sample Value</th>
                    <th className="py-3 px-4 font-semibold text-center w-12">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-850">
                  {/* SECTION HEADER: MANDATORY */}
                  <tr className="bg-dark-900/60 text-slate-400">
                    <td colSpan={5} className="py-2 px-4 text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                      Mandatory Core Slots (5 Required)
                    </td>
                  </tr>

                  {/* Row 1: event_id */}
                  <tr className="hover:bg-dark-900/40 transition">
                    <td className="py-3.5 px-4">
                      <div className="flex items-start gap-3">
                        <div className="p-1.5 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400 shrink-0 mt-0.5">
                          <Hash className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs font-bold text-slate-100">event_id</span>
                            <span className="text-rose-400 font-bold">*</span>
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">string/uuid</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">Unique Transaction Identifier</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
                        <select
                          value={eventIdCol}
                          onChange={(e) => setEventIdCol(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
                        >
                          {rawColumns.map((col) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      <span className="text-slate-500">Constraint:</span> Unique Primary Key
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-mono text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                        "TX_98201"
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">
                      —
                    </td>
                  </tr>

                  {/* Row 2: timestamp */}
                  <tr className="hover:bg-dark-900/40 transition">
                    <td className="py-3.5 px-4">
                      <div className="flex items-start gap-3">
                        <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0 mt-0.5">
                          <Clock className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs font-bold text-slate-100">timestamp</span>
                            <span className="text-rose-400 font-bold">*</span>
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">datetime</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">Transaction Event Timestamp</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
                        <select
                          value={timeCol}
                          onChange={(e) => setTimeCol(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
                        >
                          {rawColumns.map((col) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-500">Format:</span>
                        <select
                          value={timeFormat}
                          onChange={(e) => setTimeFormat(e.target.value as any)}
                          className="px-2 py-1 bg-dark-900 border border-dark-700 rounded text-xs font-mono text-amber-300 focus:outline-none"
                        >
                          <option value="auto">Auto Parse</option>
                          <option value="iso">ISO-8601 UTC</option>
                          <option value="epoch_s">Epoch Seconds</option>
                          <option value="epoch_ms">Epoch Milliseconds</option>
                        </select>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-mono text-xs text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                        "2026-09-15"
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">
                      —
                    </td>
                  </tr>

                  {/* Row 3: amount */}
                  <tr className="hover:bg-dark-900/40 transition">
                    <td className="py-3.5 px-4">
                      <div className="flex items-start gap-3">
                        <div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shrink-0 mt-0.5">
                          <DollarSign className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs font-bold text-slate-100">amount</span>
                            <span className="text-rose-400 font-bold">*</span>
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">float64</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">Monetary Value / Payment</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
                        <select
                          value={amountCol}
                          onChange={(e) => setAmountCol(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
                        >
                          {rawColumns.map((col) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      <span className="text-slate-500">Precision:</span> 2 Decimals ($ &gt; 0)
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-mono text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                        "$12.50"
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">
                      —
                    </td>
                  </tr>

                  {/* Row 4: user_id */}
                  <tr className="hover:bg-dark-900/40 transition">
                    <td className="py-3.5 px-4">
                      <div className="flex items-start gap-3">
                        <div className="p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shrink-0 mt-0.5">
                          <User className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs font-bold text-slate-100">user_id</span>
                            <span className="text-rose-400 font-bold">*</span>
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">string</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">Account / Card Token</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
                        <select
                          value={userIdCol}
                          onChange={(e) => setUserIdCol(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
                        >
                          {rawColumns.map((col) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      <span className="text-slate-500">Security:</span> PCI-DSS Tokenized
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-mono text-xs text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                        "4000-xxxx-1204"
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">
                      —
                    </td>
                  </tr>

                  {/* Row 5: label */}
                  <tr className="hover:bg-dark-900/40 transition">
                    <td className="py-3.5 px-4">
                      <div className="flex items-start gap-3">
                        <div className="p-1.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 shrink-0 mt-0.5">
                          <Flame className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs font-bold text-slate-100">label</span>
                            <span className="text-rose-400 font-bold">*</span>
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-dark-800 text-slate-400 border border-dark-700">binary (0/1)</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">Ground Truth Fraud Tag</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
                        <select
                          value={targetCol}
                          onChange={(e) => setTargetCol(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
                        >
                          {rawColumns.map((col) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      <span className="text-slate-500">Distribution:</span> 0: 99.4% | 1: 0.6%
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-mono text-xs text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                        "0 (Legit) / 1 (Fraud)"
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center text-slate-600 font-mono text-xs">
                      —
                    </td>
                  </tr>

                  {/* SECTION HEADER: OPTIONAL DOMAIN ATTRIBUTES */}
                  <tr className="bg-dark-900/60 text-slate-400">
                    <td colSpan={5} className="py-2.5 px-4">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                          Optional Domain Attributes ({optionalMappings.length} Configured)
                        </span>
                        <span className="text-[11px] text-slate-500 normal-case">
                          Retain contextual signals into normalized parquet.
                        </span>
                      </div>
                    </td>
                  </tr>

                  {/* OPTIONAL ROWS */}
                  {optionalMappings.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 px-4 text-center text-xs text-slate-500 font-mono">
                        No optional attributes configured. Click "Add Optional Attribute" to preserve contextual signals.
                      </td>
                    </tr>
                  ) : (
                    optionalMappings.map((m, idx) => (
                      <tr key={idx} className="hover:bg-dark-900/40 transition">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-3">
                            <div className="p-1.5 rounded-lg bg-dark-800 border border-dark-700 text-slate-400 shrink-0">
                              <Layers className="w-3.5 h-3.5" />
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-1.5">
                                <input
                                  type="text"
                                  value={m.target}
                                  onChange={(e) => handleUpdateOptional(idx, 'target', e.target.value)}
                                  placeholder="target_column_name"
                                  className="w-full px-2 py-1 bg-dark-900 border border-dark-700 rounded text-xs font-mono text-brand-300 focus:outline-none focus:border-brand-500"
                                />
                              </div>
                              <span className="text-[10px] text-slate-500 mt-0.5 block">Contextual Signal</span>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <ArrowRight className="w-3.5 h-3.5 text-slate-500 hidden sm:block shrink-0" />
                            <select
                              value={m.raw}
                              onChange={(e) => handleUpdateOptional(idx, 'raw', e.target.value)}
                              className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
                            >
                              {rawColumns.map((col) => (
                                <option key={col} value={col}>{col}</option>
                              ))}
                            </select>
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono text-xs text-slate-400">
                          <span className="text-slate-500">Transform:</span> Passthrough / Inferred Type
                        </td>
                        <td className="py-3 px-4 font-mono text-xs text-slate-300">
                          <span className="px-2 py-0.5 rounded bg-dark-800 border border-dark-750 text-slate-400">
                            Auto Inferred
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            type="button"
                            onClick={() => handleRemoveOptional(idx)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition"
                            title="Remove attribute"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SchemaMappingWorkspace;
