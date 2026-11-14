import React, { useState } from 'react';
import {
	ArrowUpRight,
	BrainCircuit,
	Gauge,
	Scale,
	ShieldCheck,
	Sliders,
	Sparkles,
} from 'lucide-react';
import {
	Bar,
	CartesianGrid,
	ComposedChart,
	Legend,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '@/hooks';
import type { EffectivenessAnalysisData } from '@/types';

interface EffectivenessTabProps {
	data?: EffectivenessAnalysisData;
	isLoading: boolean;
}

function formatCurrency(val: number | undefined | null): string {
	return `$${Number(val ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export const EffectivenessTab: React.FC<EffectivenessTabProps> = ({ data, isLoading }) => {
	const navigate = useNavigate();
	const { chartTokens } = useTheme();
	const [selectedThreshold, setSelectedThreshold] = useState<number>(0.5);

	if (isLoading) {
		return (
			<div className="space-y-4 animate-pulse">
				<div className="h-44 bg-dark-900 border border-dark-700/80 rounded-xl" />
				<div className="h-72 bg-dark-900 border border-dark-700/80 rounded-xl" />
			</div>
		);
	}

	if (!data || !data.attribution) {
		return null;
	}

	const { attribution } = data;
	const ruleLeaderboard = data.rule_leaderboard || [];
	const scoreCalibration = data.score_calibration || [];
	const thresholdCurve = data.threshold_simulator?.curve || [];
	const totalKnownFraud = data.threshold_simulator?.total_known_fraud_count ?? 0;

	const segments = attribution.segments || [];
	const aiSeg = segments.find((s) => s.segment === 'AI_EXCLUSIVE');
	const overlapSeg = segments.find((s) => s.segment === 'CONSENSUS_OVERLAP');
	const ruleSeg = segments.find((s) => s.segment === 'RULE_EXCLUSIVE');

	const aiPct = (attribution.ai_exclusive_catch_rate ?? aiSeg?.count_pct ?? 0) * 100;
	const overlapPct = (attribution.consensus_overlap_rate ?? overlapSeg?.count_pct ?? 0) * 100;
	const rulePct = (attribution.rule_exclusive_catch_rate ?? ruleSeg?.count_pct ?? 0) * 100;

	const activePoint =
		thresholdCurve.find((pt) => Math.abs(pt.threshold - selectedThreshold) < 0.01) ||
		thresholdCurve.find((pt) => Math.abs(pt.threshold - 0.5) < 0.01) ||
		thresholdCurve[0];

	return (
		<div className="space-y-6">
			{/* 1. AI vs. Rule Catch Attribution */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
				<div className="flex flex-wrap items-center justify-between gap-2 mb-4">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Sparkles size={15} className="text-brand-400" />
							<span>Phân bổ bắt gian lận: AI so với luật xác định</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Exclusive and overlapping contributions across {attribution.total_caught_fraud_count ?? 0} confirmed fraud events ({formatCurrency(attribution.total_caught_fraud_amount)} prevented)
						</p>
					</div>
				</div>

				{/* Stacked Visual Bar */}
				<div className="w-full h-3.5 bg-dark-950 border border-dark-800 rounded-full overflow-hidden flex mb-4">
					<div
						className="bg-cyan-500 h-full transition-all duration-300"
						style={{ width: `${aiPct}%` }}
						title={`Chỉ AI bắt: ${aiPct.toFixed(1)}%`}
					/>
					<div
						className="bg-purple-500 h-full transition-all duration-300"
						style={{ width: `${overlapPct}%` }}
						title={`Đồng thuận kết hợp: ${overlapPct.toFixed(1)}%`}
					/>
					<div
						className="bg-amber-500 h-full transition-all duration-300"
						style={{ width: `${rulePct}%` }}
						title={`Chỉ luật bắt: ${rulePct.toFixed(1)}%`}
					/>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					{/* AI-Only Catch */}
					<div className="bg-dark-950 border border-cyan-500/30 rounded-xl p-4">
						<div className="flex items-center justify-between text-xs text-cyan-300 font-semibold uppercase tracking-wider">
							<span>Chỉ AI bắt (XGBoost)</span>
							<BrainCircuit size={15} className="text-cyan-400" />
						</div>
						<div className="mt-2 flex items-baseline justify-between">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">
								{aiPct.toFixed(1)}%
							</span>
							<span className="text-xs font-mono tabular-nums text-cyan-300">
								{aiSeg?.fraud_count ?? 0} txs • {formatCurrency(aiSeg?.fraud_amount)}
							</span>
						</div>
						<p className="text-[11px] text-slate-400 mt-1.5">
							Được bắt hoàn toàn bởi xác suất ML (`model_score &ge; threshold`) mà không kích hoạt luật nào.
						</p>
					</div>

					{/* Hybrid Consensus */}
					<div className="bg-dark-950 border border-purple-500/30 rounded-xl p-4">
						<div className="flex items-center justify-between text-xs text-purple-300 font-semibold uppercase tracking-wider">
							<span>Đồng thuận kết hợp (AI + luật)</span>
							<ShieldCheck size={15} className="text-purple-400" />
						</div>
						<div className="mt-2 flex items-baseline justify-between">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">
								{overlapPct.toFixed(1)}%
							</span>
							<span className="text-xs font-mono tabular-nums text-purple-300">
								{overlapSeg?.fraud_count ?? 0} txs • {formatCurrency(overlapSeg?.fraud_amount)}
							</span>
						</div>
						<p className="text-[11px] text-slate-400 mt-1.5">
							High-confidence fraud flagged simultaneously by both XGBoost and deterministic rules.
						</p>
					</div>

					{/* Rule-Only Catch */}
					<div className="bg-dark-950 border border-amber-500/30 rounded-xl p-4">
						<div className="flex items-center justify-between text-xs text-amber-300 font-semibold uppercase tracking-wider">
							<span>Chỉ luật bắt (chính sách)</span>
							<Scale size={15} className="text-amber-400" />
						</div>
						<div className="mt-2 flex items-baseline justify-between">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">
								{rulePct.toFixed(1)}%
							</span>
							<span className="text-xs font-mono tabular-nums text-amber-300">
								{ruleSeg?.fraud_count ?? 0} txs • {formatCurrency(ruleSeg?.fraud_amount)}
							</span>
						</div>
						<p className="text-[11px] text-slate-400 mt-1.5">
							Được bắt bởi luật chính sách nghiệp vụ khi `model_score` vẫn dưới ngưỡng quyết định.
						</p>
					</div>
				</div>
			</div>

			{/* 2. Rule Ground-Truth Leaderboard */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5">
				<div className="flex items-center justify-between mb-4">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Scale size={15} className="text-emerald-400" />
							<span>Bảng xếp hạng luật theo nhãn thực tế</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Độ chính xác (Precision) thực nghiệm, tỷ lệ dương tính giả (FPR) và khối lượng gian lận đã ngăn chặn theo từng luật đang hoạt động
						</p>
					</div>
					<button
						type="button"
						onClick={() => navigate('/rules')}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 text-xs font-medium text-brand-300 border border-dark-700 transition-colors cursor-pointer"
					>
						<span>Điều chỉnh trong động cơ luật</span>
						<ArrowUpRight size={13} />
					</button>
				</div>

				{ruleLeaderboard.length === 0 ? (
					<div className="py-8 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
						Chưa ghi nhận lần kích hoạt luật nào trong phạm vi phân tích đã chọn.
					</div>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-left border-collapse">
							<thead>
								<tr className="border-b border-dark-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
									<th className="py-2.5 px-3">Luật</th>
									<th className="py-2.5 px-3">Thao tác</th>
									<th className="py-2.5 px-3 text-right">Triggers</th>
									<th className="py-2.5 px-3 text-right">TP / FP</th>
									<th className="py-2.5 px-3 text-right">Độ chính xác (Precision)</th>
									<th className="py-2.5 px-3">Tỷ lệ dương tính giả</th>
									<th className="py-2.5 px-3 text-right">Prevented ($)</th>
									<th className="py-2.5 px-3 text-center">Diagnostic Badge</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-dark-800/60 text-xs">
								{ruleLeaderboard.map((row) => {
									const badgeStyles: Record<string, string> = {
										HIGH_VALUE: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
										NOISY: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
										BALANCED: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
										UNVERIFIED: 'bg-slate-800 text-slate-400 border-slate-700',
									};
									const precPct = row.verified_precision != null ? row.verified_precision * 100 : 0;
									const fprPct = row.verified_fpr != null ? row.verified_fpr * 100 : 0;
									return (
										<tr key={row.rule_code} className="hover:bg-dark-800/40 transition-colors">
											<td className="py-2.5 px-3">
												<div className="font-mono font-semibold text-slate-100">{row.rule_code}</div>
												<div className="text-[11px] text-slate-400">{row.rule_name}</div>
											</td>
											<td className="py-2.5 px-3 font-mono">
												<span
													className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
														row.action === 'REJECT'
															? 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
															: 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
													}`}
												>
													{row.action}
												</span>
											</td>
											<td className="py-2.5 px-3 text-right font-mono tabular-nums text-slate-200">
												{(row.total_hits ?? 0).toLocaleString()}
											</td>
											<td className="py-2.5 px-3 text-right font-mono tabular-nums">
												<span className="text-emerald-400">{row.verified_tp ?? 0}</span>
												<span className="text-slate-600 mx-1">/</span>
												<span className="text-rose-400">{row.verified_fp ?? 0}</span>
											</td>
											<td className="py-2.5 px-3 text-right font-mono tabular-nums font-semibold text-slate-100">
												{row.verified_precision != null ? `${precPct.toFixed(1)}%` : '—'}
											</td>
											<td className="py-2.5 px-3 w-44">
												<div className="flex items-center gap-2">
													<div className="flex-1 h-2 bg-dark-950 rounded-full overflow-hidden">
														<div
															className={`h-full rounded-full ${
																fprPct >= 60 ? 'bg-rose-500' : 'bg-amber-400'
															}`}
															style={{ width: `${Math.min(fprPct, 100)}%` }}
														/>
													</div>
													<span className="font-mono tabular-nums text-[11px] text-slate-300 w-12 text-right">
														{row.verified_fpr != null ? `${fprPct.toFixed(1)}%` : '—'}
													</span>
												</div>
											</td>
											<td className="py-2.5 px-3 text-right font-mono tabular-nums font-semibold text-emerald-400">
												{formatCurrency(row.fraud_value_caught)}
											</td>
											<td className="py-2.5 px-3 text-center">
												<span
													className={`inline-block px-2 py-0.5 rounded border text-[10px] font-mono font-semibold ${
														badgeStyles[row.policy_health_tag] || badgeStyles.UNVERIFIED
													}`}
												>
													{row.policy_health_tag}
												</span>
											</td>
										</tr>
									);
								})}
							</tbody>
						</table>
					</div>
				)}
			</div>

			{/* 3. Score Calibration + What-If Threshold Simulator */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
				{/* Model Score Calibration Chart */}
				<div className="lg:col-span-7 bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="mb-4">
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Gauge size={15} className="text-cyan-400" />
							<span>Hiệu chỉnh điểm XGBoost (10 khoảng xác suất)</span>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Gian lận đã xác nhận so với dương tính giả & chưa xác minh theo từng nhóm xác suất (`0.0–1.0`)
						</p>
					</div>

					<div className="h-64 w-full">
						<ResponsiveContainer width="100%" height="100%">
							<ComposedChart data={scoreCalibration} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
								<CartesianGrid strokeDasharray="3 3" stroke={chartTokens.gridSubtleStroke} />
								<XAxis dataKey="bin" stroke={chartTokens.axisStroke} tick={{ fontSize: 11 }} />
								<YAxis stroke={chartTokens.axisStroke} tick={{ fontSize: 11 }} />
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
									dataKey="confirmed_fraud_count"
									name="Giao dịch gian lận đã xác nhận"
									stackId="a"
									fill="#10B981"
								/>
								<Bar
									dataKey="false_positive_count"
									name="Giao dịch dương tính giả"
									stackId="a"
									fill="#F43F5E"
								/>
								<Bar
									dataKey="unverified_count"
									name="Giao dịch chưa xác minh"
									stackId="a"
									fill="#3B82F6"
									radius={[4, 4, 0, 0]}
								/>
							</ComposedChart>
						</ResponsiveContainer>
					</div>
				</div>

				{/* Interactive What-If Threshold Simulator */}
				<div className="lg:col-span-5 bg-dark-900 border border-dark-700/80 rounded-xl p-5 flex flex-col justify-between">
					<div>
						<div className="flex items-center justify-between mb-3">
							<div>
								<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
									<Sliders size={15} className="text-brand-400" />
									<span>Mô phỏng ngưỡng quyết định</span>
								</h3>
								<p className="text-xs text-slate-400 mt-0.5">
									Mô phỏng độ nhạy, độ chính xác (Precision) và khối lượng hàng đợi xem xét trước khi áp dụng ngưỡng mới
								</p>
							</div>
							<span className="px-2.5 py-1 rounded-lg bg-brand-500/15 border border-brand-500/30 font-mono text-sm font-bold text-brand-300">
								τ = {selectedThreshold.toFixed(2)}
							</span>
						</div>

						<div className="my-4 bg-dark-950 border border-dark-800 rounded-xl p-4">
							<div className="flex items-center justify-between text-xs text-slate-400 font-mono mb-2">
								<span>0,05 (ưu tiên độ nhạy)</span>
								<span>0,50 (mặc định)</span>
								<span>0,95 — ưu tiên độ chính xác (Precision)</span>
							</div>
							<input
								type="range"
								min={0.05}
								max={0.95}
								step={0.05}
								value={selectedThreshold}
								onChange={(e) => setSelectedThreshold(Number(e.target.value))}
								className="w-full accent-brand-500 cursor-pointer"
							/>
						</div>

						{activePoint && (
							<div className="grid grid-cols-2 gap-3">
								<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
									<div className="text-[11px] uppercase tracking-wider text-slate-400">
										Độ nhạy ước tính
									</div>
									<div className="text-xl font-bold font-mono tabular-nums text-emerald-400 mt-1">
										{((activePoint.estimated_recall ?? 0) * 100).toFixed(1)}%
									</div>
									<div className="text-[11px] font-mono text-slate-500 mt-0.5">
										{activePoint.caught_fraud_count ?? 0} / {totalKnownFraud} known fraud caught
									</div>
								</div>

								<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
									<div className="text-[11px] uppercase tracking-wider text-slate-400">
										Độ chính xác (Precision) ước tính
									</div>
									<div className="text-xl font-bold font-mono tabular-nums text-cyan-400 mt-1">
										{((activePoint.estimated_precision ?? 0) * 100).toFixed(1)}%
									</div>
									<div className="text-[11px] font-mono text-slate-500 mt-0.5">
										{activePoint.false_positive_count ?? 0} estimated false positives
									</div>
								</div>

								<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
									<div className="text-[11px] uppercase tracking-wider text-slate-400">
										Khối lượng hàng đợi xem xét
									</div>
									<div className="text-xl font-bold font-mono tabular-nums text-slate-100 mt-1">
										{(activePoint.review_queue_volume ?? 0).toLocaleString()} txs
									</div>
									<div className="text-[11px] font-mono text-slate-500 mt-0.5">
										Transactions with score &ge; {activePoint.threshold.toFixed(2)}
									</div>
								</div>

								<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
									<div className="text-[11px] uppercase tracking-wider text-slate-400">
										Giảm FP so với đường cơ sở
									</div>
									<div
										className={`text-xl font-bold font-mono tabular-nums mt-1 ${
											(activePoint.fp_reduction_pct ?? 0) >= 0
												? 'text-emerald-400'
												: 'text-rose-400'
										}`}
									>
										{(activePoint.fp_reduction_pct ?? 0) >= 0 ? '-' : '+'}
										{Math.abs((activePoint.fp_reduction_pct ?? 0) * 100).toFixed(1)}%
									</div>
									<div className="text-[11px] font-mono text-slate-500 mt-0.5">
										False positive volume delta
									</div>
								</div>
							</div>
						)}
					</div>
				</div>
			</div>
		</div>
	);
};
