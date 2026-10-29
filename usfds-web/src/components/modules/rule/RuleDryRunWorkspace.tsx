import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
	Play,
	RotateCcw,
	CheckCircle2,
	FileCode2,
	Database,
	X,
	SlidersHorizontal,
	AlertTriangle,
	Terminal,
	ShieldAlert,
} from 'lucide-react';
import { datasetApi } from '../../../api/datasetApi';
import { ruleApi } from '../../../api/ruleApi';
import { useProject } from '../../../hooks/useProjects';
import type { DatasetArtifactResponse, DatasetResponse } from '../../../types/dataset';
import type {
	RuleResponse,
	RuleGroup,
	RuleAction,
	RuleBacktestResultResponse,
	RuleBacktestSampleHit,
	RuleExecutionResultResponse,
} from '../../../types/rule';
import { createStitchSampleRuleGroup, groupToJsonLogic } from '../../../utils/jsonLogicParser';

interface RuleDryRunWorkspaceProps {
	ruleCode: string;
	ruleName: string;
	ruleAction: RuleAction;
	conditionGroup?: RuleGroup;
	currentRule?: RuleResponse | null;
	errorMessage?: string | null;
}

interface ArtifactOption {
	dataset: DatasetResponse;
	artifact: DatasetArtifactResponse;
	label: string;
}

const FALLBACK_PROJECT_ID = '11111111-1111-1111-1111-111111111111';

