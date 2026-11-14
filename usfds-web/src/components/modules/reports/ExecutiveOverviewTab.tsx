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
	Target,
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
	const funnel = data.funnel || [];
	const financialTrends = data.financial_trends || [];
	const statusBreakdown = data.queue_breakdown?.by_status || [];
	const priorityBreakdown = data.queue_breakdown?.by_priority || [];

	return (
		<div className="space-y-6">
			{/* 6 Executive KPI Cards */}
			<div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
				{/* 1. Gross Scanned Volume */}
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between">
						<span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
							Gross Scanned Volume
						</span>
						<div className="p-2 rounded-lg bg-slate-800/80 text-slate-300">
							<DollarSign size={16} />
						</div>
					</div>
					<div className="my-2">
						<div className="text-2xl font-bold font-mono tabular-nums text-slate-100">
							{formatCurrency(kpis.gross_scanned_volume)}
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{(kpis.gross_scanned_count ?? 0).toLocaleString()} total transactions evaluated
						</div>
					</div>
				</div>

				{/* 2. Amount at Risk */}
				<div className="bg-dark-900 border border-amber-500/30 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between">
						<span className="text-xs font-semibold uppercase tracking-wider text-amber-300">
							Amount at Risk (Flagged)
						</span>
						<div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
							<AlertTriangle size={16} />
						</div>
					</div>
					<div className="my-2">
						<div className="text-2xl font-bold font-mono tabular-nums text-amber-300">
							{formatCurrency(kpis.amount_at_risk)}
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{(kpis.flagged_tx_count ?? 0).toLocaleString()} flagged events ({kpis.reject_count ?? 0} REJECT / {kpis.review_count ?? 0} REVIEW)
						</div>
					</div>
				</div>

				{/* 3. Confirmed Fraud Loss Prevented */}
				<div className="bg-dark-900 border border-emerald-500/30 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between">
						<span className="text-xs font-semibold uppercase tracking-wider text-emerald-300">
							Confirmed Fraud Prevented
						</span>
						<div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
							<ShieldCheck size={16} />
						</div>
					</div>
					<div className="my-2">
						<div className="text-2xl font-bold font-mono tabular-nums text-emerald-400">
							{formatCurrency(kpis.confirmed_fraud_loss_prevented)}
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{(kpis.confirmed_fraud_count ?? 0).toLocaleString()} verified fraud transactions stopped
						</div>
					</div>
				</div>

				{/* 4. False Positive Friction & Insult Rate */}
				<div className="bg-dark-900 border border-rose-500/30 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between">
						<span className="text-xs font-semibold uppercase tracking-wider text-rose-300">
							False Positive Friction & Insult Rate
						</span>
						<div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
							<ShieldAlert size={16} />
						</div>
					</div>
					<div className="my-2">
						<div className="flex items-baseline gap-3">
							<span className="text-2xl font-bold font-mono tabular-nums text-rose-400">
								{formatCurrency(kpis.false_positive_friction_volume)}
							</span>
							<span className="text-xs font-mono tabular-nums px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30">
								{((kpis.insult_rate ?? 0) * 100).toFixed(2)}% Insult Rate
							</span>
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{(kpis.false_positive_count ?? 0).toLocaleString()} legitimate transactions interrupted
						</div>
					</div>
				</div>

				{/* 5. Verified Precision & Alert-to-Fraud Ratio */}
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between">
						<span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
							Verified Precision & Alert Ratio
						</span>
						<div className="p-2 rounded-lg bg-brand-500/10 text-brand-400">
							<Target size={16} />
						</div>
					</div>
					<div className="my-2">
						<div className="flex items-baseline gap-3">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">
								{kpis.verified_precision != null ? `${(kpis.verified_precision * 100).toFixed(1)}%` : '—'}
							</span>
							<span className="text-xs font-mono tabular-nums px-2 py-0.5 rounded bg-brand-500/15 text-brand-300 border border-brand-500/30">
								{kpis.alert_to_fraud_label || '—'} Alert:Fraud
							</span>
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							True positive share among verified alerts
						</div>
					</div>
				</div>

				{/* 6. Case Resolution Rate & Backlog */}
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 flex flex-col justify-between">
					<div className="flex items-center justify-between">
						<span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
							Case Resolution Rate & Backlog
						</span>
						<div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
							<Clock size={16} />
						</div>
					</div>
					<div className="my-2">
						<div className="flex items-baseline gap-3">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">
								{((kpis.case_resolution_rate ?? 0) * 100).toFixed(1)}%
							</span>
							<span className="text-xs font-mono tabular-nums px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
								{(kpis.open_cases ?? 0) + (kpis.in_progress_cases ?? 0)} Open Backlog ({kpis.critical_high_backlog ?? 0} High/Crit)
							</span>
						</div>
						<div className="text-xs text-slate-400 mt-1 font-mono tabular-nums">
							{kpis.resolved_cases ?? 0} resolved out of {kpis.total_cases ?? 0} dispatched case(s)
						</div>
					</div>
				</div>
			</div>

			{/* Funnel + Case Queue Health Breakdown */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
				{/* 4-Stage End-to-End Funnel */}
				<div className="lg:col-span-7 bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="flex items-center justify-between mb-4">
						<div>
							<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
								<Filter size={15} className="text-brand-400" />
								<span>End-to-End Detection & Investigation Funnel</span>
							</h3>
							<p className="text-xs text-slate-400 mt-0.5">
								Conversion across Hybrid Inference scanning, Alerting, Case Intake, and Resolution
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
												{(stage.tx_count ?? 0).toLocaleString()} txs
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

				{/* Case Queue Status & Priority Breakdown */}
				<div className="lg:col-span-5 bg-dark-900 border border-dark-700/80 rounded-xl p-5 flex flex-col justify-between">
					<div>
						<div className="flex items-center justify-between mb-4">
							<div>
								<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
									<CheckCircle2 size={15} className="text-emerald-400" />
									<span>Investigation Queue & Priority Breakdown</span>
								</h3>
								<p className="text-xs text-slate-400 mt-0.5">
									Distribution of dispatched fraud cases by status and priority
								</p>
							</div>
							<button
								type="button"
								onClick={() => navigate('/investigation')}
								className="inline-flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 font-medium cursor-pointer"
							>
								<span>Open Queue</span>
								<ArrowUpRight size={13} />
							</button>
						</div>

						<div className="space-y-4">
							<div>
								<div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
									By Case Status
								</div>
								{statusBreakdown.length === 0 ? (
									<div className="text-xs text-slate-500 py-3 text-center bg-dark-950 rounded-lg border border-dark-800">
										No dispatched cases in current scope
									</div>
								) : (
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
									</div>
								)}
							</div>

							<div>
								<div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
									By Case Priority
								</div>
								{priorityBreakdown.length === 0 ? (
									<div className="text-xs text-slate-500 py-3 text-center bg-dark-950 rounded-lg border border-dark-800">
										No priority data available
									</div>
								) : (
									<div className="grid grid-cols-2 gap-2">
										{priorityBreakdown.map((item) => (
											<div
												key={item.priority}
												className="bg-dark-950 border border-dark-800 rounded-lg px-3 py-2 flex items-center justify-between"
											>
												<div>
													<div className="text-[11px] font-mono text-slate-300">{item.priority}</div>
													<div className="text-[11px] font-mono text-slate-500">
														{formatCurrency(item.total_amount)}
													</div>
												</div>
												<span className="text-sm font-bold font-mono tabular-nums text-slate-100">
													{item.total_count}
												</span>
											</div>
										))}
									</div>
								)}
							</div>
						</div>
					</div>
				</div>
			</div>

			{/* Financial Protection vs. Friction Trend */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
				<div className="flex items-center justify-between mb-4">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Activity size={15} className="text-brand-400" />
							<span>Financial Protection vs. Customer Friction Trend</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Comparison of Confirmed Fraud Prevented ($) vs. False Positive Friction ($) and Flagged Alert Count across Detection Runs
						</p>
					</div>
				</div>

				{financialTrends.length === 0 ? (
					<div className="h-64 flex items-center justify-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
						No detection run data found in current analytical scope.
					</div>
				) : (
					<div className="h-72 w-full">
						<ResponsiveContainer width="100%" height="100%">
							<ComposedChart data={financialTrends} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
								<CartesianGrid strokeDasharray="3 3" stroke={chartTokens.gridSubtleStroke} />
								<XAxis dataKey="job_name" stroke={chartTokens.axisStroke} tick={{ fontSize: 11 }} />
								<YAxis
									yAxisId="left"
									stroke={chartTokens.axisStroke}
									tick={{ fontSize: 11 }}
									tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
								/>
								<YAxis
									yAxisId="right"
									orientation="right"
									stroke={chartTokens.axisLabel}
									tick={{ fontSize: 11 }}
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
									name="Confirmed Fraud Prevented ($)"
									fill="#10B981"
									radius={[4, 4, 0, 0]}
								/>
								<Bar
									yAxisId="left"
									dataKey="false_positive_amount"
									name="False Positive Friction ($)"
									fill="#F43F5E"
									radius={[4, 4, 0, 0]}
								/>
								<Line
									yAxisId="right"
									type="monotone"
									dataKey="flagged_count"
									name="Flagged Transactions"
									stroke="#38BDF8"
									strokeWidth={2}
									dot={{ r: 3 }}
								/>
							</ComposedChart>
						</ResponsiveContainer>
					</div>
				)}
			</div>
		</div>
	);
};
