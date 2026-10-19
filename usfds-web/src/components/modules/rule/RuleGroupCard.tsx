import React from 'react';
import { Plus, FolderPlus, Trash2 } from 'lucide-react';
import type { RuleGroup, RuleClause, LogicalCombinator } from '../../../types/rule';
import {
  isRuleGroup,
  createDefaultClause,
  createDefaultGroup,
} from '../../../utils/jsonLogicParser';
import { RuleClauseRow } from './RuleClauseRow';

interface RuleGroupCardProps {
  group: RuleGroup;
  level?: number;
  prefixIndex?: string;
  onChange: (updatedGroup: RuleGroup) => void;
  onDeleteGroup?: () => void;
}

export const RuleGroupCard: React.FC<RuleGroupCardProps> = ({
  group,
  level = 0,
  prefixIndex = '1',
  onChange,
  onDeleteGroup,
}) => {
  const isRoot = level === 0;

  const handleCombinatorChange = (combinator: LogicalCombinator) => {
    onChange({ ...group, combinator });
  };

  const handleClauseChange = (index: number, updated: RuleClause | RuleGroup) => {
    const newClauses = [...group.clauses];
    newClauses[index] = updated;
    onChange({ ...group, clauses: newClauses });
  };

  const handleAddClause = () => {
    onChange({
      ...group,
      clauses: [...group.clauses, createDefaultClause()],
    });
  };

  const handleAddSubGroup = () => {
    onChange({
      ...group,
      clauses: [...group.clauses, createDefaultGroup('ANY')],
    });
  };

  const handleDeleteClause = (index: number) => {
    const newClauses = group.clauses.filter((_, idx) => idx !== index);
    onChange({ ...group, clauses: newClauses });
  };

  const combinatorColor =
    group.combinator === 'ALL'
      ? 'border-blue-500/30 text-blue-300 bg-blue-950/30'
      : group.combinator === 'ANY'
      ? 'border-amber-500/30 text-amber-300 bg-amber-950/30'
      : 'border-purple-500/30 text-purple-300 bg-purple-950/30';

  const combinatorBadge =
    group.combinator === 'ALL'
      ? 'Logical AND'
      : group.combinator === 'ANY'
      ? 'Logical OR Sub-branch'
      : 'Logical NOT / NOR';

  return (
    <div
      className={`${
        isRoot
          ? 'p-4 rounded-xl bg-dark-950/70 border border-slate-800/80 space-y-4'
          : 'p-3 rounded-lg bg-dark-900/80 border border-slate-800/90 border-l-2 border-l-brand-500 space-y-3 relative'
      }`}
    >

      {/* Group Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          {!isRoot && (
            <span className="text-[11px] font-mono text-slate-500 w-6 shrink-0">
              {prefixIndex}
            </span>
          )}
          <span className="text-xs font-mono text-slate-300 font-semibold">IF</span>

          <div className="relative inline-block">
            <select
              value={group.combinator}
              onChange={(e) => handleCombinatorChange(e.target.value as LogicalCombinator)}
              aria-label="Logic Combinator"
              className={`border text-xs font-mono font-semibold rounded-md px-2.5 py-1 pr-6 focus:outline-none cursor-pointer ${combinatorColor}`}
            >
              <option value="ALL">ALL of</option>
              <option value="ANY">ANY of</option>
              <option value="NONE">NONE of</option>
            </select>
          </div>

          <span className="text-xs text-slate-300">
            {isRoot ? 'the following conditions are true:' : 'the sub-conditions are true:'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
              group.combinator === 'ALL'
                ? 'text-slate-400 bg-dark-900 border-slate-800'
                : 'text-amber-400/90 bg-amber-950/20 border-amber-500/30'
            }`}
          >
            {combinatorBadge}
          </span>

          {!isRoot && onDeleteGroup && (
            <button
              type="button"
              onClick={onDeleteGroup}
              className="text-slate-500 hover:text-red-400 p-1 rounded hover:bg-red-950/20 transition-colors"
              title="Remove sub-group"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Clauses and Subgroups List */}
      <div className="space-y-3">
        {group.clauses.length === 0 ? (
          <div className="py-4 text-center border border-dashed border-slate-800 rounded-lg text-slate-500 text-xs font-mono">
            Chưa có điều kiện nào. Bấm &ldquo;Add Condition&rdquo; để thiết lập.
          </div>
        ) : (
          group.clauses.map((item, idx) => {
            const currentPrefix = isRoot ? `${prefixIndex}.${idx + 1}` : `${prefixIndex}.${idx + 1}`;
            if (isRuleGroup(item)) {
              return (
                <RuleGroupCard
                  key={item.id || idx}
                  group={item}
                  level={level + 1}
                  prefixIndex={currentPrefix}
                  onChange={(updated) => handleClauseChange(idx, updated)}
                  onDeleteGroup={() => handleDeleteClause(idx)}
                />
              );
            }

            return (
              <RuleClauseRow
                key={item.id || idx}
                clause={item}
                indexLabel={currentPrefix}
                onChange={(updated) => handleClauseChange(idx, updated)}
                onDelete={() => handleDeleteClause(idx)}
              />
            );
          })
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2.5 pt-1">
        <button
          type="button"
          onClick={handleAddClause}
          className={`px-3 py-1.5 rounded-md bg-dark-900 hover:bg-dark-850 border border-slate-800 text-xs font-medium transition-colors flex items-center gap-1.5 ${
            isRoot ? 'text-brand-400 hover:border-brand-500/50' : 'text-slate-300'
          }`}
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Condition</span>
        </button>

        {level < 2 && (
          <button
            type="button"
            onClick={handleAddSubGroup}
            className="px-3 py-1.5 rounded-md bg-dark-900 hover:bg-dark-850 border border-slate-800 text-slate-300 hover:border-slate-700 text-xs font-medium transition-colors flex items-center gap-1.5"
          >
            <FolderPlus className="w-3.5 h-3.5 text-slate-400" />
            <span>Add Nested Group</span>
          </button>
        )}
      </div>
    </div>
  );
};
