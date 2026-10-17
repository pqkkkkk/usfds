import { useState } from 'react';
import { 
  Search, 
  Database, 
  BrainCircuit, 
  ShieldCheck, 
  ArrowRight, 
  X,
  Terminal,
  SearchCheck,
  BarChart2
} from 'lucide-react';
import type { AppModule } from '../../types/navigation';

interface OmnisearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateModule: (module: AppModule) => void;
}

export const OmnisearchModal = ({
  isOpen,
  onClose,
  onNavigateModule,
}: OmnisearchModalProps) => {
  const [query, setQuery] = useState('');

  if (!isOpen) return null;

  // Quick module launcher
  const quickActions = [
    { label: 'Data Management (Datasets, Lineage Tree, Schema, Features)', module: 'data-management' as AppModule, type: 'Module', icon: Database },
    { label: 'Model Management (Training Wizard, Hyperparameters, Evaluation)', module: 'model-management' as AppModule, type: 'Module', icon: BrainCircuit },
    { label: 'Rule Management (Visual Studio, Historical Backtest, AI Mining)', module: 'rule-management' as AppModule, type: 'Module', icon: ShieldCheck },
    { label: 'Detection (Batch Inference Jobs & Scoring Execution)', module: 'detection' as AppModule, type: 'Module', icon: Terminal },
    { label: 'Investigation (Alert Queue, Drilldown & Case Dispatch)', module: 'investigation' as AppModule, type: 'Module', icon: SearchCheck },
    { label: 'Insight & Report (Fraud Analytics, False Positives, Trends)', module: 'insight-report' as AppModule, type: 'Module', icon: BarChart2 },
  ];

  const filtered = quickActions.filter(item => 
    item.label.toLowerCase().includes(query.toLowerCase()) || 
    item.type.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div 
        role="dialog"
        aria-label="Omnisearch"
        className="w-full max-w-xl bg-dark-900 border border-dark-700 rounded-xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150 flex flex-col"
      >
        {/* Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-dark-700/80 bg-dark-850">
          <Search className="w-4 h-4 text-brand-400" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search module or workflow..."
            className="flex-1 bg-transparent border-none outline-none text-xs text-slate-100 placeholder:text-slate-500 font-sans"
          />
          <button 
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length > 0 ? (
            filtered.map((item, idx) => {
              const Icon = item.icon;
              return (
                <button
                  key={idx}
                  onClick={() => {
                    onNavigateModule(item.module);
                    onClose();
                  }}
                  className="w-full flex items-center justify-between p-2.5 rounded-lg hover:bg-dark-800 text-left transition group focus-ring text-xs"
                >
                  <div className="flex items-center gap-3 truncate">
                    <div className="w-7 h-7 rounded-md bg-dark-800 border border-dark-700 flex items-center justify-center text-slate-400 group-hover:text-brand-400 shrink-0">
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div className="truncate">
                      <div className="text-slate-200 font-medium group-hover:text-white truncate">
                        {item.label}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {item.type}
                      </div>
                    </div>
                  </div>

                  <ArrowRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-brand-400 transition shrink-0" />
                </button>
              );
            })
          ) : (
            <div className="py-8 text-center text-xs text-slate-500">
              No results found for "{query}"
            </div>
          )}
        </div>

        {/* Modal Footer Key Guide */}
        <div className="px-4 py-2 border-t border-dark-800 bg-dark-950/60 flex items-center justify-between text-[11px] text-slate-500 font-mono">
          <span>USFDS Quick Launcher</span>
          <div className="flex items-center gap-2">
            <span>[Esc] to close</span>
          </div>
        </div>
      </div>
    </div>
  );
};
