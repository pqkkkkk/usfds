import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
	ArrowLeft,
	CheckCircle2,
	XCircle,
	Rocket,
	Sliders,
	Activity,
	BarChart3,
	ShieldCheck,
	AlertTriangle,
	RotateCcw,
	Loader2,
	FileCode2,
	Clock,
	Star,
} from 'lucide-react';
import { trainingApi } from '../../../api/trainingApi';
import type {
	ModelResponse,
	ModelVersionResponse,
	ThresholdGridPoint,
	TrainingRunResponse,
} from '../../../types/model';
import { ActivateModelModal } from './ActivateModelModal';

export const TrainingRunDetailView: React.FC = () => {
	const { runId } = useParams<{ runId: string }>();
	const navigate = useNavigate();

	const [run, setRun] = useState<TrainingRunResponse | null>(null);
	const [model, setModel] = useState<ModelResponse | null>(null);
	const [version, setVersion] = useState<ModelVersionResponse | null>(null);
	const [isLoading, setIsLoading] = useState<boolean>(true);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);

	// Interactive Threshold Simulator state
	const [selectedThreshold, setSelectedThreshold] = useState<number>(0.5);
	const [cmDisplayMode, setCmDisplayMode] = useState<'count' | 'percent'>('count');
	const [isActivateModalOpen, setIsActivateModalOpen] = useState<boolean>(false);

	const loadRunDetails = useCallback(async () => {
		if (!runId) {
			return;
		}
		setIsLoading(true);
		setErrorMsg(null);
		try {
			const runRes = await trainingApi.getTrainingRun(runId);
			if (!runRes.success || !runRes.data) {
				setErrorMsg(runRes.error || 'Không tìm thấy bản ghi TrainingRun.');
				return;
			}
			const runData = runRes.data;
			setRun(runData);

			const initThreshold =
				runData.recommended_threshold ??
				runData.custom_metrics?.recommended_thresholds?.best_f1?.threshold ??
				runData.default_threshold ??
				0.5;
			setSelectedThreshold(Number(initThreshold.toFixed(4)));

			const promises: Promise<void>[] = [];
			if (runData.model_id) {
				promises.push(
					trainingApi.getModel(runData.model_id).then((mRes) => {
						if (mRes.success && mRes.data) {
							setModel(mRes.data);
						}
					})
				);
			}
			if (runData.version_id) {
				promises.push(
					trainingApi.getModelVersion(runData.version_id).then((vRes) => {
						if (vRes.success && vRes.data) {
							setVersion(vRes.data);
						}
					})
				);
			}
			await Promise.all(promises);
		} finally {
			setIsLoading(false);
		}
	}, [runId]);

	useEffect(() => {
		loadRunDetails();
	}, [loadRunDetails]);

	const customMetrics = run?.custom_metrics || {};
	const thresholdGrid: ThresholdGridPoint[] = customMetrics.threshold_tuning_grid || [];
	const recommendedThresholds = customMetrics.recommended_thresholds || {};

	// Find closest grid point for current slider value
	const activePoint: ThresholdGridPoint = useMemo(() => {
		if (thresholdGrid.length > 0) {
			let closest = thresholdGrid[0];
			let minDiff = Math.abs(closest.threshold - selectedThreshold);
			for (const pt of thresholdGrid) {
				const diff = Math.abs(pt.threshold - selectedThreshold);
				if (diff < minDiff) {
					minDiff = diff;
					closest = pt;
				}
			}
			return closest;
		}
		const cm = customMetrics.confusion_matrix || { tp: 0, fp: 0, tn: 0, fn: 0 };
		return {
			threshold: selectedThreshold,
			precision: run?.precision_score ?? customMetrics.precision ?? 0,
			recall: run?.recall_score ?? customMetrics.recall ?? 0,
			f1_score: run?.f1_score ?? customMetrics.f1_score ?? 0,
			f2_score: customMetrics.f2_score ?? 0,
			accuracy: run?.accuracy ?? customMetrics.accuracy ?? 0,
			tp: cm.tp,
			fp: cm.fp,
			tn: cm.tn,
			fn: cm.fn,
		};
	}, [thresholdGrid, selectedThreshold, customMetrics, run]);

	const fprAtThreshold = useMemo(() => {
		const totalLegit = activePoint.fp + activePoint.tn;
		return totalLegit > 0 ? activePoint.fp / totalLegit : 0;
	}, [activePoint]);

	const renderPolylinePoints = (xArr: number[], yArr: number[]): string => {
		const len = Math.min(xArr.length, yArr.length);
		if (len === 0) {
			return '';
		}
		const pts: string[] = [];
		for (let i = 0; i < len; i++) {
			const x = Math.max(0, Math.min(1, xArr[i])) * 240 + 30;
			const y = (1 - Math.max(0, Math.min(1, yArr[i]))) * 180 + 15;
			pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
		}
		return pts.join(' ');
	};

	if (isLoading) {
		return (
			<div className="flex-1 flex items-center justify-center bg-dark-950 text-xs text-slate-400 gap-2.5">
				<Loader2 className="w-4 h-4 animate-spin text-brand-400" />
				<span>Đang tải kết quả huấn luyện mô hình...</span>
			</div>
		);
	}

	if (errorMsg || !run) {
		return (
			<div className="flex-1 p-6 bg-dark-950">
				<div className="max-w-xl mx-auto p-6 rounded-xl bg-dark-900 border border-rose-500/30 text-center space-y-3">
					<XCircle className="w-8 h-8 text-rose-400 mx-auto" />
					<h2 className="text-sm font-bold text-slate-100">Không thể tải kết quả huấn luyện</h2>
					<p className="text-xs text-rose-300">{errorMsg}</p>
					<button
						type="button"
						onClick={() => navigate('/models')}
						className="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-xs text-slate-200"
					>
						Quay lại Model Hub
					</button>
				</div>
			</div>
		);
	}

	const isFailed = run.status === 'FAILED';
	const rocCurve = customMetrics.roc_curve;
	const prCurve = customMetrics.pr_curve;
	const scoreDist = customMetrics.score_distribution;

	const actualLegitTotal = activePoint.tn + activePoint.fp;
	const actualFraudTotal = activePoint.fn + activePoint.tp;

	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden bg-dark-950">
			{/* Top Header */}
			<div className="px-6 py-4 border-b border-dark-800 bg-dark-900/60 flex flex-wrap items-center justify-between gap-4">
				<div className="flex items-center gap-3">
					<button
						type="button"
						onClick={() => navigate('/models')}
						className="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-300 transition"
						title="Quay lại Model Hub"
					>
						<ArrowLeft className="w-4 h-4" />
					</button>
					<div>
						<div className="flex flex-wrap items-center gap-2">
							<h1 className="text-base font-bold text-slate-100">{run.run_name}</h1>
							{run.status === 'COMPLETED' ? (
								<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
									<CheckCircle2 className="w-3 h-3" />
									COMPLETED
								</span>
							) : (
								<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
									<XCircle className="w-3 h-3" />
									{run.status}
								</span>
							)}
							{version && (
								<span
									className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
										version.status === 'APPROVED'
											? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
											: 'bg-brand-500/15 text-brand-400 border border-brand-500/30'
									}`}
								>
									v{version.semver} · {version.status}
								</span>
							)}
						</div>
						<div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-400 mt-1 font-mono">
							<span>
								Model: <strong className="text-slate-200">{model?.display_name || model?.model_name || run.model_id}</strong>
							</span>
							{typeof run.duration_seconds === 'number' && (
								<span className="flex items-center gap-1">
									<Clock className="w-3 h-3" />
									Duration: {run.duration_seconds}s
								</span>
							)}
							{run.dataset_artifact_id && (
								<span>Artifact: {run.dataset_artifact_id.slice(0, 12)}...</span>
							)}
						</div>
					</div>
				</div>

				{/* Header Actions */}
				<div className="flex items-center gap-2.5">
					<button
						type="button"
						onClick={() =>
							navigate(
								`/models/train?modelId=${run.model_id || ''}&artifactId=${run.dataset_artifact_id || ''}`
							)
						}
						className="px-3.5 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 border border-dark-700 text-xs font-semibold text-slate-200 transition flex items-center gap-1.5"
					>
						<RotateCcw className="w-3.5 h-3.5" />
						<span>Re-train / Clone</span>
					</button>

					{version && !isFailed && (
						<button
							type="button"
							onClick={() => setIsActivateModalOpen(true)}
							className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-glow-green transition flex items-center gap-2"
						>
							<Rocket className="w-4 h-4" />
							<span>
								{version.status === 'APPROVED'
									? `Update Active Threshold (${activePoint.threshold.toFixed(2)})`
									: `Activate Model @ ${activePoint.threshold.toFixed(2)}`}
							</span>
						</button>
					)}
				</div>
			</div>

			{/* Main Content */}
			<div className="flex-1 overflow-y-auto p-6 space-y-6">
				{isFailed ? (
					/* EXCEPTION FLOW 2a: FAILED TRAINING RUN */
					<div className="bg-dark-900 border border-rose-500/30 rounded-xl p-6 space-y-4">
						<div className="flex items-center gap-2.5 text-rose-400">
							<AlertTriangle className="w-5 h-5" />
							<h2 className="text-sm font-bold">
								Execution Error Log — Quá trình huấn luyện thất bại
							</h2>
						</div>
						<pre className="p-4 rounded-xl bg-dark-950 border border-dark-800 text-xs font-mono text-rose-300 whitespace-pre-wrap overflow-x-auto">
							{run.error_message || 'Không có nhật ký lỗi chi tiết.'}
						</pre>
						<div className="flex justify-end">
							<button
								type="button"
								onClick={() =>
									navigate(
										`/models/train?modelId=${run.model_id || ''}&artifactId=${run.dataset_artifact_id || ''}`
									)
								}
								className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold transition flex items-center gap-2"
							>
								<RotateCcw className="w-3.5 h-3.5" />
								<span>Retry in Training Wizard</span>
							</button>
						</div>
					</div>
				) : (
					<>
						{/* 1. Core Performance KPIs */}
						<div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
							<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
								<div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
									PR-AUC (Avg Precision)
								</div>
								<div className="text-lg font-bold font-mono text-amber-400 mt-1">
									{typeof customMetrics.pr_auc === 'number'
										? customMetrics.pr_auc.toFixed(4)
										: '—'}
								</div>
							</div>

							<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
								<div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
									ROC-AUC
								</div>
								<div className="text-lg font-bold font-mono text-brand-400 mt-1">
									{typeof customMetrics.roc_auc === 'number'
										? customMetrics.roc_auc.toFixed(4)
										: '—'}
								</div>
							</div>

							<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
								<div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
									F1-Score (Default)
								</div>
								<div className="text-lg font-bold font-mono text-emerald-400 mt-1">
									{typeof run.f1_score === 'number' ? run.f1_score.toFixed(4) : '—'}
								</div>
							</div>

							<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
								<div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
									F2-Score (Recall-Weighted)
								</div>
								<div className="text-lg font-bold font-mono text-purple-400 mt-1">
									{typeof customMetrics.f2_score === 'number'
										? customMetrics.f2_score.toFixed(4)
										: '—'}
								</div>
							</div>

							<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
								<div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
									Precision (Default)
								</div>
								<div className="text-lg font-bold font-mono text-slate-100 mt-1">
									{typeof run.precision_score === 'number'
										? run.precision_score.toFixed(4)
										: '—'}
								</div>
							</div>

							<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
								<div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
									Recall (Default)
								</div>
								<div className="text-lg font-bold font-mono text-slate-100 mt-1">
									{typeof run.recall_score === 'number'
										? run.recall_score.toFixed(4)
										: '—'}
								</div>
							</div>
						</div>

						{/* 2. Interactive Threshold Simulator & 2x2 Confusion Matrix */}
						<div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
							{/* Left: Threshold Slider & Presets (6 cols) */}
							<div className="lg:col-span-6 bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-4">
								<div className="flex items-center justify-between border-b border-dark-800 pb-3">
									<div className="flex items-center gap-2">
										<Sliders className="w-4 h-4 text-amber-400" />
										<h2 className="text-xs font-bold uppercase tracking-wider text-slate-100">
											Decision Threshold Simulator
										</h2>
									</div>
									<span className="px-2.5 py-0.5 rounded-lg font-mono text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
										Threshold = {activePoint.threshold.toFixed(4)}
									</span>
								</div>

								{/* Slider */}
								<div className="space-y-2">
									<input
										type="range"
										min="0.01"
										max="0.99"
										step="0.01"
										value={selectedThreshold}
										onChange={(e) => setSelectedThreshold(parseFloat(e.target.value))}
										aria-label="Decision Threshold Slider"
										className="w-full accent-amber-400 cursor-pointer"
									/>
									<div className="flex justify-between text-[10px] font-mono text-slate-500">
										<span>0.01 (Max Recall)</span>
										<span>0.50 (Default)</span>
										<span>0.99 (Max Precision)</span>
									</div>
								</div>

								{/* Recommended Threshold Preset Pills */}
								<div className="space-y-1.5">
									<div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
										<Star className="w-3 h-3 text-amber-400" />
										<span>Recommended Operational Presets:</span>
									</div>
									<div className="flex flex-wrap gap-2">
										{recommendedThresholds.best_f1 && (
											<button
												type="button"
												onClick={() =>
													setSelectedThreshold(recommendedThresholds.best_f1!.threshold)
												}
												className="px-2.5 py-1 rounded-lg bg-dark-950 hover:bg-dark-800 border border-dark-700 text-[11px] font-mono text-slate-200 transition"
											>
												★ Best F1 ({recommendedThresholds.best_f1.threshold.toFixed(2)})
											</button>
										)}
										{recommendedThresholds.best_f2 && (
											<button
												type="button"
												onClick={() =>
													setSelectedThreshold(recommendedThresholds.best_f2!.threshold)
												}
												className="px-2.5 py-1 rounded-lg bg-dark-950 hover:bg-dark-800 border border-dark-700 text-[11px] font-mono text-slate-200 transition"
											>
												Best F2 ({recommendedThresholds.best_f2.threshold.toFixed(2)})
											</button>
										)}
										{recommendedThresholds.youden_j && (
											<button
												type="button"
												onClick={() =>
													setSelectedThreshold(recommendedThresholds.youden_j!.threshold)
												}
												className="px-2.5 py-1 rounded-lg bg-dark-950 hover:bg-dark-800 border border-dark-700 text-[11px] font-mono text-slate-200 transition"
											>
												Youden J ({recommendedThresholds.youden_j.threshold.toFixed(2)})
											</button>
										)}
										{recommendedThresholds.high_recall_90 && (
											<button
												type="button"
												onClick={() =>
													setSelectedThreshold(recommendedThresholds.high_recall_90!.threshold)
												}
												className="px-2.5 py-1 rounded-lg bg-dark-950 hover:bg-dark-800 border border-dark-700 text-[11px] font-mono text-slate-200 transition"
											>
												Recall ≥ 90% ({recommendedThresholds.high_recall_90.threshold.toFixed(2)})
											</button>
										)}
									</div>
								</div>

								{/* Dynamic Metrics at Selected Threshold */}
								<div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 pt-2">
									<div className="p-2.5 rounded-lg bg-dark-950 border border-dark-800 text-center">
										<div className="text-[10px] text-slate-400">Precision</div>
										<div className="text-xs font-bold font-mono text-slate-100 mt-0.5">
											{activePoint.precision.toFixed(4)}
										</div>
									</div>
									<div className="p-2.5 rounded-lg bg-dark-950 border border-dark-800 text-center">
										<div className="text-[10px] text-slate-400">Recall</div>
										<div className="text-xs font-bold font-mono text-emerald-400 mt-0.5">
											{activePoint.recall.toFixed(4)}
										</div>
									</div>
									<div className="p-2.5 rounded-lg bg-dark-950 border border-dark-800 text-center">
										<div className="text-[10px] text-slate-400">F1-Score</div>
										<div className="text-xs font-bold font-mono text-brand-400 mt-0.5">
											{activePoint.f1_score.toFixed(4)}
										</div>
									</div>
									<div className="p-2.5 rounded-lg bg-dark-950 border border-dark-800 text-center">
										<div className="text-[10px] text-slate-400">F2-Score</div>
										<div className="text-xs font-bold font-mono text-purple-400 mt-0.5">
											{activePoint.f2_score.toFixed(4)}
										</div>
									</div>
									<div className="p-2.5 rounded-lg bg-dark-950 border border-dark-800 text-center">
										<div className="text-[10px] text-slate-400">FPR</div>
										<div className="text-xs font-bold font-mono text-rose-400 mt-0.5">
											{(fprAtThreshold * 100).toFixed(2)}%
										</div>
									</div>
								</div>
							</div>

							{/* Right: Confusion Matrix @ Threshold (6 cols) */}
							<div className="lg:col-span-6 bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-4">
								<div className="flex items-center justify-between border-b border-dark-800 pb-3">
									<h2 className="text-xs font-bold uppercase tracking-wider text-slate-100">
										Confusion Matrix @ Threshold {activePoint.threshold.toFixed(2)}
									</h2>
									<div className="flex items-center gap-1 bg-dark-950 p-1 rounded-lg border border-dark-800 text-[10px] font-mono">
										<button
											type="button"
											onClick={() => setCmDisplayMode('count')}
											className={`px-2 py-0.5 rounded ${
												cmDisplayMode === 'count'
													? 'bg-brand-500 text-white font-bold'
													: 'text-slate-400'
											}`}
										>
											Count
										</button>
										<button
											type="button"
											onClick={() => setCmDisplayMode('percent')}
											className={`px-2 py-0.5 rounded ${
												cmDisplayMode === 'percent'
													? 'bg-brand-500 text-white font-bold'
													: 'text-slate-400'
											}`}
										>
											Row %
										</button>
									</div>
								</div>

								<div className="grid grid-cols-2 gap-3">
									{/* TN */}
									<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 flex flex-col justify-between">
										<div className="flex items-center justify-between text-[11px] text-slate-400">
											<span>Actual Legit → Pred Legit</span>
											<span className="font-mono font-bold text-slate-300">TN</span>
										</div>
										<div className="text-xl font-bold font-mono text-slate-100 mt-2">
											{cmDisplayMode === 'count'
												? activePoint.tn.toLocaleString()
												: actualLegitTotal > 0
												? `${((activePoint.tn / actualLegitTotal) * 100).toFixed(1)}%`
												: '0.0%'}
										</div>
										<div className="text-[10px] text-slate-500 mt-1">
											Giao dịch hợp lệ phân loại đúng
										</div>
									</div>

									{/* FP */}
									<div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex flex-col justify-between">
										<div className="flex items-center justify-between text-[11px] text-amber-300">
											<span>Actual Legit → Pred Fraud</span>
											<span className="font-mono font-bold">FP (False Alarm)</span>
										</div>
										<div className="text-xl font-bold font-mono text-amber-400 mt-2">
											{cmDisplayMode === 'count'
												? activePoint.fp.toLocaleString()
												: actualLegitTotal > 0
												? `${((activePoint.fp / actualLegitTotal) * 100).toFixed(1)}%`
												: '0.0%'}
										</div>
										<div className="text-[10px] text-amber-300/80 mt-1">
											Báo động giả (Cần rà soát thủ công)
										</div>
									</div>

									{/* FN */}
									<div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex flex-col justify-between">
										<div className="flex items-center justify-between text-[11px] text-rose-300">
											<span>Actual Fraud → Pred Legit</span>
											<span className="font-mono font-bold">FN (Missed Fraud)</span>
										</div>
										<div className="text-xl font-bold font-mono text-rose-400 mt-2">
											{cmDisplayMode === 'count'
												? activePoint.fn.toLocaleString()
												: actualFraudTotal > 0
												? `${((activePoint.fn / actualFraudTotal) * 100).toFixed(1)}%`
												: '0.0%'}
										</div>
										<div className="text-[10px] text-rose-300/80 mt-1">
											Bỏ sót gian lận (Rủi ro thất thoát)
										</div>
									</div>

									{/* TP */}
									<div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex flex-col justify-between">
										<div className="flex items-center justify-between text-[11px] text-emerald-300">
											<span>Actual Fraud → Pred Fraud</span>
											<span className="font-mono font-bold">TP (Caught Fraud)</span>
										</div>
										<div className="text-xl font-bold font-mono text-emerald-400 mt-2">
											{cmDisplayMode === 'count'
												? activePoint.tp.toLocaleString()
												: actualFraudTotal > 0
												? `${((activePoint.tp / actualFraudTotal) * 100).toFixed(1)}%`
												: '0.0%'}
										</div>
										<div className="text-[10px] text-emerald-300/80 mt-1">
											Bắt đúng giao dịch gian lận
										</div>
									</div>
								</div>
							</div>
						</div>

						{/* 3. Visual Curves: ROC Curve, PR Curve, Score Distribution */}
						<div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
							{/* ROC Curve */}
							<div className="bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-3">
								<div className="flex items-center justify-between">
									<span className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
										<Activity className="w-4 h-4 text-brand-400" />
										ROC Curve
									</span>
									<span className="text-xs font-mono text-brand-400 font-bold">
										AUC = {typeof customMetrics.roc_auc === 'number' ? customMetrics.roc_auc.toFixed(4) : '—'}
									</span>
								</div>
								{rocCurve && rocCurve.fpr?.length ? (
									<svg viewBox="0 0 290 220" className="w-full h-48 bg-dark-950 rounded-lg border border-dark-800">
										{/* Axes */}
										<line x1="30" y1="15" x2="30" y2="195" stroke="#334155" strokeWidth="1" />
										<line x1="30" y1="195" x2="270" y2="195" stroke="#334155" strokeWidth="1" />
										{/* Diagonal Baseline */}
										<line
											x1="30"
											y1="195"
											x2="270"
											y2="15"
											stroke="#475569"
											strokeDasharray="4 4"
											strokeWidth="1"
										/>
										{/* ROC Polyline */}
										<polyline
											fill="none"
											stroke="#3B82F6"
											strokeWidth="2.2"
											points={renderPolylinePoints(rocCurve.fpr, rocCurve.tpr)}
										/>
										<text x="150" y="213" textAnchor="middle" fill="#94A3B8" fontSize="9">
											False Positive Rate (FPR)
										</text>
										<text
											x="12"
											y="105"
											textAnchor="middle"
											fill="#94A3B8"
											fontSize="9"
											transform="rotate(-90 12 105)"
										>
											True Positive Rate (TPR)
										</text>
									</svg>
								) : (
									<div className="h-48 flex items-center justify-center bg-dark-950 rounded-lg border border-dark-800 text-xs text-slate-500">
										Không có dữ liệu ROC Curve
									</div>
								)}
							</div>

							{/* Precision-Recall Curve */}
							<div className="bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-3">
								<div className="flex items-center justify-between">
									<span className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
										<Activity className="w-4 h-4 text-emerald-400" />
										Precision-Recall Curve
									</span>
									<span className="text-xs font-mono text-emerald-400 font-bold">
										PR-AUC = {typeof customMetrics.pr_auc === 'number' ? customMetrics.pr_auc.toFixed(4) : '—'}
									</span>
								</div>
								{prCurve && prCurve.recall?.length ? (
									<svg viewBox="0 0 290 220" className="w-full h-48 bg-dark-950 rounded-lg border border-dark-800">
										<line x1="30" y1="15" x2="30" y2="195" stroke="#334155" strokeWidth="1" />
										<line x1="30" y1="195" x2="270" y2="195" stroke="#334155" strokeWidth="1" />
										<polyline
											fill="none"
											stroke="#10B981"
											strokeWidth="2.2"
											points={renderPolylinePoints(prCurve.recall, prCurve.precision)}
										/>
										<text x="150" y="213" textAnchor="middle" fill="#94A3B8" fontSize="9">
											Recall
										</text>
										<text
											x="12"
											y="105"
											textAnchor="middle"
											fill="#94A3B8"
											fontSize="9"
											transform="rotate(-90 12 105)"
										>
											Precision
										</text>
									</svg>
								) : (
									<div className="h-48 flex items-center justify-center bg-dark-950 rounded-lg border border-dark-800 text-xs text-slate-500">
										Không có dữ liệu PR Curve
									</div>
								)}
							</div>

							{/* Score Distribution Histogram */}
							<div className="bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-3">
								<div className="flex items-center justify-between">
									<span className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
										<BarChart3 className="w-4 h-4 text-amber-400" />
										Score Distribution
									</span>
									<span className="text-[10px] font-mono text-slate-400">
										Blue: Legit · Red: Fraud
									</span>
								</div>
								{scoreDist && scoreDist.legit_counts?.length ? (
									<svg viewBox="0 0 290 220" className="w-full h-48 bg-dark-950 rounded-lg border border-dark-800">
										<line x1="30" y1="15" x2="30" y2="195" stroke="#334155" strokeWidth="1" />
										<line x1="30" y1="195" x2="270" y2="195" stroke="#334155" strokeWidth="1" />
										{(() => {
											const bins = scoreDist.legit_counts.length;
											const maxCount = Math.max(
												1,
												...scoreDist.legit_counts,
												...scoreDist.fraud_counts
											);
											const barW = 240 / bins;
											return scoreDist.legit_counts.map((lCount, idx) => {
												const fCount = scoreDist.fraud_counts[idx] || 0;
												const lH = (lCount / maxCount) * 170;
												const fH = (fCount / maxCount) * 170;
												const x = 30 + idx * barW;
												return (
													<g key={idx}>
														<rect
															x={x + 0.5}
															y={195 - lH}
															width={Math.max(1, barW / 2 - 0.5)}
															height={lH}
															fill="#3B82F6"
															opacity="0.75"
														/>
														<rect
															x={x + barW / 2}
															y={195 - fH}
															width={Math.max(1, barW / 2 - 0.5)}
															height={fH}
															fill="#EF4444"
															opacity="0.85"
														/>
													</g>
												);
											});
										})()}
										{/* Active Threshold Vertical Line */}
										<line
											x1={30 + activePoint.threshold * 240}
											y1="15"
											x2={30 + activePoint.threshold * 240}
											y2="195"
											stroke="#FBBF24"
											strokeWidth="2"
											strokeDasharray="3 3"
										/>
										<text x="150" y="213" textAnchor="middle" fill="#94A3B8" fontSize="9">
											Predicted Fraud Probability (Threshold = {activePoint.threshold.toFixed(2)})
										</text>
									</svg>
								) : (
									<div className="h-48 flex items-center justify-center bg-dark-950 rounded-lg border border-dark-800 text-xs text-slate-500">
										Không có dữ liệu Score Distribution
									</div>
								)}
							</div>
						</div>

						{/* 4. Configuration & Lineage Metadata */}
						<div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
							<div className="bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-3">
								<div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200 border-b border-dark-800 pb-2.5">
									<ShieldCheck className="w-4 h-4 text-emerald-400" />
									<span>Model Version & Artifact Integrity</span>
								</div>
								<div className="space-y-2 text-xs">
									<div className="flex justify-between">
										<span className="text-slate-400">Version ID:</span>
										<span className="font-mono text-slate-200">{version?.version_id || '—'}</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Artifact URI:</span>
										<span className="font-mono text-slate-200 truncate max-w-xs" title={version?.artifact_uri}>
											{version?.artifact_uri || '—'}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">SHA-256 Checksum:</span>
										<span className="font-mono text-emerald-400 text-[11px]">
											{version?.checksum_sha256
												? `${version.checksum_sha256.slice(0, 16)}...${version.checksum_sha256.slice(-8)}`
												: '—'}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Saved Decision Threshold:</span>
										<span className="font-mono font-bold text-amber-400">
											{version ? Number(version.decision_threshold).toFixed(4) : '—'}
										</span>
									</div>
								</div>
							</div>

							<div className="bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-3">
								<div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200 border-b border-dark-800 pb-2.5">
									<FileCode2 className="w-4 h-4 text-brand-400" />
									<span>Hyperparameters Configuration</span>
								</div>
								<pre className="p-3 rounded-xl bg-dark-950 border border-dark-800 text-[11px] font-mono text-slate-200 overflow-x-auto max-h-36">
									{JSON.stringify(run.hyperparameters || {}, null, 2)}
								</pre>
							</div>
						</div>
					</>
				)}
			</div>

			{/* Activate Model Modal (SUC-10) */}
			<ActivateModelModal
				isOpen={isActivateModalOpen}
				version={version}
				model={model}
				initialThreshold={activePoint.threshold}
				onClose={() => setIsActivateModalOpen(false)}
				onSuccess={(updatedVer) => {
					setVersion(updatedVer);
				}}
			/>
		</div>
	);
};
