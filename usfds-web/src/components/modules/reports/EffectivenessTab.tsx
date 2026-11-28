import React, { useMemo, useState } from 'react';
import {
	Activity,
	AlertTriangle,
	ArrowUpRight,
	BrainCircuit,
	ChevronDown,
	ChevronUp,
	Gauge,
	Layers,
	Scale,
	ShieldCheck,
	Sliders,
	Sparkles,
	TrendingUp,
} from 'lucide-react';
import {
	Bar,
	CartesianGrid,
	ComposedChart,
	Legend,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '@/hooks';
import type {
	DualThresholdEvaluation,
	EffectivenessAnalysisData,
	ThresholdSimulationPoint,
} from '@/types';
import { MetricInfoTooltip } from './MetricInfoTooltip';

interface EffectivenessTabProps {
	data?: EffectivenessAnalysisData;
	isLoading: boolean;
}

function formatCurrency(val: number | undefined | null): string {
	return `$${Number(val ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function evaluateDualClient(
	curve: ThresholdSimulationPoint[],
	mode: 'hybrid' | 'model_only',
	tauReview: number,
	tauReject: number,
	totalKnownFraudAmt: number,
	reviewCost: number,
	falseDeclineRatio: number
): DualThresholdEvaluation | null {
	if (curve.length === 0) {
		return null;
	}
	const effReject = Math.max(tauReview, tauReject);
	const pickClosest = (target: number) =>
		curve.reduce((best, pt) =>
			Math.abs(pt.threshold - target) < Math.abs(best.threshold - target) ? pt : best
		);
	const ptRev = pickClosest(tauReview);
	const ptRej = pickClosest(effReject);
	const revBucket = ptRev[mode];
	const rejBucket = ptRej[mode];
	if (!revBucket || !rejBucket) {
		return null;
	}

	const caughtCnt = revBucket.flagged_tp_count;
	const caughtAmt = revBucket.flagged_tp_amount;
	const reviewCnt = Math.max(0, revBucket.flagged_count - rejBucket.reject_count);
	const rejectCnt = rejBucket.reject_count;
	const hardFpCnt = rejBucket.reject_fp_count;
	const hardFpAmt = rejBucket.reject_fp_amount;
	const softFpCnt = Math.max(0, revBucket.flagged_fp_count - hardFpCnt);
	const totalEval = caughtCnt + revBucket.flagged_fp_count;
	const vdr = totalKnownFraudAmt > 0 ? caughtAmt / totalKnownFraudAmt : 0;
	const precision = totalEval > 0 ? caughtCnt / totalEval : 0;
	const netSavings = caughtAmt - reviewCnt * reviewCost - hardFpAmt * falseDeclineRatio;

	return {
		tau_review: ptRev.threshold,
		tau_reject: ptRej.threshold,
		caught_fraud_count: caughtCnt,
		caught_fraud_amount: caughtAmt,
		vdr,
		precision,
		review_queue_count: reviewCnt,
		reject_count: rejectCnt,
		hard_false_decline_count: hardFpCnt,
		hard_false_decline_amount: hardFpAmt,
		soft_review_fp_count: softFpCnt,
		net_savings: netSavings,
	};
}

const PSI_BADGE_MAP: Record<string, { label: string; className: string }> = {
	STABLE: { label: 'Ổn định (< 0,10)', className: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
	MODERATE_SHIFT: { label: 'Cảnh báo dịch chuyển', className: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
	SIGNIFICANT_SHIFT: { label: 'Cần retrain (> 0,25)', className: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
	INSUFFICIENT_DATA: { label: 'Thiếu mẫu so sánh', className: 'bg-slate-800 text-slate-400 border-slate-700' },
};

export const EffectivenessTab: React.FC<EffectivenessTabProps> = ({ data, isLoading }) => {
	const navigate = useNavigate();
	const { chartTokens } = useTheme();
	const [calibrationMode, setCalibrationMode] = useState<'equal_width' | 'equal_count'>('equal_width');
	const [expandedRule, setExpandedRule] = useState<string | null>(null);
	const [showFnDrawer, setShowFnDrawer] = useState<boolean>(false);
	const [tauReview, setTauReview] = useState<number>(0.5);
	const [tauReject, setTauReject] = useState<number>(0.8);
	const [reviewCost, setReviewCost] = useState<number>(5);
	const [falseDeclinePct, setFalseDeclinePct] = useState<number>(15);
	const [suggestMode, setSuggestMode] = useState<'hybrid' | 'model_only'>('hybrid');

	const thresholdCurve = data?.threshold_simulator?.curve || [];
	const totalKnownFraudAmt = data?.threshold_simulator?.total_known_fraud_amount ?? 0;

	const hybridEval = useMemo(
		() =>
			evaluateDualClient(
				thresholdCurve,
				'hybrid',
				tauReview,
				tauReject,
				totalKnownFraudAmt,
				reviewCost,
				falseDeclinePct / 100
			),
		[thresholdCurve, tauReview, tauReject, totalKnownFraudAmt, reviewCost, falseDeclinePct]
	);

	const modelOnlyEval = useMemo(
		() =>
			evaluateDualClient(
				thresholdCurve,
				'model_only',
				tauReview,
				tauReject,
				totalKnownFraudAmt,
				reviewCost,
				falseDeclinePct / 100
			),
		[thresholdCurve, tauReview, tauReject, totalKnownFraudAmt, reviewCost, falseDeclinePct]
	);

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
	const fnSamples = data.fn_samples || [];
	const modelHealth = data.model_health;
	const psiMeta = PSI_BADGE_MAP[modelHealth?.psi_status || 'INSUFFICIENT_DATA'] || PSI_BADGE_MAP.INSUFFICIENT_DATA;
	const calibrationBins =
		(calibrationMode === 'equal_count'
			? data.score_calibration_modes?.equal_count
			: data.score_calibration_modes?.equal_width) ||
		data.score_calibration ||
		[];
	const calibrationChartData = calibrationBins.map((b) => ({
		...b,
		ideal_pct: Number(((b.mean_predicted_score ?? 0) * 100).toFixed(2)),
		observed_pct: b.observed_fraud_rate != null ? Number((b.observed_fraud_rate * 100).toFixed(2)) : null,
	}));
	const liftCurve = (data.lift_gain_curve || []).map((pt) => ({
		...pt,
		gain_count_100: Number(((pt.gain_count_pct ?? 0) * 100).toFixed(1)),
		gain_amount_100: Number(((pt.gain_amount_pct ?? 0) * 100).toFixed(1)),
	}));
	const driftBins = (data.score_drift?.bins || []).map((b) => ({
		...b,
		baseline_100: Number(((b.baseline_pct ?? 0) * 100).toFixed(1)),
		current_100: Number(((b.current_pct ?? 0) * 100).toFixed(1)),
	}));
	const modelComparison = data.model_comparison || [];

	const segments = attribution.segments || [];
	const aiSeg = segments.find((s) => s.segment === 'AI_EXCLUSIVE');
	const overlapSeg = segments.find((s) => s.segment === 'CONSENSUS_OVERLAP');
	const ruleSeg = segments.find((s) => s.segment === 'RULE_EXCLUSIVE');

	const aiPct = (attribution.ai_exclusive_catch_rate ?? aiSeg?.count_pct ?? 0) * 100;
	const overlapPct = (attribution.consensus_overlap_rate ?? overlapSeg?.count_pct ?? 0) * 100;
	const rulePct = (attribution.rule_exclusive_catch_rate ?? ruleSeg?.count_pct ?? 0) * 100;

	const applyRecommendation = (key: 'capacity_top_k' | 'target_precision' | 'max_net_savings') => {
		const rec = data.threshold_simulator?.recommendations?.[suggestMode]?.[key];
		if (!rec) {
			return;
		}
		setTauReview(rec.tau_review);
		setTauReject(Math.max(rec.tau_review, rec.tau_reject));
	};

	return (
		<div className="space-y-6">
			{/* Hàng 1: Phân bổ AI vs. Luật + Dải Sức khỏe Mô hình */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-5">
				<div className="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Sparkles size={15} className="text-brand-400" aria-hidden="true" />
							<span>Phân bổ bắt gian lận: Mô hình AI so với Luật nghiệp vụ</span>
							<MetricInfoTooltip
								title="Phân bổ đóng góp AI vs. Luật"
								formula="Chỉ AI (model hit, no rule) · Đồng thuận (cả hai) · Chỉ luật (rule hit, score < ngưỡng)"
								meaning="Đo giá trị gia tăng riêng của mô hình AI so với tập luật thủ công đang chạy."
							/>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Đóng góp độc lập và giao thoa trên {attribution.total_caught_fraud_count ?? 0} ca gian lận ({formatCurrency(attribution.total_caught_fraud_amount)} đã chặn)
						</p>
					</div>
				</div>

				<div className="w-full h-3.5 bg-dark-950 border border-dark-800 rounded-full overflow-hidden flex">
					<div className="bg-cyan-500 h-full transition-all duration-300" style={{ width: `${aiPct}%` }} title={`Chỉ AI bắt: ${aiPct.toFixed(1)}%`} />
					<div className="bg-purple-500 h-full transition-all duration-300" style={{ width: `${overlapPct}%` }} title={`Đồng thuận: ${overlapPct.toFixed(1)}%`} />
					<div className="bg-amber-500 h-full transition-all duration-300" style={{ width: `${rulePct}%` }} title={`Chỉ luật bắt: ${rulePct.toFixed(1)}%`} />
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div className="bg-dark-950 border border-cyan-500/30 rounded-xl p-4">
						<div className="flex items-center justify-between text-xs text-cyan-300 font-semibold uppercase tracking-wider">
							<span>Chỉ mô hình AI bắt</span>
							<BrainCircuit size={15} className="text-cyan-400" aria-hidden="true" />
						</div>
						<div className="mt-2 flex items-baseline justify-between">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">{aiPct.toFixed(1)}%</span>
							<span className="text-xs font-mono tabular-nums text-cyan-300">
								{aiSeg?.fraud_count ?? 0} GD • {formatCurrency(aiSeg?.fraud_amount)}
							</span>
						</div>
						<p className="text-[11px] text-slate-400 mt-1.5">
							Phát hiện hoàn toàn bởi điểm xác suất AI mà không kích hoạt luật nghiệp vụ nào.
						</p>
					</div>

					<div className="bg-dark-950 border border-purple-500/30 rounded-xl p-4">
						<div className="flex items-center justify-between text-xs text-purple-300 font-semibold uppercase tracking-wider">
							<span>Đồng thuận kết hợp (AI + Luật)</span>
							<ShieldCheck size={15} className="text-purple-400" aria-hidden="true" />
						</div>
						<div className="mt-2 flex items-baseline justify-between">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">{overlapPct.toFixed(1)}%</span>
							<span className="text-xs font-mono tabular-nums text-purple-300">
								{overlapSeg?.fraud_count ?? 0} GD • {formatCurrency(overlapSeg?.fraud_amount)}
							</span>
						</div>
						<p className="text-[11px] text-slate-400 mt-1.5">
							Gian lận độ tin cậy cao bị cả mô hình AI và tập luật đồng thời gắn cờ.
						</p>
					</div>

					<div className="bg-dark-950 border border-amber-500/30 rounded-xl p-4">
						<div className="flex items-center justify-between text-xs text-amber-300 font-semibold uppercase tracking-wider">
							<span>Chỉ luật nghiệp vụ bắt</span>
							<Scale size={15} className="text-amber-400" aria-hidden="true" />
						</div>
						<div className="mt-2 flex items-baseline justify-between">
							<span className="text-2xl font-bold font-mono tabular-nums text-slate-100">{rulePct.toFixed(1)}%</span>
							<span className="text-xs font-mono tabular-nums text-amber-300">
								{ruleSeg?.fraud_count ?? 0} GD • {formatCurrency(ruleSeg?.fraud_amount)}
							</span>
						</div>
						<p className="text-[11px] text-slate-400 mt-1.5">
							Bắt bởi tập luật chính sách khi điểm mô hình AI còn dưới ngưỡng quyết định.
						</p>
					</div>
				</div>

				{/* Dải Sức khỏe Mô hình */}
				<div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-dark-800">
					<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
						<div className="text-[11px] text-slate-400 flex items-center gap-1">
							<span>KS Statistic</span>
							<MetricInfoTooltip
								title="KS Statistic"
								formula="KS = max |CDF_fraud(s) − CDF_legit(s)|"
								meaning="Đo độ tách biệt phân phối điểm giữa gian lận và giao dịch hợp lệ."
								benchmark="0,2–0,4 đạt · > 0,4 tốt"
							/>
						</div>
						<div className="text-lg font-bold font-mono tabular-nums text-emerald-400 mt-1">
							{modelHealth?.ks_statistic != null ? modelHealth.ks_statistic.toFixed(3) : '—'}
						</div>
					</div>
					<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
						<div className="text-[11px] text-slate-400 flex items-center gap-1">
							<span>Brier Score</span>
							<MetricInfoTooltip
								title="Brier Score"
								formula="mean((model_score − y)²)"
								meaning="Sai số bình phương trung bình của xác suất dự báo. Càng gần 0 càng chính xác."
								benchmark="< 0,10 tốt"
							/>
						</div>
						<div className="text-lg font-bold font-mono tabular-nums text-cyan-300 mt-1">
							{modelHealth?.brier_score != null ? modelHealth.brier_score.toFixed(4) : '—'}
						</div>
					</div>
					<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
						<div className="text-[11px] text-slate-400 flex items-center gap-1">
							<span>ECE (Độ lệch hiệu chỉnh)</span>
							<MetricInfoTooltip
								title="Expected Calibration Error (ECE)"
								formula="Σ (n_b / N) × |Observed_b − MeanPred_b|"
								meaning="Độ lệch trung bình có trọng số giữa xác suất dự đoán và tỷ lệ gian lận thực tế."
								benchmark="< 0,05 hiệu chỉnh tốt"
							/>
						</div>
						<div className="text-lg font-bold font-mono tabular-nums text-slate-100 mt-1">
							{modelHealth?.ece != null ? modelHealth.ece.toFixed(4) : '—'}
						</div>
					</div>
					<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
						<div className="text-[11px] text-slate-400 flex items-center gap-1">
							<span>Score Drift (PSI)</span>
							<MetricInfoTooltip
								title="Population Stability Index (PSI)"
								formula="Σ (p_cur − p_base) × ln(p_cur / p_base)"
								meaning="Đo mức độ dịch chuyển phân phối điểm AI giữa nửa đầu và nửa sau giai đoạn."
								benchmark="< 0,10 ổn định · > 0,25 cần retrain"
							/>
						</div>
						<div className="flex items-center gap-2 mt-1 flex-wrap">
							<span className="text-lg font-bold font-mono tabular-nums text-slate-100">
								{modelHealth?.psi != null ? modelHealth.psi.toFixed(4) : '—'}
							</span>
							<span className={`px-2 py-0.5 rounded border text-[10px] font-mono font-semibold ${psiMeta.className}`}>
								{psiMeta.label}
							</span>
						</div>
					</div>
				</div>
			</div>

			{/* Hàng 2: Bảng xếp hạng Tập luật + Drawer Mẫu sai sót FP/FN */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-4">
				<div className="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Scale size={15} className="text-emerald-400" aria-hidden="true" />
							<span>Bảng xếp hạng tập luật theo nhãn thực tế</span>
							<MetricInfoTooltip
								title="FAR & Bắt độc nhất (Unique Catch)"
								formula="FAR = FP / (TP + FP) · Unique Catch = gian lận chỉ duy nhất luật này match (không trùng AI/luật khác)"
								meaning="Phát hiện luật dư thừa (Unique Catch = 0 + FAR cao) và cảnh báo Mẫu nhỏ (n < 30)."
								benchmark="FAR ≥ 70% → NOISY"
							/>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							Độ chính xác (Precision), tỷ lệ báo giả (FAR), đóng góp bắt độc nhất (Unique Catch) và mẫu sai sót
						</p>
					</div>
					<div className="flex items-center gap-2">
						{fnSamples.length > 0 && (
							<button
								type="button"
								onClick={() => setShowFnDrawer((v) => !v)}
								className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-xs font-medium text-rose-300 border border-rose-500/30 cursor-pointer"
							>
								<span>Xem {fnSamples.length} mẫu lọt lưới (FN)</span>
								{showFnDrawer ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
							</button>
						)}
						<button
							type="button"
							onClick={() => navigate('/rules')}
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 text-xs font-medium text-brand-300 border border-dark-700 transition-colors cursor-pointer"
						>
							<span>Điều chỉnh trong Rule Studio</span>
							<ArrowUpRight size={13} aria-hidden="true" />
						</button>
					</div>
				</div>

				{showFnDrawer && fnSamples.length > 0 && (
					<div className="bg-dark-950 border border-rose-500/30 rounded-lg p-3 space-y-2">
						<div className="text-xs font-semibold text-rose-300">
							Top {fnSamples.length} giao dịch gian lận lọt lưới toàn hệ thống (ALLOW nhưng nhãn thực tế = 1)
						</div>
						<div className="overflow-x-auto">
							<table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
								<thead>
									<tr className="border-b border-dark-800 text-[10px] text-slate-400 uppercase">
										<th className="py-1 px-2">Event ID</th>
										<th className="py-1 px-2">User</th>
										<th className="py-1 px-2 text-right">Số tiền</th>
										<th className="py-1 px-2 text-right">AI Score</th>
										<th className="py-1 px-2">Thời gian</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800/60">
									{fnSamples.map((s) => (
										<tr key={s.event_id}>
											<td className="py-1 px-2 text-slate-200">{s.event_id}</td>
											<td className="py-1 px-2 text-slate-400">{s.user_id}</td>
											<td className="py-1 px-2 text-right text-rose-300">{formatCurrency(s.amount)}</td>
											<td className="py-1 px-2 text-right text-slate-300">{s.model_score.toFixed(4)}</td>
											<td className="py-1 px-2 text-slate-400">{s.tx_timestamp || '—'}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</div>
				)}

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
									<th className="py-2.5 px-3">Hành động</th>
									<th className="py-2.5 px-3 text-right">Số lần nổ</th>
									<th className="py-2.5 px-3 text-right">TP / FP</th>
									<th className="py-2.5 px-3 text-right">Precision</th>
									<th className="py-2.5 px-3">Tỷ lệ báo giả (FAR)</th>
									<th className="py-2.5 px-3 text-right">Bắt độc nhất</th>
									<th className="py-2.5 px-3 text-right">Ngăn chặn ($)</th>
									<th className="py-2.5 px-3 text-center">Đánh giá</th>
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
									const farRaw = row.false_alert_rate ?? row.verified_fpr;
									const farPct = farRaw != null ? farRaw * 100 : 0;
									const isExpanded = expandedRule === row.rule_code;
									return (
										<React.Fragment key={row.rule_code}>
											<tr className="hover:bg-dark-800/40 transition-colors">
												<td className="py-2.5 px-3">
													<div className="flex items-center gap-2">
														<span className="font-mono font-semibold text-slate-100">{row.rule_code}</span>
														{row.is_small_sample && (
															<span className="px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px] font-mono">
																Mẫu nhỏ (&lt;30)
															</span>
														)}
													</div>
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
																className={`h-full rounded-full ${farPct >= 70 ? 'bg-rose-500' : 'bg-amber-400'}`}
																style={{ width: `${Math.min(farPct, 100)}%` }}
															/>
														</div>
														<span className="font-mono tabular-nums text-[11px] text-slate-300 w-12 text-right">
															{farRaw != null ? `${farPct.toFixed(1)}%` : '—'}
														</span>
													</div>
												</td>
												<td className="py-2.5 px-3 text-right font-mono tabular-nums text-cyan-300">
													{formatCurrency(row.unique_catch_amount)} ({row.unique_catch_count ?? 0})
												</td>
												<td className="py-2.5 px-3 text-right font-mono tabular-nums font-semibold text-emerald-400">
													{formatCurrency(row.fraud_value_caught)}
												</td>
												<td className="py-2.5 px-3 text-center">
													<div className="flex items-center justify-center gap-1.5">
														<span
															className={`inline-block px-2 py-0.5 rounded border text-[10px] font-mono font-semibold ${
																badgeStyles[row.policy_health_tag] || badgeStyles.UNVERIFIED
															}`}
														>
															{row.policy_health_tag}
														</span>
														{(row.fp_samples?.length ?? 0) > 0 && (
															<button
																type="button"
																onClick={() => setExpandedRule(isExpanded ? null : row.rule_code)}
																className="text-[10px] font-mono text-brand-300 hover:underline cursor-pointer"
															>
																{isExpanded ? 'Ẩn FP' : `FP (${row.fp_samples.length})`}
															</button>
														)}
													</div>
												</td>
											</tr>
											{isExpanded && row.fp_samples.length > 0 && (
												<tr className="bg-dark-950/70">
													<td colSpan={9} className="p-3">
														<div className="text-[11px] font-semibold text-amber-300 mb-1.5">
															Top {row.fp_samples.length} mẫu báo giả (FP) của {row.rule_code}
														</div>
														<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 font-mono text-[11px]">
															{row.fp_samples.map((fp) => (
																<div key={fp.event_id} className="border border-dark-800 rounded px-2.5 py-1.5 bg-dark-900 flex items-center justify-between">
																	<span className="text-slate-200">{fp.event_id} ({fp.user_id})</span>
																	<span className="text-amber-300">{formatCurrency(fp.amount)}</span>
																</div>
															))}
														</div>
													</td>
												</tr>
											)}
										</React.Fragment>
									);
								})}
							</tbody>
						</table>
					</div>
				)}
			</div>

			{/* Hàng 3: Calibration Reliability Curve (6/12) + Top-K Cumulative Gain / Lift (6/12) */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
				<div className="lg:col-span-6 bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="flex flex-wrap items-center justify-between gap-2 mb-4">
						<div>
							<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
								<Gauge size={15} className="text-cyan-400" aria-hidden="true" />
								<span>Đường cong hiệu chỉnh xác suất (Calibration Curve)</span>
								<MetricInfoTooltip
									title="Đường cong hiệu chỉnh xác suất"
									formula="So sánh Mean Predicted Score (%) với Observed Fraud Rate (%)"
									meaning="Nếu đường thực nghiệm bám sát đường lý tưởng y = x thì điểm xác suất của mô hình phản ánh đúng rủi ro thực tế."
									benchmark="ECE < 0,05"
								/>
							</h3>
							<p className="text-xs text-slate-400 mt-0.5">
								Xác suất dự báo trung bình so với tỷ lệ gian lận thực nghiệm và mật độ mẫu
							</p>
						</div>
						<div className="inline-flex rounded-lg bg-dark-950 p-0.5 border border-dark-800 text-[11px]">
							<button
								type="button"
								aria-pressed={calibrationMode === 'equal_width'}
								onClick={() => setCalibrationMode('equal_width')}
								className={`px-2.5 py-1 rounded-md cursor-pointer ${
									calibrationMode === 'equal_width' ? 'bg-brand-600 text-white' : 'text-slate-400'
								}`}
							>
								Khoảng đều (Uniform)
							</button>
							<button
								type="button"
								aria-pressed={calibrationMode === 'equal_count'}
								onClick={() => setCalibrationMode('equal_count')}
								className={`px-2.5 py-1 rounded-md cursor-pointer ${
									calibrationMode === 'equal_count' ? 'bg-brand-600 text-white' : 'text-slate-400'
								}`}
							>
								Phân vị đều (Equal-Count)
							</button>
						</div>
					</div>

					<div className="h-64 w-full">
						<ResponsiveContainer width="100%" height="100%">
							<ComposedChart data={calibrationChartData} margin={{ top: 10, right: 16, left: 0, bottom: 5 }}>
								<CartesianGrid strokeDasharray="3 3" stroke={chartTokens.gridSubtleStroke} />
								<XAxis dataKey="bin" stroke={chartTokens.axisStroke} tick={{ fontSize: 10 }} />
								<YAxis yAxisId="left" stroke={chartTokens.axisStroke} tick={{ fontSize: 11 }} unit="%" domain={[0, 100]} />
								<YAxis yAxisId="right" orientation="right" stroke={chartTokens.axisLabel} tick={{ fontSize: 10 }} />
								<Tooltip
									contentStyle={{
										backgroundColor: chartTokens.tooltipBg,
										borderColor: chartTokens.tooltipBorder,
										color: chartTokens.tooltipText,
										borderRadius: '0.5rem',
										fontSize: '12px',
									}}
								/>
								<Legend wrapperStyle={{ fontSize: '11px' }} />
								<Bar yAxisId="right" dataKey="total_count" name="Số lượng mẫu" fill={chartTokens.inactiveBar} opacity={0.35} radius={[3, 3, 0, 0]} />
								<Line yAxisId="left" type="monotone" dataKey="ideal_pct" name="Lý tưởng (y = x)" stroke="#94A3B8" strokeDasharray="4 4" dot={false} />
								<Line yAxisId="left" type="monotone" dataKey="observed_pct" name="Tỷ lệ gian lận thực nghiệm (%)" stroke="#10B981" strokeWidth={2} dot={{ r: 3 }} />
							</ComposedChart>
						</ResponsiveContainer>
					</div>
				</div>

				{/* Top-K Cumulative Gain / Lift */}
				<div className="lg:col-span-6 bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<div className="mb-3">
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<TrendingUp size={15} className="text-emerald-400" aria-hidden="true" />
							<span>Đường cong bắt gian lận Top-K (Cumulative Gain / Lift)</span>
							<MetricInfoTooltip
								title="Đường cong bắt gian lận Top-K"
								formula="Xếp hạng theo model_score giảm dần → đo % Fraud $ và % Fraud Count ở Top K%"
								meaning="Trả lời câu hỏi: Nếu đội điều tra chỉ đủ sức xem 5% giao dịch điểm cao nhất thì bắt được bao nhiêu % tiền gian lận?"
							/>
						</h3>
						<div className="flex flex-wrap gap-2 mt-2 font-mono text-[11px]">
							{liftCurve
								.filter((p) => p.top_pct === 1 || p.top_pct === 5 || p.top_pct === 10)
								.map((p) => (
									<span key={p.top_pct} className="px-2 py-0.5 rounded bg-dark-950 border border-dark-800 text-slate-200">
										{p.label}: <strong className="text-emerald-400">{p.gain_amount_100}% $</strong> (Lift {p.lift}×)
									</span>
								))}
						</div>
					</div>

					<div className="h-56 w-full">
						<ResponsiveContainer width="100%" height="100%">
							<LineChart data={liftCurve} margin={{ top: 10, right: 16, left: 0, bottom: 5 }}>
								<CartesianGrid strokeDasharray="3 3" stroke={chartTokens.gridSubtleStroke} />
								<XAxis dataKey="label" stroke={chartTokens.axisStroke} tick={{ fontSize: 10 }} />
								<YAxis stroke={chartTokens.axisStroke} tick={{ fontSize: 11 }} unit="%" domain={[0, 100]} />
								<Tooltip
									contentStyle={{
										backgroundColor: chartTokens.tooltipBg,
										borderColor: chartTokens.tooltipBorder,
										color: chartTokens.tooltipText,
										borderRadius: '0.5rem',
										fontSize: '12px',
									}}
								/>
								<Legend wrapperStyle={{ fontSize: '11px' }} />
								<Line type="monotone" dataKey="gain_amount_100" name="% Giá trị gian lận ($)" stroke="#10B981" strokeWidth={2} dot={{ r: 3 }} />
								<Line type="monotone" dataKey="gain_count_100" name="% Số ca gian lận" stroke="#38BDF8" strokeWidth={2} dot={{ r: 3 }} />
							</LineChart>
						</ResponsiveContainer>
					</div>
				</div>
			</div>

			{/* Hàng 4: Bộ Mô phỏng Ngưỡng Kép (Dual-Threshold & Cost-Aware Simulator — Hybrid vs Model-only song song) */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-4">
				<div className="flex flex-wrap items-center justify-between gap-3">
					<div>
						<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Sliders size={15} className="text-brand-400" aria-hidden="true" />
							<span>Bộ mô phỏng ngưỡng kép & tối ưu chi phí (Dual-Threshold Simulator)</span>
							<MetricInfoTooltip
								title="Ngưỡng kép (τ_review, τ_reject) & Lợi ích ròng"
								formula="Net Savings = Prevented $ − (Review × Chi phí duyệt) − (Hard FP $ × Trọng số chặn nhầm)"
								meaning="Chia giao dịch thành 3 vùng: Cho qua (< τ_review), Duyệt tay ([τ_review, τ_reject)), Chặn tự động (≥ τ_reject), so sánh song song Hybrid và Chỉ AI."
							/>
						</h3>
						<p className="text-xs text-slate-400 mt-0.5">
							So sánh song song tại cùng cặp ngưỡng (τ_review = {tauReview.toFixed(2)}, τ_reject = {tauReject.toFixed(2)})
						</p>
					</div>

					<div className="flex flex-wrap items-center gap-2">
						<div className="inline-flex rounded-lg bg-dark-950 p-0.5 border border-dark-800 text-[11px]">
							<button
								type="button"
								onClick={() => setSuggestMode('hybrid')}
								className={`px-2 py-1 rounded cursor-pointer ${suggestMode === 'hybrid' ? 'bg-brand-600 text-white' : 'text-slate-400'}`}
							>
								Gợi ý theo Hybrid
							</button>
							<button
								type="button"
								onClick={() => setSuggestMode('model_only')}
								className={`px-2 py-1 rounded cursor-pointer ${suggestMode === 'model_only' ? 'bg-brand-600 text-white' : 'text-slate-400'}`}
							>
								Gợi ý theo Chỉ AI
							</button>
						</div>
						<button type="button" onClick={() => applyRecommendation('capacity_top_k')} className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-[11px] text-slate-200 cursor-pointer">
							Sức tải duyệt
						</button>
						<button type="button" onClick={() => applyRecommendation('target_precision')} className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-[11px] text-slate-200 cursor-pointer">
							Precision mục tiêu
						</button>
						<button type="button" onClick={() => applyRecommendation('max_net_savings')} className="px-2.5 py-1 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/40 text-[11px] text-emerald-300 font-semibold cursor-pointer">
							Tối ưu Lợi ích ròng
						</button>
					</div>
				</div>

				{data.label_source === 'VERIFIED_ONLY' && (
					<div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
						<AlertTriangle size={14} className="text-amber-400 shrink-0" aria-hidden="true" />
						<span>
							Đang ở chế độ <strong>Chỉ hồ sơ đã xác minh</strong>: các giao dịch ALLOW không có nhãn nên kết quả mô phỏng khi hạ ngưỡng thấp có thể chịu thiên lệch chọn mẫu (selection bias).
						</span>
					</div>
				)}

				<div className="grid grid-cols-1 md:grid-cols-4 gap-4 bg-dark-950 border border-dark-800 rounded-xl p-4">
					<div>
						<div className="flex items-center justify-between text-xs text-slate-300 font-mono mb-1.5">
							<span>Ngưỡng đẩy duyệt (τ_review)</span>
							<span className="font-bold text-amber-300">{tauReview.toFixed(2)}</span>
						</div>
						<input
							type="range"
							aria-label="Ngưỡng đẩy duyệt tau_review"
							min={0.05}
							max={0.95}
							step={0.05}
							value={tauReview}
							onChange={(e) => {
								const next = Number(e.target.value);
								setTauReview(next);
								if (tauReject < next) {
									setTauReject(next);
								}
							}}
							className="w-full accent-amber-400 cursor-pointer"
						/>
					</div>
					<div>
						<div className="flex items-center justify-between text-xs text-slate-300 font-mono mb-1.5">
							<span>Ngưỡng chặn tự động (τ_reject)</span>
							<span className="font-bold text-rose-300">{tauReject.toFixed(2)}</span>
						</div>
						<input
							type="range"
							aria-label="Ngưỡng chặn tự động tau_reject"
							min={0.05}
							max={0.95}
							step={0.05}
							value={tauReject}
							onChange={(e) => setTauReject(Math.max(tauReview, Number(e.target.value)))}
							className="w-full accent-rose-400 cursor-pointer"
						/>
					</div>
					<div>
						<label className="block text-[11px] font-mono text-slate-400 mb-1">Chi phí duyệt/ca ($)</label>
						<input
							type="number"
							min={0}
							step={1}
							value={reviewCost}
							onChange={(e) => setReviewCost(Math.max(0, Number(e.target.value) || 0))}
							className="w-full bg-dark-900 border border-dark-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
					<div>
						<label className="block text-[11px] font-mono text-slate-400 mb-1">Trọng số chặn nhầm (%)</label>
						<input
							type="number"
							min={0}
							max={100}
							step={1}
							value={falseDeclinePct}
							onChange={(e) => setFalseDeclinePct(Math.max(0, Number(e.target.value) || 0))}
							className="w-full bg-dark-900 border border-dark-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
				</div>

				{/* So sánh song song Hybrid và Chỉ AI */}
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
					{[
						{ title: 'Kết hợp AI + Luật (Hybrid)', evalRes: hybridEval, accent: 'border-purple-500/30', badge: 'bg-purple-500/15 text-purple-300' },
						{ title: 'Chỉ AI (Model-only)', evalRes: modelOnlyEval, accent: 'border-cyan-500/30', badge: 'bg-cyan-500/15 text-cyan-300' },
					].map((panel) => (
						<div key={panel.title} className={`bg-dark-950 border ${panel.accent} rounded-xl p-4 space-y-3`}>
							<div className="flex items-center justify-between">
								<span className="text-xs font-bold uppercase tracking-wider text-slate-100">{panel.title}</span>
								<span className={`px-2 py-0.5 rounded text-[10px] font-mono ${panel.badge}`}>
									Precision {((panel.evalRes?.precision ?? 0) * 100).toFixed(1)}%
								</span>
							</div>
							<div className="grid grid-cols-2 gap-2.5 font-mono tabular-nums">
								<div className="bg-dark-900 border border-dark-800 rounded-lg p-2.5">
									<div className="text-[10px] text-slate-400 uppercase">Gian lận bắt được</div>
									<div className="text-base font-bold text-emerald-400 mt-0.5">
										{formatCurrency(panel.evalRes?.caught_fraud_amount)}
									</div>
									<div className="text-[10px] text-slate-500">
										VDR {((panel.evalRes?.vdr ?? 0) * 100).toFixed(1)}% ({panel.evalRes?.caught_fraud_count ?? 0} ca)
									</div>
								</div>
								<div className="bg-dark-900 border border-dark-800 rounded-lg p-2.5">
									<div className="text-[10px] text-slate-400 uppercase">Hàng đợi REVIEW</div>
									<div className="text-base font-bold text-amber-300 mt-0.5">
										{(panel.evalRes?.review_queue_count ?? 0).toLocaleString()} ca
									</div>
									<div className="text-[10px] text-slate-500">
										{panel.evalRes?.soft_review_fp_count ?? 0} ca xem xét nhầm
									</div>
								</div>
								<div className="bg-dark-900 border border-dark-800 rounded-lg p-2.5">
									<div className="text-[10px] text-slate-400 uppercase">Chặn nhầm REJECT</div>
									<div className="text-base font-bold text-rose-400 mt-0.5">
										{formatCurrency(panel.evalRes?.hard_false_decline_amount)}
									</div>
									<div className="text-[10px] text-slate-500">
										{panel.evalRes?.hard_false_decline_count ?? 0} / {panel.evalRes?.reject_count ?? 0} ca REJECT
									</div>
								</div>
								<div className="bg-dark-900 border border-dark-800 rounded-lg p-2.5">
									<div className="text-[10px] text-slate-400 uppercase">Lợi ích ròng (Net Savings)</div>
									<div className={`text-base font-bold mt-0.5 ${(panel.evalRes?.net_savings ?? 0) >= 0 ? 'text-cyan-300' : 'text-rose-400'}`}>
										{formatCurrency(panel.evalRes?.net_savings)}
									</div>
									<div className="text-[10px] text-slate-500">Sau chi phí duyệt & chặn nhầm</div>
								</div>
							</div>
						</div>
					))}
				</div>
			</div>

			{/* Hàng 5: So sánh Phiên bản Mô hình (7/12) + Phân rã PSI Drift (5/12) */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
				<div className="lg:col-span-7 bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2 mb-3">
						<Layers size={15} className="text-brand-400" aria-hidden="true" />
						<span>So sánh hiệu năng theo phiên bản mô hình</span>
					</h3>
					{modelComparison.length === 0 ? (
						<div className="py-8 text-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
							Chưa có phiên bản mô hình gắn với phiên quét trong phạm vi hiện tại.
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
								<thead>
									<tr className="border-b border-dark-800 text-[10px] text-slate-400 uppercase">
										<th className="py-2 px-2.5">Phiên bản mô hình</th>
										<th className="py-2 px-2.5 text-right">Tổng GD</th>
										<th className="py-2 px-2.5 text-right">Precision</th>
										<th className="py-2 px-2.5 text-right">VDR</th>
										<th className="py-2 px-2.5 text-right">KS</th>
										<th className="py-2 px-2.5 text-right">Brier</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800/60">
									{modelComparison.map((m) => (
										<tr key={m.model_version_id} className="hover:bg-dark-800/40">
											<td className="py-2 px-2.5 text-slate-100 font-semibold">{m.display_label}</td>
											<td className="py-2 px-2.5 text-right text-slate-300">{m.tx_count.toLocaleString()}</td>
											<td className="py-2 px-2.5 text-right text-cyan-300">
												{m.verified_precision != null ? `${(m.verified_precision * 100).toFixed(1)}%` : '—'}
											</td>
											<td className="py-2 px-2.5 text-right text-emerald-400">
												{m.vdr != null ? `${(m.vdr * 100).toFixed(1)}%` : '—'}
											</td>
											<td className="py-2 px-2.5 text-right text-slate-200">
												{m.ks_statistic != null ? m.ks_statistic.toFixed(3) : '—'}
											</td>
											<td className="py-2 px-2.5 text-right text-slate-300">
												{m.brier_score != null ? m.brier_score.toFixed(4) : '—'}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</div>

				<div className="lg:col-span-5 bg-dark-900 border border-dark-700/80 rounded-xl p-5">
					<h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2 mb-1">
						<Activity size={15} className="text-amber-400" aria-hidden="true" />
						<span>Phân rã dịch chuyển điểm (PSI Bin Breakdown)</span>
					</h3>
					<p className="text-xs text-slate-400 mb-3">
						So sánh tỷ trọng điểm Baseline ({data.score_drift?.baseline_count ?? 0}) vs Hiện tại ({data.score_drift?.current_count ?? 0})
					</p>
					{driftBins.length === 0 ? (
						<div className="h-52 flex items-center justify-center text-xs text-slate-500 bg-dark-950 rounded-lg border border-dark-800">
							Cần tối thiểu 20 giao dịch (mỗi giai đoạn ≥ 10) để tính PSI.
						</div>
					) : (
						<div className="h-52 w-full">
							<ResponsiveContainer width="100%" height="100%">
								<ComposedChart data={driftBins} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
									<CartesianGrid strokeDasharray="3 3" stroke={chartTokens.gridSubtleStroke} />
									<XAxis dataKey="bin" stroke={chartTokens.axisStroke} tick={{ fontSize: 10 }} />
									<YAxis stroke={chartTokens.axisStroke} tick={{ fontSize: 10 }} unit="%" />
									<Tooltip
										contentStyle={{
											backgroundColor: chartTokens.tooltipBg,
											borderColor: chartTokens.tooltipBorder,
											color: chartTokens.tooltipText,
											borderRadius: '0.5rem',
											fontSize: '12px',
										}}
									/>
									<Legend wrapperStyle={{ fontSize: '11px' }} />
									<Bar dataKey="baseline_100" name="Giai đoạn chuẩn (%)" fill="#64748B" radius={[3, 3, 0, 0]} />
									<Bar dataKey="current_100" name="Giai đoạn hiện tại (%)" fill="#F59E0B" radius={[3, 3, 0, 0]} />
								</ComposedChart>
							</ResponsiveContainer>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};
