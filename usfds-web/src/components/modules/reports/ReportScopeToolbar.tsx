import React from 'react';
import { Calendar, Filter, RotateCcw, ShieldCheck } from 'lucide-react';
import type { ReportScopeFilter } from '@/types';

interface ReportScopeToolbarProps {
	scope: ReportScopeFilter;
	onChange: (next: ReportScopeFilter) => void;
	scannedJobsCount?: number;
}

export const ReportScopeToolbar: React.FC<ReportScopeToolbarProps> = ({
	scope,
	onChange,
	scannedJobsCount,
}) => {
	const hasActiveFilters = Boolean(
		scope.dateFrom || scope.dateTo || scope.useDatasetFallback === false
	);

	return (
		<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3">
			<div className="flex flex-wrap items-center gap-3">
				<div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400 pr-2 border-r border-dark-700">
					<Filter size={14} className="text-brand-400" />
					<span>Phạm vi phân tích</span>
				</div>

				{/* Transaction date range (tx_timestamp, not the detection session date) */}
				<div
					className="flex items-center gap-2 bg-dark-950 border border-dark-700/80 rounded-lg px-2.5 py-1.5"
					title="Lọc theo thời điểm giao dịch"
				>
					<Calendar size={13} className="text-slate-400 shrink-0" />
					<input
						type="date"
						aria-label="Từ ngày"
						value={scope.dateFrom || ''}
						onChange={(e) => onChange({ ...scope, dateFrom: e.target.value || undefined })}
						className="bg-transparent text-xs text-slate-200 font-mono focus:outline-none cursor-pointer"
					/>
					<span className="text-slate-600 text-xs">→</span>
					<input
						type="date"
						aria-label="Đến ngày"
						value={scope.dateTo || ''}
						onChange={(e) => onChange({ ...scope, dateTo: e.target.value || undefined })}
						className="bg-transparent text-xs text-slate-200 font-mono focus:outline-none cursor-pointer"
					/>
				</div>

				{/* Ground-Truth Priority Toggle */}
				<button
					type="button"
					onClick={() => onChange({ ...scope, useDatasetFallback: !(scope.useDatasetFallback ?? true) })}
					className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors cursor-pointer ${
						scope.useDatasetFallback ?? true
							? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
							: 'bg-brand-500/10 border-brand-500/30 text-brand-300'
					}`}
					title="Bật/tắt việc dùng nhãn thực tế của tập dữ liệu khi giao dịch chưa xem xét và có nhãn"
				>
					<ShieldCheck size={13} />
					<span>
						{scope.useDatasetFallback ?? true
							? 'Nhãn thực tế: kết luận hồ sơ + dự phòng từ tập dữ liệu'
							: 'Nhãn thực tế: chỉ hồ sơ đã xác minh'}
					</span>
				</button>

				{hasActiveFilters && (
					<button
						type="button"
						onClick={() =>
							onChange({
								dateFrom: undefined,
								dateTo: undefined,
								useDatasetFallback: true,
							})
						}
						className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 text-slate-300 text-xs transition-colors cursor-pointer"
					>
						<RotateCcw size={12} />
						<span>Đặt lại</span>
					</button>
				)}
			</div>

			<div className="flex items-center gap-2 text-xs text-slate-400 font-mono tabular-nums">
				<span className="inline-block w-2 h-2 rounded-full bg-emerald-400" />
				<span>Kho dữ liệu dự án • {scannedJobsCount ?? 0} phiên quét</span>
			</div>
		</div>
	);
};