export const RuleDryRunWorkspace: React.FC<RuleDryRunWorkspaceProps> = ({
	ruleCode,
	ruleName,
	ruleAction,
	conditionGroup,
	currentRule,
	errorMessage,
}) => {
	const { currentProject, currentProjectId } = useProject();
	const effectiveProjectId = currentProjectId || FALLBACK_PROJECT_ID;

	const [activeMode, setActiveMode] = useState<'dataset-backtest' | 'single-tx'>('dataset-backtest');

	// Dataset & Artifact catalog state
	const [artifactOptions, setArtifactOptions] = useState<ArtifactOption[]>([]);
	const [selectedArtifactId, setSelectedArtifactId] = useState<string>('');
	const [isLoadingArtifacts, setIsLoadingArtifacts] = useState<boolean>(false);

	// Backtest simulation state
	const [isRunning, setIsRunning] = useState<boolean>(false);
	const [backtestError, setBacktestError] = useState<string | null>(null);
	const [backtestResult, setBacktestResult] = useState<RuleBacktestResultResponse | null>(null);
	const [filterTab, setFilterTab] = useState<'ALL' | 'TP' | 'FP'>('ALL');
	const [inspectingTx, setInspectingTx] = useState<RuleBacktestSampleHit | null>(null);

	// Single-Transaction Evaluator state
	const defaultTxPayload = useMemo(() => {
		const cols = currentProject?.raw_schema?.columns;
		const sampleRaw: Record<string, any> = {};
		if (cols && Object.keys(cols).length > 0) {
			for (const [colName, spec] of Object.entries(cols)) {
				if (spec.logical_type === 'NUMERIC') {
					sampleRaw[colName] = colName.toLowerCase().includes('amount') ? 2500 : 1;
				} else if (spec.logical_type === 'BOOLEAN') {
					sampleRaw[colName] = true;
				} else {
					sampleRaw[colName] = 'SAMPLE';
				}
			}
		} else {
			sampleRaw.amount = 2500;
			sampleRaw.is_new_device_24h = true;
			sampleRaw.velocity_count_1h = 6;
			sampleRaw.merchant_risk_category = 'crypto';
		}
		return JSON.stringify(
			{
				transaction_id: 'TX-TEST-001',
				raw_features: sampleRaw,
				enriched_features: {},
			},
			null,
			2
		);
	}, [currentProject?.raw_schema]);

	const [txJsonInput, setTxJsonInput] = useState<string>(defaultTxPayload);
	const [isEvaluatingTx, setIsEvaluatingTx] = useState<boolean>(false);
	const [singleEvalResult, setSingleEvalResult] = useState<RuleExecutionResultResponse | null>(null);
	const [batchEvalResults, setBatchEvalResults] = useState<RuleExecutionResultResponse[] | null>(null);
	const [singleEvalError, setSingleEvalError] = useState<string | null>(null);

	useEffect(() => {
		setTxJsonInput(defaultTxPayload);
	}, [defaultTxPayload]);

	const loadProjectArtifacts = useCallback(async () => {
		setIsLoadingArtifacts(true);
		try {
			const dsRes = await datasetApi.listDatasets(effectiveProjectId);
			const dsList = dsRes.success && Array.isArray(dsRes.data) ? dsRes.data : [];
			const options: ArtifactOption[] = [];

			const details = await Promise.all(
				dsList.map(async (ds) => {
					const detailRes = await datasetApi.getDatasetDetail(ds.dataset_id);
					return [
						ds,
						detailRes.success && detailRes.data ? detailRes.data.artifacts : [],
					] as const;
				})
			);

			for (const [ds, arts] of details) {
				for (const art of arts) {
					const rowsLabel = art.row_count ? `${art.row_count.toLocaleString()} rows` : 'rows N/A';
					options.push({
						dataset: ds,
						artifact: art,
						label: `${ds.display_name || ds.dataset_name} / ${art.pipeline_stage} (${rowsLabel})`,
					});
				}
			}

			setArtifactOptions(options);
			if (options.length > 0 && !selectedArtifactId) {
				// Prefer FEATURE_ENGINEERED or MAPPED or RAW artifact
				const preferred =
					options.find((o) => o.artifact.pipeline_stage === 'FEATURE_ENGINEERED') ||
					options.find((o) => o.artifact.pipeline_stage === 'MAPPED') ||
					options[0];
				setSelectedArtifactId(preferred.artifact.artifact_id);
			}
		} finally {
			setIsLoadingArtifacts(false);
		}
	}, [effectiveProjectId, selectedArtifactId]);

	useEffect(() => {
		loadProjectArtifacts();
	}, [loadProjectArtifacts]);

	const handleRunSimulation = async () => {
		if (!selectedArtifactId) {
			setBacktestError('Vui lòng chọn một Dataset Artifact trong dự án để chạy kiểm thử Backtest.');
			return;
		}
		setIsRunning(true);
		setBacktestError(null);
		try {
			const compiledCondition = groupToJsonLogic(
				conditionGroup || createStitchSampleRuleGroup()
			);
			const res = await ruleApi.backtestRule({
				project_id: effectiveProjectId,
				dataset_artifact_id: selectedArtifactId,
				rule_id: currentRule?.rule_id,
				condition: compiledCondition,
				action: ruleAction,
				rule_code: ruleCode,
				rule_name: ruleName,
				max_samples: 50,
			});
			if (res.success && res.data) {
				setBacktestResult(res.data);
				setFilterTab('ALL');
			} else {
				setBacktestError(res.error || 'Không thể thực thi Backtest trên Dataset Artifact đã chọn.');
			}
		} finally {
			setIsRunning(false);
		}
	};

	const handleEvaluateSingleTransaction = async (mode: 'single' | 'project-batch') => {
		setIsEvaluatingTx(true);
		setSingleEvalError(null);
		setSingleEvalResult(null);
		setBatchEvalResults(null);
		try {
			let parsed: any;
			try {
				parsed = JSON.parse(txJsonInput);
			} catch {
				setSingleEvalError('Payload JSON không hợp lệ. Vui lòng kiểm tra cú pháp JSON.');
				return;
			}

			const txId = String(parsed.transaction_id || 'TX-TEST-001');
			const rawFeatures = parsed.raw_features || parsed.mapped_features || {};
			const enrichedFeatures = parsed.enriched_features || {};

			if (mode === 'single') {
				if (!currentRule?.rule_id) {
					setSingleEvalError(
						'Quy tắc chưa được lưu vào cơ sở dữ liệu. Vui lòng nhấn "Save Rule" ở Bước 1 trước khi gọi /evaluate.'
					);
					return;
				}
				const res = await ruleApi.evaluateSingleRule(currentRule.rule_id, {
					transaction_id: txId,
					raw_features: rawFeatures,
					mapped_features: rawFeatures,
					enriched_features: enrichedFeatures,
				});
				if (res.success && res.data) {
					setSingleEvalResult(res.data);
				} else {
					setSingleEvalError(res.error || 'Lỗi khi đánh giá giao dịch đơn lẻ.');
				}
			} else {
				const res = await ruleApi.evaluateProjectRules({
					project_id: effectiveProjectId,
					transaction_id: txId,
					raw_features: rawFeatures,
					mapped_features: rawFeatures,
					enriched_features: enrichedFeatures,
				});
				if (res.success && Array.isArray(res.data)) {
					setBatchEvalResults(res.data);
				} else {
					setSingleEvalError(res.error || 'Lỗi khi đánh giá toàn bộ Active Rules của dự án.');
				}
			}
		} finally {
			setIsEvaluatingTx(false);
		}
	};

	const sampleHits = backtestResult?.sample_hits || [];
	const filteredTransactions = sampleHits.filter((tx) => {
		if (filterTab === 'TP') return tx.ground_truth === 1;
		if (filterTab === 'FP') return tx.ground_truth === 0;
		return true;
	});

	const tpSamplesCount = sampleHits.filter((t) => t.ground_truth === 1).length;
	const fpSamplesCount = sampleHits.filter((t) => t.ground_truth === 0).length;

	return (
		<div className="flex-1 p-6 space-y-5 overflow-y-auto bg-dark-950">
			{/* Top-level Error Notice from Workspace */}
			{(errorMessage || backtestError) && (
				<div className="p-3.5 rounded-xl bg-red-950/40 border border-red-500/50 text-red-300 text-xs flex items-start justify-between gap-3">
					<div className="flex items-start gap-2.5">
						<AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
						<span className="font-mono">{errorMessage || backtestError}</span>
					</div>
					{backtestError && (
						<button
							type="button"
							onClick={() => setBacktestError(null)}
							className="text-red-400 hover:text-red-200 cursor-pointer"
						>
							<X className="w-4 h-4" />
						</button>
					)}
				</div>
			)}

			{/* Mode Switcher Tabs: Historical Dataset Backtest vs Single-Transaction Evaluator */}
			<div className="flex items-center justify-between border-b border-slate-800 pb-3">
				<div className="flex items-center gap-2 bg-dark-900 p-1 rounded-lg border border-slate-800">
					<button
						type="button"
						onClick={() => setActiveMode('dataset-backtest')}
						className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition flex items-center gap-2 cursor-pointer ${
							activeMode === 'dataset-backtest'
								? 'bg-brand-600 text-white shadow-sm'
								: 'text-slate-400 hover:text-slate-200'
						}`}
					>
						<Database className="w-3.5 h-3.5" />
						<span>Historical Dataset Backtest</span>
					</button>
					<button
						type="button"
						onClick={() => setActiveMode('single-tx')}
						className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition flex items-center gap-2 cursor-pointer ${
							activeMode === 'single-tx'
								? 'bg-brand-600 text-white shadow-sm'
								: 'text-slate-400 hover:text-slate-200'
						}`}
					>
						<Terminal className="w-3.5 h-3.5" />
						<span>Single-Transaction Evaluator (/evaluate)</span>
					</button>
				</div>
			</div>

			{activeMode === 'dataset-backtest' ? (
				<>
					{/* 1. Target Dataset & Configuration Bar */}
					<div className="bg-dark-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
						<div className="flex flex-wrap items-center gap-4 flex-1">
							{/* Target Rule Summary Pill */}
							<div className="border-r border-slate-800 pr-4 hidden lg:block">
								<span className="block text-[10px] font-mono uppercase text-slate-500 mb-0.5">
									TARGET RULE
								</span>
								<div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 font-mono">
									<span className="text-brand-400 font-bold">{ruleCode}</span>
									<span
										className="text-slate-400 font-normal truncate max-w-[200px]"
										title={ruleName}
									>
										{ruleName}
									</span>
								</div>
							</div>

							{/* Dataset Artifact Selector */}
							<div className="flex-1 min-w-[280px] max-w-xl">
								<label className="block text-[10px] font-mono uppercase text-slate-400 mb-1 flex items-center gap-1.5">
									<Database className="w-3 h-3 text-brand-400" />
									<span>EVALUATION DATASET ARTIFACT</span>
								</label>
								<div className="relative">
									<select
										value={selectedArtifactId}
										onChange={(e) => setSelectedArtifactId(e.target.value)}
										disabled={isLoadingArtifacts || artifactOptions.length === 0}
										className="w-full bg-dark-850 border border-slate-800 hover:border-brand-500/60 text-slate-200 text-xs font-mono rounded-lg px-3 py-2 pr-8 focus:outline-none focus:border-brand-500 cursor-pointer transition appearance-none"
									>
										{artifactOptions.length === 0 ? (
											<option value="">
												{isLoadingArtifacts
													? 'Đang tải danh sách Dataset của dự án...'
													: 'Chưa có Dataset Artifact nào trong dự án hiện tại'}
											</option>
										) : (
											artifactOptions.map((opt) => (
												<option
													key={opt.artifact.artifact_id}
													value={opt.artifact.artifact_id}
												>
													{opt.label}
												</option>
											))
										)}
									</select>
									<div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
										<SlidersHorizontal className="w-3.5 h-3.5" />
									</div>
								</div>
							</div>
						</div>

						{/* Action Button */}
						<div className="flex items-center gap-3">
							<button
								type="button"
								onClick={handleRunSimulation}
								disabled={isRunning || !selectedArtifactId}
								className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2 cursor-pointer"
							>
								{isRunning ? (
									<RotateCcw className="w-3.5 h-3.5 animate-spin" />
								) : (
									<Play className="w-3.5 h-3.5 fill-white" />
								)}
								<span>
									{isRunning ? 'Đang thực thi Dry Run...' : 'Run Dry Run Simulation'}
								</span>
							</button>
						</div>
					</div>

					{/* 2. Telemetry KPI Cards (6-card Grid theo SUC-12) */}
					<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
						{/* Card 1: Total Rule Hits */}
						<div className="bg-dark-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all">
							<div className="text-[10px] font-mono uppercase text-slate-400 mb-1">
								TOTAL RULE HITS
							</div>
							<div className="text-2xl font-bold font-mono text-white tracking-tight">
								{backtestResult ? backtestResult.total_hits.toLocaleString() : '—'}
							</div>
							<div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
								{backtestResult ? (
									<>
										<span className="text-blue-400 font-mono font-medium">
											{(backtestResult.hit_rate * 100).toFixed(2)}%
										</span>{' '}
										of {backtestResult.total_transactions.toLocaleString()} txns
									</>
								) : (
									<span>Chưa chạy mô phỏng</span>
								)}
							</div>
						</div>

						{/* Card 2: Precision */}
						<div className="bg-dark-900 border border-emerald-500/30 hover:border-emerald-500/50 rounded-xl p-3.5 transition-all bg-gradient-to-b from-emerald-950/20 to-transparent">
							<div className="text-[10px] font-mono uppercase text-emerald-400/90 mb-1 flex items-center justify-between">
								<span>PRECISION</span>
								{backtestResult?.target_column && (
									<span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1 py-0.5 rounded font-mono font-semibold">
										{backtestResult.target_column}
									</span>
								)}
							</div>
							<div className="text-2xl font-bold font-mono text-emerald-400 tracking-tight">
								{backtestResult
									? backtestResult.has_ground_truth
										? backtestResult.precision.toFixed(3)
										: 'N/A'
									: '—'}
							</div>
							<div className="text-[11px] text-slate-400 mt-1">
								{backtestResult ? (
									backtestResult.has_ground_truth ? (
										<span>
											TP:{' '}
											<strong className="text-emerald-400 font-mono">
												{backtestResult.tp.toLocaleString()}
											</strong>{' '}
											/ FP: {backtestResult.fp.toLocaleString()}
										</span>
									) : (
										<span>Tập dữ liệu không có cột nhãn</span>
									)
								) : (
									<span>Tỷ lệ bắt đúng gian lận</span>
								)}
							</div>
						</div>

						{/* Card 3: Recall */}
						<div className="bg-dark-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all">
							<div className="text-[10px] font-mono uppercase text-slate-400 mb-1">RECALL</div>
							<div className="text-2xl font-bold font-mono text-white tracking-tight">
								{backtestResult
									? backtestResult.has_ground_truth
										? backtestResult.recall.toFixed(3)
										: 'N/A'
									: '—'}
							</div>
							<div className="text-[11px] text-slate-400 mt-1">
								{backtestResult ? (
									backtestResult.has_ground_truth ? (
										<span>
											Catches{' '}
											<strong className="text-slate-200 font-mono">
												{(backtestResult.recall * 100).toFixed(1)}%
											</strong>{' '}
											(FN: {backtestResult.fn.toLocaleString()})
										</span>
									) : (
										<span>Unlabeled dataset</span>
									)
								) : (
									<span>Độ phủ trên tổng gian lận</span>
								)}
							</div>
						</div>

						{/* Card 4: False Positive Rate */}
						<div className="bg-dark-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all">
							<div className="text-[10px] font-mono uppercase text-slate-400 mb-1">
								FALSE POSITIVE RATE
							</div>
							<div className="text-2xl font-bold font-mono text-emerald-400 tracking-tight">
								{backtestResult
									? backtestResult.has_ground_truth
										? `${(backtestResult.fpr * 100).toFixed(2)}%`
										: 'N/A'
									: '—'}
							</div>
							<div className="text-[11px] text-slate-400 mt-1">
								{backtestResult && backtestResult.has_ground_truth
									? `${backtestResult.fp.toLocaleString()} FP / ${backtestResult.tn.toLocaleString()} TN`
									: 'Tỷ lệ cảnh báo giả'}
							</div>
						</div>

						{/* Card 5: Execution Latency */}
						<div className="bg-dark-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all">
							<div className="text-[10px] font-mono uppercase text-slate-400 mb-1">
								EXECUTION LATENCY
							</div>
							<div className="text-2xl font-bold font-mono text-white tracking-tight">
								{backtestResult ? `${backtestResult.execution_time_ms.toFixed(1)} ms` : '—'}
							</div>
							<div className="text-[11px] text-slate-400 mt-1">
								{backtestResult ? (
									<span>
										Avg:{' '}
										<strong className="text-amber-400 font-mono">
											{backtestResult.avg_execution_time_ms.toFixed(3)} ms/tx
										</strong>
									</span>
								) : (
									<span>
										Action:{' '}
										<strong className="text-amber-400 font-mono">{ruleAction}</strong>
									</span>
								)}
							</div>
						</div>

						{/* Card 6: Fraud Prevented */}
						<div className="bg-dark-900 border border-blue-500/30 hover:border-blue-500/50 rounded-xl p-3.5 transition-all bg-gradient-to-b from-blue-950/20 to-transparent">
							<div className="text-[10px] font-mono uppercase text-blue-400 mb-1">
								FRAUD PREVENTED
							</div>
							<div className="text-2xl font-bold font-mono text-blue-400 tracking-tight">
								{backtestResult
									? `$${backtestResult.fraud_amount_caught.toLocaleString(undefined, {
											minimumFractionDigits: 2,
											maximumFractionDigits: 2,
										})}`
									: '—'}
							</div>
							<div className="text-[11px] text-slate-400 mt-1">
								Tổng giá trị giao dịch bắt trúng
							</div>
						</div>
					</div>

					{/* 3. Sample Hits Inspection Matrix Table */}
					<div className="bg-dark-900 border border-slate-800 rounded-xl p-4 space-y-3 shadow-sm">
						<div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
							<div className="flex items-center gap-2">
								<span className="text-xs font-bold font-mono uppercase text-slate-200">
									SAMPLE HITS INSPECTION MATRIX
								</span>
								<span className="text-[10px] font-mono text-slate-400 bg-dark-850 px-2 py-0.5 rounded border border-slate-800">
									{backtestResult
										? `Showing ${filteredTransactions.length} sample hits (Total hits: ${backtestResult.total_hits.toLocaleString()})`
										: 'Nhấn "Run Dry Run Simulation" để xem kết quả thực tế'}
								</span>
							</div>

							{/* Filter Tabs */}
							<div className="flex items-center bg-dark-850 p-1 rounded-lg border border-slate-800 text-xs">
								<button
									type="button"
									onClick={() => setFilterTab('ALL')}
									className={`px-3 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
										filterTab === 'ALL'
											? 'bg-blue-600/20 text-blue-300 font-semibold border border-blue-500/30'
											: 'text-slate-400 hover:text-slate-200'
									}`}
								>
									All Samples ({sampleHits.length})
								</button>
								<button
									type="button"
									onClick={() => setFilterTab('TP')}
									className={`px-3 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
										filterTab === 'TP'
											? 'bg-emerald-600/20 text-emerald-300 font-semibold border border-emerald-500/30'
											: 'text-slate-400 hover:text-slate-200'
									}`}
								>
									True Positives ({tpSamplesCount})
								</button>
								<button
									type="button"
									onClick={() => setFilterTab('FP')}
									className={`px-3 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
										filterTab === 'FP'
											? 'bg-amber-600/20 text-amber-300 font-semibold border border-amber-500/30'
											: 'text-slate-400 hover:text-slate-200'
									}`}
								>
									False Positives ({fpSamplesCount})
								</button>
							</div>
						</div>

						{/* Table Viewport */}
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead>
									<tr className="text-[10px] font-mono uppercase text-slate-400 border-b border-slate-800 bg-dark-950/60">
										<th className="py-2.5 px-3">EVENT_ID</th>
										<th className="py-2.5 px-3">TIMESTAMP</th>
										<th className="py-2.5 px-3">AMOUNT</th>
										<th className="py-2.5 px-3">USER_ID</th>
										<th className="py-2.5 px-3">GROUND TRUTH</th>
										<th className="py-2.5 px-3">MATCHED CLAUSES</th>
										<th className="py-2.5 px-3 text-right">ACTION</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-800 font-mono text-[11px]">
									{!backtestResult ? (
										<tr>
											<td colSpan={7} className="py-10 text-center text-slate-500">
												Chọn một Dataset Artifact phía trên và nhấn{' '}
												<strong className="text-slate-300">Run Dry Run Simulation</strong> để
												chạy kiểm thử quy tắc trên dữ liệu thật.
											</td>
										</tr>
									) : filteredTransactions.length === 0 ? (
										<tr>
											<td colSpan={7} className="py-10 text-center text-slate-500">
												Không có giao dịch nào khớp với bộ lọc hiện tại.
											</td>
										</tr>
									) : (
										filteredTransactions.map((tx) => (
											<tr
												key={tx.event_id}
												className={`hover:bg-dark-850/80 transition-colors ${
													tx.ground_truth === 1 ? 'bg-emerald-950/10' : ''
												}`}
											>
												<td className="py-2.5 px-3 font-bold text-blue-400">{tx.event_id}</td>
												<td className="py-2.5 px-3 text-slate-400">{tx.timestamp}</td>
												<td className="py-2.5 px-3 text-white font-bold">
													${tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
												</td>
												<td className="py-2.5 px-3 text-slate-300">{tx.user_id}</td>
												<td className="py-2.5 px-3">
													{tx.ground_truth === 1 ? (
														<span className="bg-rose-500/20 text-rose-400 border border-rose-500/40 px-2 py-0.5 rounded text-[10px] font-bold">
															1 - FRAUD
														</span>
													) : tx.ground_truth === 0 ? (
														<span className="bg-slate-700/40 text-slate-300 border border-slate-600/40 px-2 py-0.5 rounded text-[10px] font-bold">
															0 - LEGIT
														</span>
													) : (
														<span className="bg-slate-800 text-slate-400 px-2 py-0.5 rounded text-[10px]">
															UNLABELED
														</span>
													)}
												</td>
												<td className="py-2.5 px-3">
													<div className="flex flex-wrap gap-1 font-sans">
														{tx.matched_clauses.map((clause, idx) => (
															<span
																key={idx}
																className="bg-dark-800 border border-slate-800 text-slate-300 px-1.5 py-0.5 rounded text-[10px]"
															>
																{clause}
															</span>
														))}
													</div>
												</td>
												<td className="py-2.5 px-3 text-right">
													<button
														type="button"
														onClick={() => setInspectingTx(tx)}
														className="text-blue-400 hover:text-blue-300 text-[11px] hover:underline font-sans cursor-pointer"
													>
														Inspect AST
													</button>
												</td>
											</tr>
										))
									)}
								</tbody>
							</table>
						</div>
					</div>
				</>
			) : (
				/* Mode 2: Single-Transaction Evaluator (/evaluate & /evaluate-batch) */
				<div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
					{/* Left JSON Editor (6 cols) */}
					<div className="lg:col-span-6 bg-dark-900 border border-slate-800 rounded-xl p-5 space-y-4">
						<div className="flex items-center justify-between border-b border-slate-800 pb-3">
							<div>
								<h3 className="text-xs font-bold font-mono uppercase text-slate-200">
									TRANSACTION EXECUTION CONTEXT (JSON)
								</h3>
								<p className="text-[11px] text-slate-400 mt-0.5">
									Kiểm thử trực tiếp quy tắc hiện tại hoặc toàn bộ Active Rules của dự án trên một
									giao dịch JSON.
								</p>
							</div>
						</div>

						<textarea
							rows={14}
							value={txJsonInput}
							onChange={(e) => setTxJsonInput(e.target.value)}
							className="w-full bg-dark-950 border border-slate-800 focus:border-brand-500 rounded-lg p-3.5 font-mono text-xs text-slate-200 focus:outline-none leading-relaxed"
						/>

						{singleEvalError && (
							<div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 text-red-300 text-xs font-mono">
								{singleEvalError}
							</div>
						)}

						<div className="flex flex-wrap items-center gap-3 pt-1">
							<button
								type="button"
								disabled={isEvaluatingTx}
								onClick={() => handleEvaluateSingleTransaction('single')}
								className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2 cursor-pointer"
							>
								<Play className="w-3.5 h-3.5 fill-white" />
								<span>Evaluate Current Rule ({ruleCode})</span>
							</button>

							<button
								type="button"
								disabled={isEvaluatingTx}
								onClick={() => handleEvaluateSingleTransaction('project-batch')}
								className="px-4 py-2 rounded-lg bg-dark-850 hover:bg-dark-800 border border-slate-700 text-slate-200 text-xs font-medium transition flex items-center gap-2 cursor-pointer"
							>
								<ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
								<span>Evaluate All Active Project Rules</span>
							</button>
						</div>
					</div>

					{/* Right Evaluation Output (6 cols) */}
					<div className="lg:col-span-6 bg-dark-900 border border-slate-800 rounded-xl p-5 space-y-4">
						<div className="border-b border-slate-800 pb-3">
							<h3 className="text-xs font-bold font-mono uppercase text-slate-200">
								EVALUATION RESULT
							</h3>
							<p className="text-[11px] text-slate-400 mt-0.5">
								Kết quả trả về từ <code className="font-mono text-brand-300">RuleExecutor</code>
							</p>
						</div>

						{singleEvalResult ? (
							<div className="space-y-3">
								<div
									className={`p-4 rounded-xl border flex items-center justify-between ${
										singleEvalResult.is_triggered
											? 'bg-emerald-950/30 border-emerald-500/50 text-emerald-300'
											: 'bg-slate-900 border-slate-800 text-slate-300'
									}`}
								>
									<div>
										<div className="text-[10px] font-mono uppercase text-slate-400">
											Rule {singleEvalResult.rule_code} (v{singleEvalResult.version_number})
										</div>
										<div className="text-sm font-bold font-mono mt-0.5">
											{singleEvalResult.is_triggered ? 'TRIGGERED (MATCHED)' : 'NOT TRIGGERED'}
										</div>
										<div className="text-xs text-slate-400 mt-1">
											{singleEvalResult.trigger_reason}
										</div>
									</div>
									<div className="text-right font-mono">
										<span className="px-2.5 py-1 rounded text-xs font-bold bg-dark-950 border border-slate-700">
											Action: {singleEvalResult.action}
										</span>
										<div className="text-[11px] text-slate-400 mt-1.5">
											{singleEvalResult.execution_time_ms.toFixed(3)} ms
										</div>
									</div>
								</div>
							</div>
						) : batchEvalResults ? (
							<div className="space-y-2.5">
								{batchEvalResults.length === 0 ? (
									<div className="py-8 text-center text-xs text-slate-500 font-mono">
										Dự án hiện chưa có quy tắc nào ở trạng thái ACTIVE.
									</div>
								) : (
									batchEvalResults.map((r) => (
										<div
											key={r.rule_id}
											className={`p-3 rounded-lg border flex items-center justify-between text-xs font-mono ${
												r.is_triggered
													? 'bg-emerald-950/25 border-emerald-500/40 text-emerald-300'
													: 'bg-dark-950 border-slate-800 text-slate-400'
											}`}
										>
											<div>
												<span className="font-bold text-brand-300">{r.rule_code}</span> —{' '}
												<span className="text-slate-200">{r.rule_name}</span> (v{r.version_number})
												<div className="text-[11px] text-slate-400 mt-0.5">{r.trigger_reason}</div>
											</div>
											<div className="text-right">
												<span
													className={`px-2 py-0.5 rounded text-[10px] font-bold ${
														r.is_triggered
															? 'bg-emerald-500/20 text-emerald-300'
															: 'bg-slate-800 text-slate-400'
													}`}
												>
													{r.is_triggered ? `TRIGGERED (${r.action})` : 'PASS'}
												</span>
												<div className="text-[10px] text-slate-500 mt-1">
													{r.execution_time_ms.toFixed(3)} ms
												</div>
											</div>
										</div>
									))
								)}
							</div>
						) : (
							<div className="py-12 text-center text-xs text-slate-500 font-mono">
								Nhấn &ldquo;Evaluate Current Rule&rdquo; hoặc &ldquo;Evaluate All Active Project
								Rules&rdquo; để xem kết quả.
							</div>
						)}
					</div>
				</div>
			)}

			{/* 4. Inspect AST Modal */}
			{inspectingTx && (
				<div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
					<div className="bg-dark-900 border border-slate-800 rounded-xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-fade-in">
						{/* Modal Header */}
						<div className="p-4 border-b border-slate-800 flex items-center justify-between bg-dark-850">
							<div className="flex items-center gap-2">
								<FileCode2 className="w-4 h-4 text-brand-400" />
								<h3 className="text-sm font-semibold text-slate-100 font-mono">
									Inspect AST Evaluation: {inspectingTx.event_id}
								</h3>
							</div>
							<button
								type="button"
								onClick={() => setInspectingTx(null)}
								className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-dark-800 transition"
							>
								<X className="w-4 h-4" />
							</button>
						</div>

						{/* Modal Body */}
						<div className="p-5 space-y-4 overflow-y-auto">
							<div className="grid grid-cols-2 gap-3 text-xs">
								<div className="p-3 bg-dark-950 rounded-lg border border-slate-800">
									<span className="text-[10px] font-mono uppercase text-slate-500 block">
										Event Details
									</span>
									<div className="mt-1 font-mono text-slate-200 space-y-0.5">
										<div>
											User ID: <span className="text-blue-400">{inspectingTx.user_id}</span>
										</div>
										<div>
											Amount:{' '}
											<span className="text-emerald-400 font-bold">
												${inspectingTx.amount.toFixed(2)}
											</span>
										</div>
										<div>
											Timestamp: <span className="text-slate-400">{inspectingTx.timestamp}</span>
										</div>
									</div>
								</div>

								<div className="p-3 bg-dark-950 rounded-lg border border-slate-800">
									<span className="text-[10px] font-mono uppercase text-slate-500 block">
										Ground Truth vs Rule Action
									</span>
									<div className="mt-1 font-mono text-slate-200 space-y-0.5">
										<div>
											Ground Truth:{' '}
											{inspectingTx.ground_truth === 1 ? (
												<span className="text-rose-400 font-bold">FRAUD (1)</span>
											) : inspectingTx.ground_truth === 0 ? (
												<span className="text-slate-300 font-bold">LEGIT (0)</span>
											) : (
												<span className="text-slate-400">UNLABELED</span>
											)}
										</div>
										<div>
											Predicted Action:{' '}
											<span className="text-amber-400 font-bold">{ruleAction}</span>
										</div>
										<div>
											Rule Code: <span className="text-brand-300">{ruleCode}</span>
										</div>
									</div>
								</div>
							</div>

							{/* Matched Clauses Evaluation */}
							<div>
								<span className="text-[11px] font-mono uppercase text-slate-400 mb-2 block font-semibold">
									AST Clause Evaluation Breakdown
								</span>
								<div className="space-y-1.5 font-mono text-xs">
									{inspectingTx.matched_clauses.map((clause, idx) => (
										<div
											key={idx}
											className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between"
										>
											<div className="flex items-center gap-2">
												<CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
												<span className="text-emerald-300">{clause}</span>
											</div>
											<span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/20 px-1.5 py-0.5 rounded">
												TRUE
											</span>
										</div>
									))}
								</div>
							</div>

							{/* Full Feature Context JSON */}
							<div>
								<span className="text-[11px] font-mono uppercase text-slate-400 mb-1.5 block font-semibold">
									Transaction Feature Context
								</span>
								<pre className="p-3 bg-dark-950 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
									{JSON.stringify(inspectingTx.features, null, 2)}
								</pre>
							</div>
						</div>

						{/* Modal Footer */}
						<div className="p-4 border-t border-slate-800 bg-dark-850 flex justify-end">
							<button
								type="button"
								onClick={() => setInspectingTx(null)}
								className="px-4 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 border border-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer"
							>
								Đóng
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};
