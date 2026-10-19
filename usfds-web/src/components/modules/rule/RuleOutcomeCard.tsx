import React from 'react';
import { CheckCircle2, Sliders, ShieldAlert, Ban, Check } from 'lucide-react';
import type { RuleAction } from '../../../types/rule';

interface RuleOutcomeCardProps {
  action: RuleAction;
  description: string;
  changeSummary?: string;
  onChangeAction: (action: RuleAction) => void;
  onChangeDescription: (desc: string) => void;
  onChangeChangeSummary?: (summary: string) => void;
}

export const RuleOutcomeCard: React.FC<RuleOutcomeCardProps> = ({
  action,
  description,
  changeSummary,
  onChangeAction,
  onChangeDescription,
  onChangeChangeSummary,
}) => {
  return (
    <div className="pt-2">
      {/* Header */}
      <div className="flex items-center gap-2 pb-3 border-b border-slate-800/80">
        <Sliders className="w-4 h-4 text-amber-400" />
        <h2 className="text-xs font-bold tracking-wider uppercase text-slate-200 font-mono">
          EXECUTION OUTCOME &amp; ACTION (THEN)
        </h2>
      </div>

      <div className="mt-4 space-y-4">
        {/* Decision Action: ALLOW, REVIEW, REJECT */}
        <div>
          <label className="block text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-2">
            Decision Action (Hành động khi khớp điều kiện)
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* ALLOW */}
            <button
              type="button"
              onClick={() => onChangeAction('ALLOW')}
              className={`p-3 rounded-lg border text-left transition-all flex items-center gap-2.5 cursor-pointer ${
                action === 'ALLOW'
                  ? 'bg-emerald-950/30 border-emerald-500/80 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
                  : 'bg-dark-950/90 border-slate-800/80 hover:border-slate-700 text-slate-400'
              }`}
            >
              <Check className={`w-4 h-4 shrink-0 ${action === 'ALLOW' ? 'text-emerald-400' : 'text-slate-500'}`} />
              <div>
                <div className="text-xs font-bold text-emerald-400 flex items-center gap-1">
                  ALLOW
                  {action === 'ALLOW' && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
                </div>
                <div className="text-[10px] text-slate-400 leading-tight">Chấp nhận / Vượt qua kiểm tra</div>
              </div>
            </button>

            {/* REVIEW (Amber) */}
            <button
              type="button"
              onClick={() => onChangeAction('REVIEW')}
              className={`p-3 rounded-lg border text-left transition-all flex items-center gap-2.5 cursor-pointer ${
                action === 'REVIEW'
                  ? 'bg-amber-950/30 border-amber-500/80 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.2)]'
                  : 'bg-dark-950/90 border-slate-800/80 hover:border-slate-700 text-slate-400'
              }`}
            >
              <ShieldAlert className={`w-4 h-4 shrink-0 ${action === 'REVIEW' ? 'text-amber-400' : 'text-slate-500'}`} />
              <div>
                <div className="text-xs font-bold text-amber-400 flex items-center gap-1">
                  REVIEW
                  {action === 'REVIEW' && <CheckCircle2 className="w-3 h-3 text-amber-400" />}
                </div>
                <div className="text-[10px] text-amber-300/80 leading-tight">Gửi vào hàng đợi duyệt thủ công</div>
              </div>
            </button>

            {/* REJECT (Red) */}
            <button
              type="button"
              onClick={() => onChangeAction('REJECT')}
              className={`p-3 rounded-lg border text-left transition-all flex items-center gap-2.5 cursor-pointer ${
                action === 'REJECT'
                  ? 'bg-red-950/30 border-red-500/80 text-red-300 shadow-[0_0_12px_rgba(239,68,68,0.2)]'
                  : 'bg-dark-950/90 border-slate-800/80 hover:border-slate-700 text-slate-400'
              }`}
            >
              <Ban className={`w-4 h-4 shrink-0 ${action === 'REJECT' ? 'text-red-400' : 'text-slate-500'}`} />
              <div>
                <div className="text-xs font-bold text-red-400 flex items-center gap-1">
                  REJECT
                  {action === 'REJECT' && <CheckCircle2 className="w-3 h-3 text-red-400" />}
                </div>
                <div className="text-[10px] text-slate-400 leading-tight">Từ chối giao dịch ngay lập tức</div>
              </div>
            </button>
          </div>
        </div>

        {/* Description (Mô tả quy tắc) */}
        <div>
          <label className="block text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-1">
            Description (Mô tả quy tắc nghiệp vụ)
          </label>
          <textarea
            rows={2}
            value={description}
            onChange={(e) => onChangeDescription(e.target.value)}
            placeholder="Mô tả lý do, ngữ cảnh nghiệp vụ hoặc dấu hiệu nhận biết của quy tắc..."
            className="w-full bg-dark-950 border border-slate-800 text-slate-300 text-xs font-sans rounded-lg p-3 focus:border-brand-500 focus:outline-none resize-none leading-relaxed"
          />
        </div>

        {/* Change Summary (Tóm tắt thay đổi phiên bản) */}
        {onChangeChangeSummary && (
          <div>
            <label className="block text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-1">
              Change Summary (Tóm tắt thay đổi phiên bản)
            </label>
            <input
              type="text"
              value={changeSummary || ''}
              onChange={(e) => onChangeChangeSummary(e.target.value)}
              placeholder="Ví dụ: Điều chỉnh ngưỡng số tiền lên $2,000 và thêm MCC crypto"
              className="w-full bg-dark-950 border border-slate-800 text-slate-200 text-xs font-mono rounded-lg px-3 py-2 focus:border-brand-500 focus:outline-none"
            />
          </div>
        )}
      </div>
    </div>
  );
};
