import React, { useState } from 'react';
import {
  Play,
  RotateCcw,
  CheckCircle2,
  FileCode2,
  Database,
  Calendar,
  X,
  SlidersHorizontal,
} from 'lucide-react';
import type { RuleResponse, RuleGroup, RuleAction } from '../../../types/rule';

interface RuleDryRunWorkspaceProps {
  ruleCode: string;
  ruleName: string;
  ruleAction: RuleAction;
  conditionGroup?: RuleGroup;
  currentRule?: RuleResponse | null;
}

interface SimulationTransaction {
  event_id: string;
  timestamp: string;
  amount: number;
  user_id: string;
  ground_truth: 1 | 0; // 1 = FRAUD, 0 = LEGIT
  matched_clauses: string[];
  features: Record<string, any>;
}

const SAMPLE_TRANSACTIONS: SimulationTransaction[] = [
  {
    event_id: 'TX-883120',
    timestamp: '2026-08-14 02:14:09',
    amount: 4980.0,
    user_id: 'U8892',
    ground_truth: 1,
    matched_clauses: ['amount > 2000', 'is_new_device = true', 'category = electronics'],
    features: {
      amount: 4980.0,
      is_new_device: true,
      category: 'electronics',
      velocity_1h: 3,
      ip_country: 'VN',
      risk_score: 0.89,
    },
  },
  {
    event_id: 'TX-883144',
    timestamp: '2026-08-14 02:18:41',
    amount: 2450.0,
    user_id: 'U4129',
    ground_truth: 1,
    matched_clauses: ['amount > 2000', 'velocity_1h >= 5', 'category = gift_card'],
    features: {
      amount: 2450.0,
      is_new_device: true,
      category: 'gift_card',
      velocity_1h: 6,
      ip_country: 'US',
      risk_score: 0.94,
    },
  },
  {
    event_id: 'TX-883201',
    timestamp: '2026-08-14 02:45:10',
    amount: 3120.0,
    user_id: 'U0492',
    ground_truth: 0,
    matched_clauses: ['amount > 2000', 'is_new_device = true', 'category = electronics'],
    features: {
      amount: 3120.0,
      is_new_device: true,
      category: 'electronics',
      velocity_1h: 1,
      ip_country: 'VN',
      risk_score: 0.42,
    },
  },
  {
    event_id: 'TX-883319',
    timestamp: '2026-08-14 03:02:18',
    amount: 6700.0,
    user_id: 'U7102',
    ground_truth: 1,
    matched_clauses: ['amount > 2000', 'category = crypto'],
    features: {
      amount: 6700.0,
      is_new_device: false,
      category: 'crypto',
      velocity_1h: 4,
      ip_country: 'SG',
      risk_score: 0.96,
    },
  },
  {
    event_id: 'TX-883405',
    timestamp: '2026-08-14 03:22:45',
    amount: 2150.0,
    user_id: 'U1184',
    ground_truth: 0,
    matched_clauses: ['amount > 2000', 'is_new_device = true'],
    features: {
      amount: 2150.0,
      is_new_device: true,
      category: 'travel',
      velocity_1h: 2,
      ip_country: 'VN',
      risk_score: 0.38,
    },
  },
  {
    event_id: 'TX-883510',
    timestamp: '2026-08-14 04:10:02',
    amount: 5200.0,
    user_id: 'U9921',
    ground_truth: 1,
    matched_clauses: ['amount > 2000', 'velocity_1h >= 5'],
    features: {
      amount: 5200.0,
      is_new_device: true,
      category: 'gaming',
      velocity_1h: 7,
      ip_country: 'TH',
      risk_score: 0.91,
    },
  },
];

