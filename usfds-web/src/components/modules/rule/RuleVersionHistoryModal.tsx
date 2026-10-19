import React, { useState, useEffect } from 'react';
import { X, History, User, Calendar, RotateCcw } from 'lucide-react';
import type { RuleResponse, RuleVersionResponse } from '../../../types/rule';
import { ruleApi } from '../../../api/ruleApi';

interface RuleVersionHistoryModalProps {
  rule: RuleResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onRestoreVersion: (version: RuleVersionResponse) => void;
}

export const RuleVersionHistoryModal: React.FC<RuleVersionHistoryModalProps> = ({
  rule,
  isOpen,
  onClose,
  onRestoreVersion,
}) => {
  const [versions, setVersions] = useState<RuleVersionResponse[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<RuleVersionResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && rule) {
      setLoading(true);
      ruleApi.getRuleVersions(rule.rule_id).then((res) => {
        if (res.success && res.data) {
          setVersions(res.data);
          setSelectedVersion(res.data[res.data.length - 1] || null);
        }
        setLoading(false);
      });
    }
  }, [isOpen, rule]);

  if (!isOpen || !rule) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-dark-900 border border-slate-800 w-full max-w-4xl rounded-xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-dark-950/80">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-brand-950 border border-brand-800/80 text-brand-400">
              <History className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-100">
                  Version History &amp; Audit Trail
                </h3>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800">
                  {rule.rule_code}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">{rule.name}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-dark-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content: Left Timeline + Right JSON Inspector */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden divide-y md:divide-y-0 md:divide-x divide-slate-800">
          {/* Left Timeline (40%) */}
          <div className="w-full md:w-2/5 p-4 overflow-y-auto space-y-3 bg-dark-950/40">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider pb-1">
              Historical Iterations ({versions.length})
            </div>

            {loading ? (
              <div className="py-8 text-center text-xs text-slate-500 font-mono">
                Đang tải lịch sử phiên bản...
              </div>
            ) : versions.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-500 font-mono">
                Chưa có phiên bản nào khác.
              </div>
            ) : (
              versions.map((v) => {
                const isSelected = selectedVersion?.rule_version_id === v.rule_version_id;
                const isCurrent = v.version_number === (rule.current_version?.version_number || 1);

                return (
                  <button
                    key={v.rule_version_id}
                    type="button"
                    onClick={() => setSelectedVersion(v)}
                    className={`w-full text-left p-3 rounded-lg border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-brand-950/50 border-brand-500/80 shadow-glow-blue'
                        : 'bg-dark-900 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-xs text-brand-300">
                        Version {v.version_number}.0
                      </span>
                      {isCurrent && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                          Current Live
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-slate-200 mt-1 font-medium line-clamp-2">
                      {v.change_summary || 'Cập nhật logic'}
                    </p>

                    <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                      <span className="flex items-center gap-1">
                        <User className="w-3 h-3" /> {v.created_by || 'analyst'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />{' '}
                        {new Date(v.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* Right Inspector (60%) */}
          <div className="flex-1 p-5 flex flex-col overflow-y-auto bg-dark-900">
            {selectedVersion ? (
              <div className="space-y-4 flex-1 flex flex-col">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div>
                    <h4 className="text-xs font-mono font-bold text-slate-200">
                      Version v{selectedVersion.version_number} Logic AST Inspector
                    </h4>
                    <span className="text-[11px] text-slate-400">
                      Action Decision:{' '}
                      <strong
                        className={`font-mono ${
                          selectedVersion.action === 'REVIEW'
                            ? 'text-amber-400'
                            : selectedVersion.action === 'REJECT'
                            ? 'text-red-400'
                            : 'text-emerald-400'
                        }`}
                      >
                        {selectedVersion.action}
                      </strong>
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      onRestoreVersion(selectedVersion);
                      onClose();
                    }}
                    className="px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-sm transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Load Into Studio</span>
                  </button>
                </div>

                <div className="flex-1 bg-dark-950 border border-slate-800 rounded-lg p-3.5 overflow-x-auto text-[11px] font-mono text-slate-300 leading-relaxed shadow-inner">
                  <pre className="p-0 m-0">
                    <code>{JSON.stringify(selectedVersion.condition, null, 2)}</code>
                  </pre>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-xs text-slate-500 font-mono">
                Chọn một phiên bản bên trái để xem chi tiết
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
