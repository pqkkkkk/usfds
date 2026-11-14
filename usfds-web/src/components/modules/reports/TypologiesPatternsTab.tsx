import React from 'react';
import {
	AlertOctagon,
	Clock,
	DollarSign,
	Fingerprint,
	Layers,
	ShieldAlert,
	UserX,
} from 'lucide-react';
import {
	Bar,
	CartesianGrid,
	Cell,
	ComposedChart,
	Legend,
	Line,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import { useTheme } from '@/hooks';
import type { TypologiesPatternsData } from '@/types';

interface TypologiesPatternsTabProps {
	data?: TypologiesPatternsData;
	isLoading: boolean;
}

function formatCurrency(val: number | undefined | null): string {
	return `$${Number(val ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export const TypologiesPatternsTab: React.FC<TypologiesPatternsTabProps> = ({ data, isLoading }) => {
	const { chartTokens } = useTheme();
	if (isLoading) {
		return (
			<div className="space-y-4 animate-pulse">
				<div className="h-56 bg-dark-900 border border-dark-700/80 rounded-xl" />
				<div className="h-72 bg-dark-900 border border-dark-700/80 rounded-xl" />
			</div>
		);
	}

	if (!data) {
		return null;
	}

	const fraudTypologies = (data.typology_breakdown || []).filter((i) => i.case_count > 0);
	const fpReasons = (data.fp_reason_breakdown || []).filter((i) => i.case_count > 0);
	const hourlyProfile = (data.hourly_distribution || []).map((h) => ({
		...h,
		fraud_rate_pct: Number(((h.fraud_rate ?? 0) * 100).toFixed(2)),
	}));
	const peakHours = hourlyProfile.filter((h) => h.is_peak_risk);
	const amountBrackets = data.amount_brackets || [];
	const topSubjects = data.top_flagged_subjects || [];
	const watchlistSummary = data.watchlist_summary;

	return (
		<div className="space-y-6">
			{/* 1. Fraud Typology vs False Positive Reason Breakdown */}
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
				{/* Fraud Typologies */}
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="mb-4">
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<AlertOctagon size={15} className="text-emerald-400" />
							<span>Phân tích loại hình gian lận đã xác nhận</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Distribution of verified fraud cases by analyst resolution reason (`FRAUD_REASONS`)
						</p>
					</div>

					{fraudTypologies.length === 0 ? (
						<div className="py-10 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
							Chưa ghi nhận hồ sơ gian lận đã xử lý (`RESOLVED_FRAUD`).
						</div>
					) : (
						<div className="space-y-3">
							{fraudTypologies.map((item) => {
								const pct = (item.pct ?? 0) * 100;
								return (
									<div key={item.code} className="bg-dark-950 border border-dark-800 rounded-lg p-3">
										<div className="flex items-center justify-between text-xs mb-1.5">
											<span className="font-semibold text-slate-200">{item.label}</span>
											<div className="flex items-center gap-3 font-mono tabular-nums">
												<span className="text-slate-300">{item.case_count} case(s)</span>
												<span className="text-emerald-400 font-semibold">
													{formatCurrency(item.total_amount)}
												</span>
												<span className="text-slate-400 w-12 text-right">
													{pct.toFixed(1)}%
												</span>
											</div>
										</div>
										<div className="w-full h-2 bg-dark-800 rounded-full overflow-hidden">
											<div
												className="h-full bg-emerald-500 rounded-full"
												style={{ width: `${Math.min(pct, 100)}%` }}
											/>
										</div>
									</div>
								);
							})}
						</div>
					)}
				</div>

				{/* False Positive Reasons */}
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="mb-4">
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Layers size={15} className="text-rose-400" />
							<span>Phân tích nguyên nhân gốc của dương tính giả</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Phân bố hồ sơ hợp lệ (`RESOLVED_LEGITIMATE`) theo nguyên nhân gốc gây ma sát (`LEGITIMATE_REASONS`)
						</p>
					</div>

					{fpReasons.length === 0 ? (
						<div className="py-10 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
							Chưa ghi nhận hồ sơ dương tính giả đã xử lý (`RESOLVED_LEGITIMATE`).
						</div>
					) : (
						<div className="space-y-3">
							{fpReasons.map((item) => {
								const pct = (item.pct ?? 0) * 100;
								return (
									<div key={item.code} className="bg-dark-950 border border-dark-800 rounded-lg p-3">
										<div className="flex items-center justify-between text-xs mb-1.5">
											<span className="font-semibold text-slate-200">{item.label}</span>
											<div className="flex items-center gap-3 font-mono tabular-nums">
												<span className="text-slate-300">{item.case_count} case(s)</span>
												<span className="text-rose-400 font-semibold">
													{formatCurrency(item.total_amount)}
												</span>
												<span className="text-slate-400 w-12 text-right">
													{pct.toFixed(1)}%
												</span>
											</div>
										</div>
										<div className="w-full h-2 bg-dark-800 rounded-full overflow-hidden">
											<div
												className="h-full bg-rose-500 rounded-full"
												style={{ width: `${Math.min(pct, 100)}%` }}
											/>
										</div>
									</div>
								);
							})}
						</div>
					)}
				</div>
			</div>

			{/* 2. Temporal Risk Profile (24-Hour UTC) */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
				<div className="flex flex-wrap items-center justify-between gap-2 mb-4">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Clock size={15} className="text-amber-400" />
							<span>Hồ sơ rủi ro theo 24 giờ (UTC)</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Hourly transaction volume vs. empirical fraud rate across 24 UTC hours (`00:00–23:00`)
						</p>
					</div>
					{peakHours.length > 0 && (
						<div className="flex items-center gap-2 text-xs font-mono bg-rose-500/10 border border-rose-500/30 text-rose-300 px-3 py-1 rounded-lg">
							<span>Khung rủi ro cao điểm (UTC):</span>
							<span className="font-bold">
								{peakHours.map((h) => h.label).join(', ')}
							</span>
						</div>
					)}
				</div>

				<div className="h-64 w-full">
					<ResponsiveContainer width="100%" height="100%">
						<ComposedChart data={hourlyProfile} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
							<CartesianGrid strokeDasharray="3 3" stroke={chartTokens.gridSubtleStroke} />
							<XAxis dataKey="label" stroke={chartTokens.axisStroke} tick={{ fontSize: 10 }} interval={1} />
							<YAxis yAxisId="left" stroke={chartTokens.axisStroke} tick={{ fontSize: 11 }} />
							<YAxis
								yAxisId="right"
								orientation="right"
								stroke="#F43F5E"
								tick={{ fontSize: 11 }}
								unit="%"
							/>
							<Tooltip
								contentStyle={{
									backgroundColor: chartTokens.tooltipBg,
									borderColor: chartTokens.tooltipBorder,
									color: chartTokens.tooltipText,
									borderRadius: '0.5rem',
									fontSize: '12px',
								}}
							/>
							<Legend wrapperStyle={{ fontSize: '12px' }} />
							<Bar yAxisId="left" dataKey="total_tx_count" name="Tổng giao dịch" radius={[3, 3, 0, 0]}>
								{hourlyProfile.map((entry) => (
									<Cell
										key={`cell-${entry.hour}`}
										fill={entry.is_peak_risk ? '#F59E0B' : chartTokens.inactiveBar}
									/>
								))}
							</Bar>
							<Line
								yAxisId="right"
								type="monotone"
								dataKey="fraud_rate_pct"
								name="Tỷ lệ gian lận (%)"
								stroke="#F43F5E"
								strokeWidth={2}
								dot={{ r: 2.5 }}
							/>
						</ComposedChart>
					</ResponsiveContainer>
				</div>
			</div>

			{/* 3. Amount Bracket Risk Profile & Top Flagged Subjects + Watchlist */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
				{/* 5-Segment Amount Bracket Risk Profile */}
				<div className="lg:col-span-5 bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="mb-4">
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<DollarSign size={15} className="text-emerald-400" />
							<span>Hồ sơ rủi ro theo khoảng số tiền</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Mật độ gian lận và thất thoát đã ngăn chặn theo 5 mức giá trị giao dịch
						</p>
					</div>

					<div className="overflow-x-auto">
						<table className="w-full text-left border-collapse">
							<thead>
								<tr className="border-b border-dark-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
									<th className="py-2 px-2.5">Bracket</th>
									<th className="py-2 px-2.5 text-right">Scanned</th>
									<th className="py-2 px-2.5 text-right">Flagged</th>
									<th className="py-2 px-2.5 text-right">Tỷ lệ bị gắn cờ</th>
									<th className="py-2 px-2.5 text-right">Fraud ($)</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-dark-800/60 text-xs font-mono tabular-nums">
								{amountBrackets.map((b) => (
									<tr key={b.bracket_id} className="hover:bg-dark-800/40">
										<td className="py-2.5 px-2.5 font-semibold text-slate-100">{b.label}</td>
										<td className="py-2.5 px-2.5 text-right text-slate-300">
											{(b.total_count ?? 0).toLocaleString()}
										</td>
										<td className="py-2.5 px-2.5 text-right text-amber-300">
											{(b.flagged_count ?? 0).toLocaleString()}
										</td>
										<td className="py-2.5 px-2.5 text-right text-rose-400 font-semibold">
											{((b.flag_rate ?? 0) * 100).toFixed(1)}%
										</td>
										<td className="py-2.5 px-2.5 text-right text-emerald-400">
											{formatCurrency(b.confirmed_fraud_amount)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</div>

				{/* Top Flagged Subjects & Active Watchlist Summary */}
				<div className="lg:col-span-7 bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-5">
					<div className="flex flex-wrap items-center justify-between gap-2">
						<div>
							<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
								<UserX size={15} className="text-rose-400" />
								<span>Đối tượng bị gắn cờ nhiều nhất & tóm tắt danh sách theo dõi</span>
							</h3>
							<p className="text-xs text-slate-400 mt-0.5">
								Đối tượng có mức phơi nhiễm cao nhất (`user_id`) và trạng thái thực thi `EntityBlacklist`
							</p>
						</div>
						{watchlistSummary && (
							<div className="flex items-center gap-2 text-xs font-mono">
								<span className="px-2.5 py-1 rounded bg-rose-500/15 border border-rose-500/30 text-rose-300">
									{watchlistSummary.active_blacklist_count ?? 0} Active Blacklisted
								</span>
								<span className="px-2.5 py-1 rounded bg-dark-950 border border-dark-800 text-slate-400">
									{watchlistSummary.removed_blacklist_count ?? 0} Removed
								</span>
							</div>
						)}
					</div>

					{/* Active Watchlist by EntityType */}
					{watchlistSummary?.by_entity_type && watchlistSummary.by_entity_type.length > 0 && (
						<div className="flex flex-wrap items-center gap-2">
							{watchlistSummary.by_entity_type.map((item) => (
								<div
									key={item.entity_type}
									className="px-2.5 py-1 rounded-lg bg-dark-950 border border-dark-800 text-xs font-mono flex items-center gap-2"
								>
									<Fingerprint size={12} className="text-brand-400" />
									<span className="text-slate-300">{item.entity_type}:</span>
									<span className="text-slate-100 font-bold">{item.active_count}</span>
								</div>
							))}
						</div>
					)}

					{/* Top Flagged Subjects Table */}
					{topSubjects.length === 0 ? (
						<div className="py-8 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
							Không có đối tượng bị gắn cờ trong phạm vi đã chọn.
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-left border-collapse">
								<thead>
									<tr className="border-b border-dark-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
										<th className="py-2 px-2.5">Người dùng liên quan (`user_id`)</th>
										<th className="py-2 px-2.5 text-right">Flagged Txs</th>
										<th className="py-2 px-2.5 text-right">Confirmed Fraud</th>
										<th className="py-2 px-2.5 text-right">Risk Exposure ($)</th>
										<th className="py-2 px-2.5 text-right">Điểm cao nhất</th>
										<th className="py-2 px-2.5 text-center">Danh sách theo dõi</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800/60 text-xs font-mono tabular-nums">
									{topSubjects.map((sub) => (
										<tr key={sub.user_id} className="hover:bg-dark-800/40">
											<td className="py-2 px-2.5 font-semibold text-slate-100">{sub.user_id}</td>
											<td className="py-2 px-2.5 text-right text-slate-300">
												{sub.flagged_tx_count}
											</td>
											<td className="py-2 px-2.5 text-right text-emerald-400 font-semibold">
												{sub.confirmed_fraud_count}
											</td>
											<td className="py-2 px-2.5 text-right text-amber-300">
												{formatCurrency(sub.amount_at_risk)}
											</td>
											<td className="py-2 px-2.5 text-right text-slate-200">
												{(sub.max_model_score ?? 0).toFixed(3)}
											</td>
											<td className="py-2 px-2.5 text-center">
												{sub.is_blacklisted ? (
													<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-500/15 border border-rose-500/30 text-rose-300 text-[10px]">
														<ShieldAlert size={10} />
														<span>BLACKLISTED</span>
													</span>
												) : (
													<span className="text-slate-500 text-[11px]">—</span>
												)}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};
