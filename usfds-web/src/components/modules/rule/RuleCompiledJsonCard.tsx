import React, { useState } from 'react';
import { Code, Copy, Check, Terminal } from 'lucide-react';
import type { RuleGroup } from '../../../types/rule';
import {
  groupToJsonLogic,
  groupToStitchDsl,
  countAstNodes,
} from '../../../utils/jsonLogicParser';

interface RuleCompiledJsonCardProps {
  group: RuleGroup;
}

export const RuleCompiledJsonCard: React.FC<RuleCompiledJsonCardProps> = ({ group }) => {
  const [format, setFormat] = useState<'jsonLogic' | 'stitchDsl'>('jsonLogic');
  const [copied, setCopied] = useState(false);

  const compiled =
    format === 'jsonLogic' ? groupToJsonLogic(group) : groupToStitchDsl(group);
  const jsonString = JSON.stringify(compiled, null, 2);
  const nodeCount = countAstNodes(group);

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-dark-900 border border-slate-800/90 rounded-xl p-5 shadow-sm">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <Code className="w-4 h-4 text-brand-400" />
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono">
            Compiled Rule Logic JSON (rule_condition)
          </h3>
        </div>

        <div className="flex items-center gap-2">
          {/* Format Toggle */}
          <div className="flex items-center bg-dark-950 p-0.5 rounded border border-slate-800">
            <button
              type="button"
              onClick={() => setFormat('jsonLogic')}
              className={`px-2 py-0.5 text-[10px] font-mono rounded transition-colors ${
                format === 'jsonLogic'
                  ? 'bg-brand-600 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Core JsonLogic
            </button>
            <button
              type="button"
              onClick={() => setFormat('stitchDsl')}
              className={`px-2 py-0.5 text-[10px] font-mono rounded transition-colors ${
                format === 'stitchDsl'
                  ? 'bg-brand-600 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Stitch DSL
            </button>
          </div>

          {/* Copy Button */}
          <button
            type="button"
            onClick={handleCopy}
            className="px-2.5 py-1 rounded bg-dark-950 hover:bg-dark-800 border border-slate-800 text-slate-300 text-[10px] font-mono transition-colors flex items-center gap-1.5 cursor-pointer"
            title="Sao chép JSON"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Code Block */}
      <div className="mt-3.5 p-3.5 rounded-lg bg-dark-950 border border-slate-800/90 overflow-x-auto text-[11px] font-mono text-slate-300 leading-relaxed max-h-96 overflow-y-auto">
        <pre className="p-0 m-0 font-mono">
          <code>{jsonString}</code>
        </pre>
      </div>

      {/* Metadata Telemetry */}
      <div className="mt-2.5 flex items-center justify-between text-[10px] font-mono text-slate-500">
        <span className="flex items-center gap-1.5">
          <Terminal className="w-3 h-3 text-brand-400" />
          <span>AST Nodes: {nodeCount}</span>
        </span>
        <span className="text-emerald-400/90 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block"></span>
          Evaluation Latency: ~0.3ms
        </span>
      </div>
    </div>
  );
};
