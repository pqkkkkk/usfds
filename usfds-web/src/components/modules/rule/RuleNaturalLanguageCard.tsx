import React from 'react';
import { MessageSquare, Quote } from 'lucide-react';
import type { RuleGroup, RuleAction } from '../../../types/rule';
import { groupToNaturalLanguage } from '../../../utils/jsonLogicParser';

interface RuleNaturalLanguageCardProps {
  group: RuleGroup;
  action: RuleAction;
}

export const RuleNaturalLanguageCard: React.FC<RuleNaturalLanguageCardProps> = ({
  group,
  action,
}) => {
  const explanation = groupToNaturalLanguage(group, action);

  const getActionBadge = () => {
    switch (action) {
      case 'REVIEW':
        return (
          <span className="text-amber-400 font-semibold not-italic px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-500/30">
            REVIEW
          </span>
        );
      case 'REJECT':
        return (
          <span className="text-red-400 font-semibold not-italic px-1.5 py-0.5 rounded bg-red-950/40 border border-red-500/30">
            REJECT
          </span>
        );
      case 'ALLOW':
      default:
        return (
          <span className="text-emerald-400 font-semibold not-italic px-1.5 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/30">
            ALLOW
          </span>
        );
    }
  };

  return (
    <div className="bg-dark-900 border border-slate-800/90 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-brand-400" />
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono">
            Natural Language Interpretation
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/40 text-blue-300 border border-blue-900/50">
          Auto-synced
        </span>
      </div>

      <div className="mt-3.5 p-4 rounded-lg bg-dark-950 border border-slate-800 text-xs font-sans leading-relaxed text-slate-300 relative">
        <Quote className="w-4 h-4 text-slate-600 absolute top-3.5 left-3.5 select-none" />
        <div className="pl-6 italic">
          “Trigger {getActionBadge()}{' '}
          <span className="text-slate-200">
            {explanation.replace(/^Trigger (REVIEW|REJECT|ALLOW) /, '')}
          </span>
          ”
        </div>
      </div>
    </div>
  );
};
