import React, { useState } from 'react';
import { Trash2, X, Plus } from 'lucide-react';
import type { RuleClause, ComparisonOperator, AvailableFeatureField } from '../../../types/rule';
import { AVAILABLE_FEATURE_FIELDS } from '../../../utils/jsonLogicParser';

interface RuleClauseRowProps {
  clause: RuleClause;
  indexLabel: string;
  availableFields?: AvailableFeatureField[];
  onChange: (updated: RuleClause) => void;
  onDelete: () => void;
}

export const RuleClauseRow: React.FC<RuleClauseRowProps> = ({
  clause,
  indexLabel,
  availableFields = AVAILABLE_FEATURE_FIELDS,
  onChange,
  onDelete,
}) => {
  const [customTagInput, setCustomTagInput] = useState('');
  const fieldsList = availableFields.length > 0 ? availableFields : AVAILABLE_FEATURE_FIELDS;
  const currentFieldMeta = fieldsList.find((f) => f.key === clause.field);
  const hasCurrentFieldInList = Boolean(currentFieldMeta);

  const handleFieldChange = (newField: string) => {
    const meta = fieldsList.find((f) => f.key === newField);
    onChange({
      ...clause,
      field: newField,
      operator: meta?.defaultOperator || '==',
      value: meta?.dataType === 'boolean' ? true : meta?.dataType === 'array' ? ['crypto'] : meta?.dataType === 'number' ? 100 : '',
      unit: meta?.unit,
    });
  };

  const handleOperatorChange = (op: ComparisonOperator) => {
    onChange({ ...clause, operator: op });
  };

  const handleValueChange = (val: any) => {
    onChange({ ...clause, value: val });
  };

  const handleAddTag = (tag: string) => {
    const list = Array.isArray(clause.value) ? [...clause.value] : [];
    if (tag && !list.includes(tag)) {
      list.push(tag);
      onChange({ ...clause, value: list });
    }
  };

  const handleRemoveTag = (index: number) => {
    const list = Array.isArray(clause.value) ? [...clause.value] : [];
    list.splice(index, 1);
    onChange({ ...clause, value: list });
  };

  return (
    <div className="p-3 rounded-lg bg-dark-900/90 border border-slate-800 hover:border-slate-700 transition-colors flex flex-wrap lg:flex-nowrap items-center justify-between gap-3 group">
      <div className="flex flex-wrap items-center gap-2.5 flex-1">
        {/* Index label (e.g. 1.1, 2.1) */}
        <span className="text-[11px] font-mono text-slate-500 w-6 shrink-0">{indexLabel}</span>

        {/* Field selector */}
        <div className="relative min-w-[200px] flex-1 sm:flex-none">
          <select
            value={clause.field}
            onChange={(e) => handleFieldChange(e.target.value)}
            className="w-full bg-dark-950 border border-slate-800 text-slate-200 text-xs font-mono rounded-md px-2.5 py-1.5 focus:border-brand-500 focus:outline-none cursor-pointer"
          >
            {!hasCurrentFieldInList && clause.field && (
              <option value={clause.field}>{clause.field} (custom)</option>
            )}
            {fieldsList.map((f) => (
              <option key={f.key} value={f.key}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        {/* Operator selector */}
        <div className="relative w-24 shrink-0">
          <select
            value={clause.operator}
            onChange={(e) => handleOperatorChange(e.target.value as ComparisonOperator)}
            className="w-full bg-dark-950 border border-slate-800 text-brand-400 text-xs font-mono font-semibold rounded-md px-2.5 py-1.5 focus:border-brand-500 focus:outline-none text-center cursor-pointer"
          >
            <option value=">">&gt;</option>
            <option value=">=">&gt;=</option>
            <option value="<">&lt;</option>
            <option value="<=">&lt;=</option>
            <option value="==">==</option>
            <option value="!=">!=</option>
            <option value="in">IN</option>
            <option value="not_in">NOT IN</option>
            <option value="regex">REGEX</option>
          </select>
        </div>

        {/* Value Input by DataType */}
        {clause.operator === 'in' || clause.operator === 'not_in' || Array.isArray(clause.value) ? (
          <div className="flex-1 min-w-[220px] bg-dark-950 border border-slate-800 rounded-md px-2 py-1 flex flex-wrap items-center gap-1.5">
            {Array.isArray(clause.value) &&
              clause.value.map((item: string, idx: number) => (
                <span
                  key={idx}
                  className="text-[10px] font-mono bg-blue-950/60 text-blue-300 border border-blue-900/60 px-2 py-0.5 rounded flex items-center gap-1"
                >
                  {item}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(idx)}
                    className="hover:text-red-400 ml-0.5 transition-colors"
                  >
                    <X className="w-2.5 h-2.5" />
                  </button>
                </span>
              ))}

            {/* Quick add tag input & dropdown */}
            <div className="flex items-center gap-1 ml-auto">
              <input
                type="text"
                value={customTagInput}
                onChange={(e) => setCustomTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && customTagInput.trim()) {
                    e.preventDefault();
                    handleAddTag(customTagInput.trim());
                    setCustomTagInput('');
                  }
                }}
                placeholder="Nhập giá trị + Enter"
                className="bg-dark-900 border border-slate-800 rounded px-2 py-0.5 text-[10px] font-mono text-slate-200 w-28 focus:outline-none focus:border-brand-500"
              />
              <button
                type="button"
                onClick={() => {
                  if (customTagInput.trim()) {
                    handleAddTag(customTagInput.trim());
                    setCustomTagInput('');
                  }
                }}
                className="p-0.5 rounded bg-dark-850 hover:bg-dark-800 text-slate-400 hover:text-brand-400 border border-slate-800 cursor-pointer"
                title="Thêm giá trị"
              >
                <Plus className="w-3 h-3" />
              </button>
              {currentFieldMeta?.sampleValues && currentFieldMeta.sampleValues.length > 0 && (
                <select
                  onChange={(e) => {
                    if (e.target.value) {
                      handleAddTag(e.target.value);
                      e.target.value = '';
                    }
                  }}
                  className="bg-transparent text-[10px] text-slate-400 focus:outline-none cursor-pointer"
                  defaultValue=""
                >
                  <option value="" disabled>
                    + Mẫu
                  </option>
                  {currentFieldMeta.sampleValues.map((val) => (
                    <option key={String(val)} value={String(val)} className="bg-dark-900 text-slate-200">
                      {String(val)}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        ) : currentFieldMeta?.dataType === 'boolean' || typeof clause.value === 'boolean' ? (
          <div className="w-28 shrink-0">
            <select
              value={String(clause.value)}
              onChange={(e) => handleValueChange(e.target.value === 'true')}
              className="w-full bg-dark-950 border border-slate-800 text-emerald-400 text-xs font-mono font-medium rounded-md px-2.5 py-1.5 focus:border-brand-500 focus:outline-none cursor-pointer"
            >
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 flex-1 min-w-[120px]">
            <input
              type={currentFieldMeta?.dataType === 'number' ? 'number' : 'text'}
              value={clause.value}
              onChange={(e) => handleValueChange(e.target.value)}
              placeholder="Giá trị"
              className="w-full bg-dark-950 border border-slate-800 text-slate-200 text-xs font-mono rounded-md px-2.5 py-1.5 focus:border-brand-500 focus:outline-none"
            />
            {clause.unit && (
              <span className="text-[11px] font-mono text-slate-400 px-2 py-1 bg-dark-850 border border-slate-800 rounded-md shrink-0">
                {clause.unit}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Delete Clause Button */}
      <button
        type="button"
        onClick={onDelete}
        className="text-slate-500 hover:text-red-400 p-1.5 rounded hover:bg-red-950/20 transition-colors ml-1 shrink-0"
        title="Xóa điều kiện"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
};
