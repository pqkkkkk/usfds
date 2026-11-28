import React from 'react';
import {
	Activity,
	AlertTriangle,
	ArrowUpRight,
	CheckCircle2,
	Clock,
	DollarSign,
	Filter,
	ShieldAlert,
	ShieldCheck,
	ShieldOff,
	Target,
	Users,
} from 'lucide-react';
import {
	Bar,
	CartesianGrid,
	ComposedChart,
	Legend,
	Line,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '@/hooks';
import type { ExecutiveOverviewData } from '@/types';
import { MetricInfoTooltip } from './MetricInfoTooltip';

interface ExecutiveOverviewTabProps {
	data?: ExecutiveOverviewData;
	isLoading: boolean;
}

function formatCurrency(val: number | undefined | null): string {
	return `$${Number(val ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export const ExecutiveOverviewTab: React.FC<ExecutiveOverviewTabProps> = ({ data, isLoading }) => {
	const navigate = useNavigate();
	const { chartTokens } = useTheme();

	if (isLoading) {
		return (
			<div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-pulse">
				{Array.from({ length: 6 }).map((_, idx) => (
					<div key={idx} className="h-32 bg-dark-900 border border-dark-700/80 rounded-xl p-4" />
				))}
			</div>
		);
	}

	if (!data || !data.kpis) {
		return null;
	}

	const { kpis } = data;
	const isFlaggedOnly = kpis.ground_truth_coverage === 'FLAGGED_ONLY' || kpis.label_source === 'VERIFIED_ONLY';
	const funnel = data.funnel || [];
	const financialTrends = (data.financial_trends || []).map((pt) => ({
		...pt,
		x_label: pt.label || pt.date || pt.job_name,
		alert_rate_pct: Number(((pt.flagged_rate ?? 0) * 100).toFixed(2)),
	}));
	const statusBreakdown = data.queue_breakdown?.by_status || [];
	const priorityBreakdown = data.queue_breakdown?.by_priority || [];
	const caseSla = data.case_sla;
	const agingBuckets = caseSla?.aging_buckets || [];
	const analystStats = caseSla?.analyst_stats || [];

	return (
		<div className="space-y-6">
			{isFlaggedOnly && (
				<div className="flex items-start gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">
					<AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-400" aria-hidden="true" />
					<div>
						<span className="font-semibold">Chế độ chỉ hồ sơ đã xác minh:</span>{' '}
						Các giao dịch không bị gắn cờ (<code className="font-mono">ALLOW</code>) chưa có nhãn thực tế nên{' '}
						<strong>Gian lận lọt lưới (Missed Fraud / VDR / bps)</strong> và{' '}
						<strong>Tỷ lệ làm phiền khách hàng (Customer Insult Rate)</strong> được hiển thị là{' '}
						<code className="font-mono">—</code> thay vì <code className="font-mono">0</code> để tránh sai lệch.
					</div>
				</div>
			)}

			{/* Hàng 1: 6 KPI Cards (3x2) */}
			<div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
				{/* 1. Tổng khối lượng quét */}
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between gap-2">
						<span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
							<span>Tổng khối lượng quét</span>
							<MetricInfoTooltip
								title="Tổng khối lượng quét"
								formula="SUM(amount) trên toàn bộ giao dịch trong phạm vi"
								meaning="Tổng giá trị tiền và số lượng giao dịch đã đi qua hệ thống phát hiện trong khoảng thời gian chọn."
							/>
						</span>
						<div className="p-2 rounded-lg bg-slate-800/80 text-slate-300">
							<DollarSign size={16} aria-hidden="true" />
						</div>
					</div>
					<div className="my-2">
						<div className="text-2xl font-bold font-mono tabular-nums text-slate-100">
							{formatCurrency(kpis.gross_scanned_volume)}
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{(kpis.gross_scanned_count ?? 0).toLocaleString()} giao dịch đã đánh giá ({kpis.flagged_tx_count ?? 0} bị gắn cờ)
						</div>
					</div>
				</div>

				{/* 2. Gian lận đã ngăn chặn + VDR */}
				<div className="bg-dark-900 border border-emerald-500/30 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between gap-2">
						<span className="text-xs font-semibold uppercase tracking-wider text-emerald-300 flex items-center gap-1.5">
							<span>Gian lận đã ngăn chặn</span>
							<MetricInfoTooltip
								title="Tỷ lệ bắt theo giá trị (VDR)"
								formula="VDR = Prevented $ / (Prevented $ + Missed Fraud $)"
								meaning="Trong 100 đồng gian lận thực tế, hệ thống chặn được bao nhiêu đồng. Quan trọng hơn đếm số ca vì 1 ca giá trị lớn ảnh hưởng lớn hơn nhiều ca nhỏ."
								benchmark="Tốt: ≥ 75–85%"
							/>
						</span>
						<div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
							<ShieldCheck size={16} aria-hidden="true" />
						</div>
					</div>
					<div className="my-2">
						<div className="flex items-baseline gap-2.5 flex-wrap">
							<span className="text-2xl font-bold font-mono tabular-nums text-emerald-400">
								{formatCurrency(kpis.confirmed_fraud_loss_prevented)}
							</span>
							<span className="text-xs font-mono tabular-nums px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
								{kpis.value_detection_rate != null
									? `${(kpis.value_detection_rate * 100).toFixed(1)}% VDR`
									: '— VDR'}
							</span>
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{(kpis.confirmed_fraud_count ?? 0).toLocaleString()} giao dịch gian lận đã chặn
						</div>
					</div>
				</div>

				{/* 3. Gian lận lọt lưới + Net Fraud Loss bps */}
				<div className="bg-dark-900 border border-rose-500/30 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between gap-2">
						<span className="text-xs font-semibold uppercase tracking-wider text-rose-300 flex items-center gap-1.5">
							<span>Gian lận lọt lưới</span>
							<MetricInfoTooltip
								title="Gian lận lọt lưới & Net Fraud Loss (bps)"
								formula="Missed $ = SUM(amount | ALLOW & fraud) · bps = (Missed $ / Gross $) × 10.000"
								meaning="Giá trị gian lận bị bỏ sót. 1 bps = 0,01% tổng doanh số giao dịch."
								benchmark="Chuẩn ngành thẻ: < 5–10 bps"
							/>
						</span>
						<div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
							<ShieldOff size={16} aria-hidden="true" />
						</div>
					</div>
					<div className="my-2">
						<div className="flex items-baseline gap-2.5 flex-wrap">
							<span className="text-2xl font-bold font-mono tabular-nums text-rose-400">
								{kpis.missed_fraud_amount != null ? formatCurrency(kpis.missed_fraud_amount) : '—'}
							</span>
							<span className="text-xs font-mono tabular-nums px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30">
								{kpis.net_fraud_loss_bps != null ? `${kpis.net_fraud_loss_bps.toFixed(1)} bps` : '— bps'}
							</span>
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{kpis.missed_fraud_count != null
								? `${kpis.missed_fraud_count.toLocaleString()} giao dịch gian lận không bị gắn cờ`
								: 'Cần bật nhãn dự phòng từ tập dữ liệu để đo FN'}
						</div>
					</div>
				</div>

				{/* 4. Ma sát khách hàng (Customer Insult Rate + Hard Decline vs Soft Review) */}
				<div className="bg-dark-900 border border-amber-500/30 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between gap-2">
						<span className="text-xs font-semibold uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
							<span>Ma sát khách hàng (Insult Rate)</span>
							<MetricInfoTooltip
								title="Customer Insult Rate (Tỷ lệ làm phiền)"
								formula="Insult Rate = FP / (TN + FP)"
								meaning="Trên tổng giao dịch của khách thật, tỷ lệ bị chặn nhầm (REJECT) hoặc đẩy xem xét nhầm (REVIEW)."
								benchmark="Hard Decline tốt: < 0,5–1%"
							/>
						</span>
						<div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
							<ShieldAlert size={16} aria-hidden="true" />
						</div>
					</div>
					<div className="my-2">
						<div className="flex items-baseline gap-2.5 flex-wrap">
							<span className="text-2xl font-bold font-mono tabular-nums text-amber-300">
								{kpis.customer_insult_rate != null
									? `${(kpis.customer_insult_rate * 100).toFixed(2)}%`
									: '—'}
							</span>
							<span className="text-xs font-mono tabular-nums text-slate-300">
								{formatCurrency(kpis.false_positive_friction_volume)} ({kpis.false_positive_count ?? 0} GD)
							</span>
						</div>
						<div className="text-[11px] text-slate-400 mt-1 font-mono tabular-nums">
							Chặn nhầm REJECT: {formatCurrency(kpis.hard_false_decline_amount)} ({kpis.hard_false_decline_count ?? 0}) · Xem xét REVIEW: {formatCurrency(kpis.soft_review_friction_amount)} ({kpis.soft_review_friction_count ?? 0})
						</div>
					</div>
				</div>

				{/* 5. Hiệu quả cảnh báo (Verified Precision & Alert:Fraud) */}
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between gap-2">
						<span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
							<span>Hiệu quả cảnh báo (Precision)</span>
							<MetricInfoTooltip
								title="Verified Precision & Alert:Fraud"
								formula="Precision = TP / (TP + FP) · Ratio = (TP + FP) / TP"
								meaning="Tỷ lệ cảnh báo đúng trong số cảnh báo đã có nhãn. Ratio 3:1 nghĩa là duyệt 3 cảnh báo thì có 1 gian lận thật."
								benchmark="Thực tế thẻ: Precision 20–50% (2:1 – 5:1)"
							/>
						</span>
						<div className="p-2 rounded-lg bg-brand-500/10 text-brand-400">
							<Target size={16} aria-hidden="true" />
						</div>
					</div>
					<div className="my-2">
						<div className="flex items-baseline gap-2.5">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">
								{kpis.verified_precision != null ? `${(kpis.verified_precision * 100).toFixed(1)}%` : '—'}
							</span>
							<span className="text-xs font-mono tabular-nums px-2 py-0.5 rounded bg-brand-500/15 text-brand-300 border border-brand-500/30">
								{kpis.alert_to_fraud_label || '—'} Cảnh báo:Gian lận
							</span>
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{kpis.reject_count ?? 0} REJECT / {kpis.review_count ?? 0} REVIEW đang áp dụng
						</div>
					</div>
				</div>

				{/* 6. Vận hành điều tra & MTTR / SLA */}
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between gap-2">
						<span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
							<span>Vận hành điều tra & SLA</span>
							<MetricInfoTooltip
								title="MTTR & Quá hạn SLA"
								formula="MTTR P50 = Trung vị (resolved_at − created_at)"
								meaning="Tốc độ xử lý hồ sơ điều tra và số hồ sơ vượt ngưỡng SLA (CRITICAL ≤ 4h, HIGH ≤ 24h, MEDIUM ≤ 72h)."
								benchmark="Critical ≤ 4h · High ≤ 24h · Medium ≤ 72h"
							/>
						</span>
						<div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
							<Clock size={16} aria-hidden="true" />
						</div>
					</div>
					<div className="my-2">
						<div className="flex items-baseline gap-2 flex-wrap">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">
								{((kpis.case_resolution_rate ?? 0) * 100).toFixed(1)}%
							</span>
							<span className="text-xs font-mono tabular-nums px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
								MTTR P50: {kpis.mttr_p50_hours != null ? `${kpis.mttr_p50_hours.toFixed(1)}h` : '—'}
							</span>
							<span className="text-xs font-mono tabular-nums px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
								Quá SLA: {kpis.sla_breach_count ?? 0}
							</span>
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{kpis.resolved_cases ?? 0}/{kpis.total_cases ?? 0} đã xử lý · {kpis.critical_high_backlog ?? 0} tồn đọng Crit/High
						</div>
					</div>
				</div>
			</div>

			{/* Hàng 2: Xu hướng bảo vệ, lọt lưới & ma sát theo thời gian giao dịch */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
				<div className="flex items-center justify-between mb-4">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Activity size={15} className="text-brand-400" aria-hidden="true" />
							<span>Xu hướng bảo vệ, lọt lưới & ma sát theo thời gian giao dịch</span>
							<MetricInfoTooltip
								title="Xu hướng theo ngày giao dịch"
								formula="Nhóm theo ngày tx_timestamp (fallback theo phiên quét nếu thiếu mốc giờ)"
								meaning="So sánh từng ngày giữa tiền gian lận chặn được (xanh), tiền lọt lưới (đỏ) và ma sát khách thật (vàng)."
							/>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Phân rã theo {data.financial_trends_granularity === 'JOB' ? 'phiên quét' : 'ngày giao dịch (tx_timestamp)'}
						</p>
					</div>
				</div>

				{financialTrends.length === 0 ? (
					<div className="h-64 flex items-center justify-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
						Không tìm thấy dữ liệu giao dịch trong phạm vi phân tích hiện tại.
					</div>
				) : (
					<div className="h-72 w-full">
						<ResponsiveContainer width="100%" height="100%">
							<ComposedChart data={financialTrends} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
								<CartesianGrid strokeDasharray="3 3" stroke={chartTokens.gridSubtleStroke} />
								<XAxis dataKey="x_label" stroke={chartTokens.axisStroke} tick={{ fontSize: 11 }} />
								<YAxis
									yAxisId="left"
									stroke={chartTokens.axisStroke}
									tick={{ fontSize: 11 }}
									tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
								/>
								<YAxis
									yAxisId="right"
									orientation="right"
									stroke="#38BDF8"
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
								<Bar
									yAxisId="left"
									dataKey="confirmed_fraud_amount"
									name="Ngăn chặn ($)"
									fill="#10B981"
									radius={[4, 4, 0, 0]}
								/>
								{!isFlaggedOnly && (
									<Bar
										yAxisId="left"
										dataKey="missed_fraud_amount"
										name="Lọt lưới ($)"
										fill="#F43F5E"
										radius={[4, 4, 0, 0]}
									/>
								)}
								<Bar
									yAxisId="left"
									dataKey="false_positive_amount"
									name="Ma sát FP ($)"
									fill="#F59E0B"
									radius={[4, 4, 0, 0]}
								/>
								<Line
									yAxisId="right"
									type="monotone"
									dataKey="alert_rate_pct"
									name="Tỷ lệ cảnh báo (%)"
									stroke="#38BDF8"
									strokeWidth={2}
									dot={{ r: 3 }}
								/>
							</ComposedChart>
						</ResponsiveContainer>
					</div>
				)}
			</div>

			{/* Hàng 3: Phễu 4 tầng đơn điệu giảm (7/12) + Hàng đợi điều tra, Backlog Aging & Điều tra viên (5/12) */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
				<div className="lg:col-span-7 bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="flex items-center justify-between mb-4">
						<div>
							<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
								<Filter size={15} className="text-brand-400" aria-hidden="true" />
								<span>Phễu chuyển đổi 4 tầng nhất quán</span>
								<MetricInfoTooltip
									title="Phễu chuyển đổi 4 tầng"
									formula="Tổng quét ≥ Bị gắn cờ ≥ Chuyển hồ sơ ≥ Đã xử lý"
									meaning="Đo tỷ lệ thu hẹp từ tổng giao dịch đầu vào đến số vụ việc được điều tra và đóng kết luận."
								/>
							</h3>
							<p className="text-xs text-slate-400 mt-0.5">
								Luôn đơn điệu giảm từ Quét suy luận đến Hồ sơ điều tra đã đóng
							</p>
						</div>
					</div>

					<div className="space-y-4">
						{funnel.map((stage, idx) => {
							const barColors = [
								'bg-slate-500',
								'bg-amber-500',
								'bg-brand-500',
								'bg-emerald-500',
							];
							const pct = (stage.conversion_rate ?? 0) * 100;
							const widthPct = Math.max(pct, (stage.tx_count ?? 0) > 0 ? 4 : 0);
							return (
								<div key={stage.stage} className="bg-dark-950/80 border border-dark-800 rounded-lg p-3.5">
									<div className="flex items-center justify-between text-xs mb-2">
										<div className="flex items-center gap-2">
											<span className="w-5 h-5 rounded-full bg-dark-800 border border-dark-700 text-slate-300 font-mono flex items-center justify-center text-[11px]">
												{idx + 1}
											</span>
											<span className="font-semibold text-slate-200">{stage.label || stage.stage}</span>
										</div>
										<div className="flex items-center gap-4 font-mono tabular-nums">
											<span className="text-slate-300 font-semibold">
												{(stage.tx_count ?? 0).toLocaleString()} GD
											</span>
											<span className="text-emerald-400 font-semibold">
												{formatCurrency(stage.amount)}
											</span>
											<span className="text-slate-400 w-14 text-right">
												{pct.toFixed(1)}%
											</span>
										</div>
									</div>
									<div className="w-full h-2 bg-dark-800 rounded-full overflow-hidden">
										<div
											className={`h-full rounded-full transition-all duration-300 ${barColors[idx % barColors.length]}`}
											style={{ width: `${Math.min(widthPct, 100)}%` }}
										/>
									</div>
								</div>
							);
						})}
					</div>
				</div>

				{/* Hàng đợi điều tra, Backlog Aging & Hiệu suất điều tra viên */}
				<div className="lg:col-span-5 bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-5">
					<div className="flex items-center justify-between">
						<div>
							<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
								<CheckCircle2 size={15} className="text-emerald-400" aria-hidden="true" />
								<span>Hàng đợi điều tra & SLA</span>
							</h3>
							<p className="text-xs text-slate-400 mt-0.5">
								MTTR P90: {caseSla?.mttr_p90_hours != null ? `${caseSla.mttr_p90_hours.toFixed(1)}h` : '—'} · Quá hạn SLA: {((caseSla?.sla_breach_rate ?? 0) * 100).toFixed(1)}%
							</p>
						</div>
						<button
							type="button"
							onClick={() => navigate('/investigation')}
							className="inline-flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 font-medium cursor-pointer"
						>
							<span>Hàng đợi đang mở</span>
							<ArrowUpRight size={13} aria-hidden="true" />
						</button>
					</div>

					{/* Trạng thái & Ưu tiên */}
					<div className="grid grid-cols-2 gap-2">
						{statusBreakdown.map((item) => (
							<div
								key={item.status}
								className="bg-dark-950 border border-dark-800 rounded-lg px-3 py-2 flex items-center justify-between"
							>
								<div>
									<div className="text-[11px] font-mono text-slate-300">{item.label || item.status}</div>
									<div className="text-[11px] font-mono text-slate-500">
										{formatCurrency(item.amount)}
									</div>
								</div>
								<span className="text-sm font-bold font-mono tabular-nums text-slate-100">
									{item.count}
								</span>
							</div>
						))}
						{priorityBreakdown
							.filter((p) => p.priority === 'CRITICAL' || p.priority === 'HIGH')
							.map((item) => (
								<div
									key={item.priority}
									className="bg-dark-950 border border-amber-500/20 rounded-lg px-3 py-2 flex items-center justify-between"
								>
									<div>
										<div className="text-[11px] font-mono text-amber-300">Ưu tiên {item.priority}</div>
										<div className="text-[11px] font-mono text-slate-500">
											{formatCurrency(item.total_amount)}
										</div>
									</div>
									<span className="text-sm font-bold font-mono tabular-nums text-amber-300">
										{item.total_count}
									</span>
								</div>
							))}
					</div>

					{/* Tuổi hồ sơ tồn đọng (Backlog Aging) */}
					<div>
						<div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
							Tuổi hồ sơ tồn đọng (Backlog Aging)
						</div>
						<div className="grid grid-cols-4 gap-2">
							{agingBuckets.map((b) => (
								<div
									key={b.bucket}
									className={`rounded-lg border p-2 text-center font-mono ${
										b.bucket === 'GT_3D' && b.count > 0
											? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
											: 'bg-dark-950 border-dark-800 text-slate-200'
									}`}
								>
									<div className="text-[10px] text-slate-400">{b.label}</div>
									<div className="text-base font-bold tabular-nums mt-0.5">{b.count}</div>
								</div>
							))}
						</div>
					</div>

					{/* Bảng thu gọn hiệu suất điều tra viên */}
					<div>
						<div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
							<Users size={12} aria-hidden="true" />
							<span>Hiệu suất theo điều tra viên</span>
						</div>
						{analystStats.length === 0 ? (
							<div className="text-xs text-slate-500 py-3 text-center bg-dark-950 rounded-lg border border-dark-800">
								Chưa có hồ sơ đã đóng để thống kê theo điều tra viên.
							</div>
						) : (
							<div className="overflow-x-auto">
								<table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
									<thead>
										<tr className="border-b border-dark-800 text-[10px] text-slate-400 uppercase">
											<th className="py-1.5 px-2">Điều tra viên</th>
											<th className="py-1.5 px-2 text-right">Đã xử lý</th>
											<th className="py-1.5 px-2 text-right">Gian lận %</th>
											<th className="py-1.5 px-2 text-right">MTTR</th>
											<th className="py-1.5 px-2 text-right">Quá SLA</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-dark-800/60">
										{analystStats.slice(0, 5).map((a) => (
											<tr key={a.analyst}>
												<td className="py-1.5 px-2 text-slate-200 font-semibold">{a.analyst}</td>
												<td className="py-1.5 px-2 text-right text-slate-300">{a.resolved_count}</td>
												<td className="py-1.5 px-2 text-right text-emerald-400">
													{(a.fraud_rate * 100).toFixed(0)}%
												</td>
												<td className="py-1.5 px-2 text-right text-cyan-300">
													{a.median_mttr_hours != null ? `${a.median_mttr_hours.toFixed(1)}h` : '—'}
												</td>
												<td className="py-1.5 px-2 text-right text-amber-300">{a.sla_breach_count}</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						)}
					</div>
				</div>
			</div>
		</div>
	);
};