export const RuleDryRunWorkspace: React.FC<RuleDryRunWorkspaceProps> = ({
  ruleCode,
  ruleName,
  ruleAction,
}) => {
  const [selectedDataset, setSelectedDataset] = useState('cc_fraud_2026_mapped');
  const [testWindow, setTestWindow] = useState('2026_q3');
  const [isRunning, setIsRunning] = useState(false);
  const [filterTab, setFilterTab] = useState<'ALL' | 'TP' | 'FP'>('ALL');
  const [inspectingTx, setInspectingTx] = useState<SimulationTransaction | null>(null);

  const handleRunSimulation = () => {
    setIsRunning(true);
    setTimeout(() => {
      setIsRunning(false);
    }, 1200);
  };

  const filteredTransactions = SAMPLE_TRANSACTIONS.filter((tx) => {
    if (filterTab === 'TP') return tx.ground_truth === 1;
    if (filterTab === 'FP') return tx.ground_truth === 0;
    return true;
  });

  return (
    <div className="flex-1 p-6 space-y-5 overflow-y-auto bg-dark-950">
      {/* 1. Target Dataset & Configuration Bar */}
      <div className="bg-dark-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          {/* Target Rule Summary Pill */}
          <div className="border-r border-slate-800 pr-4 hidden lg:block">
            <span className="block text-[10px] font-mono uppercase text-slate-500 mb-0.5">
              TARGET RULE
            </span>
            <div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 font-mono">
              <span className="text-brand-400 font-bold">{ruleCode}</span>
              <span className="text-slate-400 font-normal truncate max-w-[200px]" title={ruleName}>
                {ruleName}
              </span>
            </div>
          </div>

          {/* Dataset Selector */}
          <div>
            <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1 flex items-center gap-1.5">
              <Database className="w-3 h-3 text-brand-400" />
              <span>EVALUATION DATASET</span>
            </label>
            <div className="relative">
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                className="bg-dark-850 border border-slate-800 hover:border-brand-500/60 text-slate-200 text-xs font-mono rounded-lg px-3 py-2 pr-8 focus:outline-none focus:border-brand-500 cursor-pointer transition appearance-none"
              >
                <option value="cc_fraud_2026_mapped">
                  cc_fraud_2026 / Artifact #2 (MAPPED, labeled, 100k rows)
                </option>
                <option value="ecommerce_q3_val">
                  ecommerce_transactions_2026 / Validation Set (50k rows)
                </option>
                <option value="high_volume_stress">
                  production_replay_stream / High Volume (300k rows)
                </option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
                <SlidersHorizontal className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>

          {/* Historical Test Window */}
          <div>
            <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1 flex items-center gap-1.5">
              <Calendar className="w-3 h-3 text-slate-400" />
              <span>HISTORICAL TEST WINDOW</span>
            </label>
            <div className="relative">
              <select
                value={testWindow}
                onChange={(e) => setTestWindow(e.target.value)}
                className="bg-dark-850 border border-slate-800 hover:border-brand-500/60 text-slate-200 text-xs font-mono rounded-lg px-3 py-2 pr-8 focus:outline-none focus:border-brand-500 cursor-pointer transition appearance-none"
              >
                <option value="2026_q3">2026-07-01 → 2026-09-30 (Q3 Benchmark)</option>
                <option value="2026_h1">2026-01-01 → 2026-06-30 (H1 Historical)</option>
                <option value="last_30_days">Last 30 Days (Rolling Window)</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
                <Calendar className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRunSimulation}
            disabled={isRunning}
            className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2 cursor-pointer"
          >
            {isRunning ? (
              <RotateCcw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-white" />
            )}
            <span>{isRunning ? 'Đang thực thi Dry Run...' : 'Run Dry Run Simulation'}</span>
          </button>
        </div>
      </div>

      {/* 2. Telemetry KPI Cards (6-card Grid theo Stitch SUC-12) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Card 1: Total Rule Hits */}
        <div className="bg-dark-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all">
          <div className="text-[10px] font-mono uppercase text-slate-400 mb-1">TOTAL RULE HITS</div>
          <div className="text-2xl font-bold font-mono text-white tracking-tight">1,284</div>
          <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <span className="text-blue-400 font-mono font-medium">0.43%</span> hit rate of 300k txns
          </div>
        </div>

        {/* Card 2: Precision */}
        <div className="bg-dark-900 border border-emerald-500/30 hover:border-emerald-500/50 rounded-xl p-3.5 transition-all bg-gradient-to-b from-emerald-950/20 to-transparent">
          <div className="text-[10px] font-mono uppercase text-emerald-400/90 mb-1 flex items-center justify-between">
            <span>PRECISION</span>
            <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1 py-0.5 rounded font-mono font-semibold">
              ≥ 0.30 REQ
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 tracking-tight">0.460</div>
          <div className="text-[11px] text-slate-400 mt-1">
            <span className="text-emerald-400 font-mono font-medium">46.0%</span> verified fraud hits
          </div>
        </div>

        {/* Card 3: Recall */}
        <div className="bg-dark-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all">
          <div className="text-[10px] font-mono uppercase text-slate-400 mb-1">RECALL</div>
          <div className="text-2xl font-bold font-mono text-white tracking-tight">0.312</div>
          <div className="text-[11px] text-slate-400 mt-1">
            Catches <span className="text-slate-200 font-mono font-medium">31.2%</span> of all frauds
          </div>
        </div>

        {/* Card 4: False Positive Rate */}
        <div className="bg-dark-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all">
          <div className="text-[10px] font-mono uppercase text-slate-400 mb-1 flex items-center justify-between">
            <span>FALSE POSITIVE RATE</span>
            <span className="text-[9px] bg-slate-800 text-slate-400 px-1 py-0.5 rounded font-mono">
              ≤ 0.50% REQ
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 tracking-tight">0.23%</div>
          <div className="text-[11px] text-slate-400 mt-1">
            Low friction rate (694 FP)
          </div>
        </div>

        {/* Card 5: Daily Review Volume */}
        <div className="bg-dark-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all">
          <div className="text-[10px] font-mono uppercase text-slate-400 mb-1">TRIGGER VOLUME</div>
          <div className="text-2xl font-bold font-mono text-white tracking-tight">~14 / day</div>
          <div className="text-[11px] text-slate-400 mt-1">
            Action: <span className="text-amber-400 font-mono font-medium">{ruleAction}</span>
          </div>
        </div>

        {/* Card 6: Fraud Prevented */}
        <div className="bg-dark-900 border border-blue-500/30 hover:border-blue-500/50 rounded-xl p-3.5 transition-all bg-gradient-to-b from-blue-950/20 to-transparent">
          <div className="text-[10px] font-mono uppercase text-blue-400 mb-1">FRAUD PREVENTED</div>
          <div className="text-2xl font-bold font-mono text-blue-400 tracking-tight">$182,450</div>
          <div className="text-[11px] text-slate-400 mt-1">
            Total value true fraud caught
          </div>
        </div>
      </div>

      {/* 3. Sample Hits Inspection Matrix Table (Stitch SUC-12 Section 5) */}
      <div className="bg-dark-900 border border-slate-800 rounded-xl p-4 space-y-3 shadow-sm">
        {/* Table Toolbar & Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold font-mono uppercase text-slate-200">
              SAMPLE HITS INSPECTION MATRIX
            </span>
            <span className="text-[10px] font-mono text-slate-400 bg-dark-850 px-2 py-0.5 rounded border border-slate-800">
              Historical Dry Run Evaluation Logs
            </span>
          </div>

          {/* Filter Tabs */}
          <div className="flex items-center bg-dark-850 p-1 rounded-lg border border-slate-800 text-xs">
            <button
              type="button"
              onClick={() => setFilterTab('ALL')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
                filterTab === 'ALL'
                  ? 'bg-blue-600/20 text-blue-300 font-semibold border border-blue-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All Hits (1,284)
            </button>
            <button
              type="button"
              onClick={() => setFilterTab('TP')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
                filterTab === 'TP'
                  ? 'bg-emerald-600/20 text-emerald-300 font-semibold border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              True Positives (590)
            </button>
            <button
              type="button"
              onClick={() => setFilterTab('FP')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
                filterTab === 'FP'
                  ? 'bg-amber-600/20 text-amber-300 font-semibold border border-amber-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              False Positives (694)
            </button>
          </div>
        </div>

        {/* Table Viewport */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[10px] font-mono uppercase text-slate-400 border-b border-slate-800 bg-dark-950/60">
                <th className="py-2.5 px-3">EVENT_ID</th>
                <th className="py-2.5 px-3">TIMESTAMP</th>
                <th className="py-2.5 px-3">AMOUNT</th>
                <th className="py-2.5 px-3">USER_ID</th>
                <th className="py-2.5 px-3">GROUND TRUTH</th>
                <th className="py-2.5 px-3">MATCHED CLAUSES</th>
                <th className="py-2.5 px-3 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono text-[11px]">
              {filteredTransactions.map((tx) => (
                <tr
                  key={tx.event_id}
                  className={`hover:bg-dark-850/80 transition-colors ${
                    tx.ground_truth === 1 ? 'bg-emerald-950/10' : ''
                  }`}
                >
                  <td className="py-2.5 px-3 font-bold text-blue-400">{tx.event_id}</td>
                  <td className="py-2.5 px-3 text-slate-400">{tx.timestamp}</td>
                  <td className="py-2.5 px-3 text-white font-bold">
                    ${tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-slate-300">{tx.user_id}</td>
                  <td className="py-2.5 px-3">
                    {tx.ground_truth === 1 ? (
                      <span className="bg-rose-500/20 text-rose-400 border border-rose-500/40 px-2 py-0.5 rounded text-[10px] font-bold">
                        1 - FRAUD
                      </span>
                    ) : (
                      <span className="bg-slate-700/40 text-slate-300 border border-slate-600/40 px-2 py-0.5 rounded text-[10px] font-bold">
                        0 - LEGIT
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex flex-wrap gap-1 font-sans">
                      {tx.matched_clauses.map((clause, idx) => (
                        <span
                          key={idx}
                          className="bg-dark-800 border border-slate-800 text-slate-300 px-1.5 py-0.5 rounded text-[10px]"
                        >
                          {clause}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <button
                      type="button"
                      onClick={() => setInspectingTx(tx)}
                      className="text-blue-400 hover:text-blue-300 text-[11px] hover:underline font-sans cursor-pointer"
                    >
                      Inspect AST
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Table Pagination Footer */}
        <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800 font-mono">
          <div>
            Showing 1–{filteredTransactions.length} of 1,284 simulation triggers
          </div>
          <div className="flex items-center gap-1">
            <button className="px-2 py-1 bg-dark-850 border border-slate-800 rounded hover:text-white transition">
              Prev
            </button>
            <span className="px-2 py-1 bg-blue-600/20 text-blue-300 rounded font-bold border border-blue-500/40">
              1
            </span>
            <button className="px-2 py-1 bg-dark-850 border border-slate-800 rounded hover:text-white transition">
              2
            </button>
            <button className="px-2 py-1 bg-dark-850 border border-slate-800 rounded hover:text-white transition">
              3
            </button>
            <span className="px-1 text-slate-600">...</span>
            <button className="px-2 py-1 bg-dark-850 border border-slate-800 rounded hover:text-white transition">
              Next
            </button>
          </div>
        </div>
      </div>

      {/* 4. Inspect AST Modal */}
      {inspectingTx && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-dark-900 border border-slate-800 rounded-xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-fade-in">
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-dark-850">
              <div className="flex items-center gap-2">
                <FileCode2 className="w-4 h-4 text-brand-400" />
                <h3 className="text-sm font-semibold text-slate-100 font-mono">
                  Inspect AST Evaluation: {inspectingTx.event_id}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setInspectingTx(null)}
                className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-dark-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-dark-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] font-mono uppercase text-slate-500 block">
                    Event Details
                  </span>
                  <div className="mt-1 font-mono text-slate-200 space-y-0.5">
                    <div>
                      User ID: <span className="text-blue-400">{inspectingTx.user_id}</span>
                    </div>
                    <div>
                      Amount:{' '}
                      <span className="text-emerald-400 font-bold">
                        ${inspectingTx.amount.toFixed(2)}
                      </span>
                    </div>
                    <div>
                      Timestamp: <span className="text-slate-400">{inspectingTx.timestamp}</span>
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-dark-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] font-mono uppercase text-slate-500 block">
                    Ground Truth vs Rule Action
                  </span>
                  <div className="mt-1 font-mono text-slate-200 space-y-0.5">
                    <div>
                      Ground Truth:{' '}
                      {inspectingTx.ground_truth === 1 ? (
                        <span className="text-rose-400 font-bold">FRAUD (1)</span>
                      ) : (
                        <span className="text-slate-300 font-bold">LEGIT (0)</span>
                      )}
                    </div>
                    <div>
                      Predicted Action:{' '}
                      <span className="text-amber-400 font-bold">{ruleAction}</span>
                    </div>
                    <div>
                      Rule Code: <span className="text-brand-300">{ruleCode}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Matched Clauses Evaluation */}
              <div>
                <span className="text-[11px] font-mono uppercase text-slate-400 mb-2 block font-semibold">
                  AST Clause Evaluation Breakdown
                </span>
                <div className="space-y-1.5 font-mono text-xs">
                  {inspectingTx.matched_clauses.map((clause, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span className="text-emerald-300">{clause}</span>
                      </div>
                      <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/20 px-1.5 py-0.5 rounded">
                        TRUE
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Full Feature Context JSON */}
              <div>
                <span className="text-[11px] font-mono uppercase text-slate-400 mb-1.5 block font-semibold">
                  Transaction Feature Context
                </span>
                <pre className="p-3 bg-dark-950 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                  {JSON.stringify(inspectingTx.features, null, 2)}
                </pre>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-800 bg-dark-850 flex justify-end">
              <button
                type="button"
                onClick={() => setInspectingTx(null)}
                className="px-4 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 border border-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
