import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
	ArrowLeft,
	Download,
	Search,
	ShieldAlert,
	ShieldCheck,
	AlertTriangle,
	CheckCircle2,
	Send,
	X,
	Cpu,
	Database,
	FileSpreadsheet,
	Filter,
	BarChart3,
	ExternalLink,
	Loader2,
} from 'lucide-react';
import { PageHeader } from '../../layout/PageHeader';
import { detectionApi } from '@/api';
import { useProject } from '@/hooks';
import type {
	DetectionActionFilter,
	DetectionDecisionAction,
	DetectionTransactionRecord,
} from '@/types';

const ACTION_BADGE_STYLES: Record<DetectionDecisionAction, string> = {
	REJECT: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
	REVIEW: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
	ALLOW: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
};

export function DetectionResultExplorerView() {
	const { jobId = '' } = useParams<{ jobId: string }>();
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const { currentProject } = useProject();
	const projectId = currentProject?.project_id || '';

	// Filters
	const [actionFilter, setActionFilter] = useState<DetectionActionFilter>('ALL');
	const [ruleCodeFilter, setRuleCodeFilter] = useState<string>('');
	const [searchQuery, setSearchQuery] = useState<string>('');

	// Selection & Drawer / Modal state
	const [selectedEventIds, setSelectedEventIds] = useState<string[]>([]);
	const [activeRecord, setActiveRecord] =
		useState<DetectionTransactionRecord | null>(null);
	const [isDispatchModalOpen, setIsDispatchModalOpen] = useState<boolean>(false);
	const [analystNotes, setAnalystNotes] = useState<string>('');
	const [dispatchSuccessCount, setDispatchSuccessCount] = useState<number | null>(
		null
	);

	const {
		data: resultsRes,
		isLoading,
		refetch,
	} = useQuery({
		queryKey: [
			'detection-job-results',
			jobId,
			actionFilter,
			ruleCodeFilter,
			searchQuery,
		],
		queryFn: () =>
			detectionApi.getJobResults({
				jobId,
				actionFilter,
				ruleCode: ruleCodeFilter || undefined,
				search: searchQuery.trim() || undefined,
				limit: 300,
				offset: 0,
			}),
		enabled: Boolean(jobId),
	});

	const job = resultsRes?.data?.job;
	const transactions = useMemo(
		() => resultsRes?.data?.transactions || [],
		[resultsRes]
	);
	const totalFiltered = resultsRes?.data?.total_filtered ?? 0;
	const metrics = resultsRes?.data?.summary_metrics || job?.summary_metrics || {};

	const scoreDistribution = metrics.score_distribution || [];
	const ruleBreakdown = metrics.rule_trigger_breakdown || [];
	const maxBinCount = useMemo(() => {
		return Math.max(1, ...scoreDistribution.map((b) => b.count));
	}, [scoreDistribution]);

	const toggleSelectEvent = (eventId: string) => {
		setSelectedEventIds((prev) =>
			prev.includes(eventId)
				? prev.filter((id) => id !== eventId)
				: [...prev, eventId]
		);
	};

	const selectAllFlaggedInView = () => {
		const flaggedIds = transactions
			.filter((tx) => tx.is_flagged && !tx.case_id)
			.map((tx) => tx.event_id);
		setSelectedEventIds(flaggedIds);
	};

	const dispatchMutation = useMutation({
		mutationFn: async (eventIdsToDispatch: string[]) => {
			const res = await detectionApi.sendToInvestigation(jobId, {
				event_ids: eventIdsToDispatch,
				analyst_notes: analystNotes.trim() || undefined,
			});
			if (!res.success || !res.data) {
				throw new Error(res.error || 'Failed to dispatch cases to investigation.');
			}
			return res.data;
		},
		onSuccess: (createdCases) => {
			setDispatchSuccessCount(createdCases.length);
			setSelectedEventIds([]);
			refetch();
			queryClient.invalidateQueries({
				queryKey: ['investigation-cases', projectId],
			});
		},
	});

	const handleExport = (format: 'csv' | 'parquet', onlyFlagged: boolean) => {
		const url = detectionApi.getExportUrl({
			jobId,
			fileFormat: format,
			onlyFlagged,
		});
		window.open(url, '_blank');
	};

	if (isLoading && !job) {
		return (
			<div className="flex-1 flex items-center justify-center bg-dark-950 text-xs text-slate-400 gap-2">
				<Loader2 className="w-5 h-5 animate-spin text-brand-400" />
				<span>Loading detection job results...</span>
			</div>
		);
	}

	if (!job) {
		return (
			<div className="flex-1 flex flex-col items-center justify-center bg-dark-950 p-6 text-center space-y-3">
				<AlertTriangle className="w-8 h-8 text-amber-400" />
				<h3 className="text-sm font-semibold text-slate-200">
					Detection Job Not Found
				</h3>
				<button
					type="button"
					onClick={() => navigate('/detection')}
					className="px-4 py-2 rounded-lg bg-brand-600 text-xs font-semibold text-white"
				>
					Back to Detection Jobs
				</button>
			</div>
		);
	}

	const rejectCount = metrics?.reject_count ?? 0;
	const reviewCount = metrics?.review_count ?? 0;
	const allowCount =
		metrics?.allow_count ?? Math.max(0, (job?.total_records || 0) - (job?.fraud_records || 0));
	const amountAtRisk = metrics?.amount_at_risk ?? 0;
	const flagRatePct = (((job?.fraud_rate ?? 0)) * 100).toFixed(2);
	const hasModel = Boolean(job?.model_version_id);
	const isArtifact =
		metrics?.input_source_type === 'ARTIFACT' || Boolean(job?.target_artifact_id);

	return (
		<div className="flex-1 flex flex-col overflow-hidden bg-dark-950 relative">
			<PageHeader
				title={job?.job_name || `Detection Job ${job?.job_id?.slice(0, 8) ?? ''}`}
				subtitle={`Input: ${metrics?.input_label || job?.input_path?.split(/[/\\]/).pop()} • Engine: ${
					hasModel
						? `${metrics?.model_display_name || metrics?.model_name || 'AI Model'} (v${metrics?.semver || '1.0.0'}, θ=${job?.score_threshold?.toFixed(2) ?? '0.50'})`
						: 'Rule-Only Mode'
				} • Active Rules: ${job?.use_rules ? (metrics?.active_rules_count ?? 'ON') : 'OFF'}`}
				badge={job?.status}
				badgeColor={job?.status === 'COMPLETED' ? 'green' : 'amber'}
				breadcrumbs={[
					{ label: 'Detection Jobs', onClick: () => navigate('/detection') },
					{ label: job?.job_name || job?.job_id?.slice(0, 8) || '' },
				]}
				actions={
					<div className="flex items-center gap-2">
						<button
							type="button"
							onClick={() => handleExport('csv', false)}
							className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs font-medium text-slate-200 flex items-center gap-1.5 transition"
						>
							<Download className="w-3.5 h-3.5 text-emerald-400" />
							Export CSV
						</button>
						<button
							type="button"
							onClick={() => handleExport('parquet', true)}
							className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs font-medium text-slate-200 flex items-center gap-1.5 transition"
						>
							<Download className="w-3.5 h-3.5 text-sky-400" />
							Flagged Parquet
						</button>
						<button
							type="button"
							onClick={() => navigate('/detection')}
							className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs font-medium text-slate-300 flex items-center gap-1.5 transition"
						>
							<ArrowLeft className="w-3.5 h-3.5" />
							All Jobs
						</button>
					</div>
				}
			/>

			<div className="flex-1 overflow-y-auto p-6 space-y-5">
				{job.status === 'FAILED' && (
					<div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2.5">
						<AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
						<div>
							<div className="font-bold text-rose-200">Detection Job Failed</div>
							<div className="mt-0.5 text-rose-300/90">
								{job.error_message || 'An error occurred during batch execution.'}
							</div>
						</div>
					</div>
				)}

				{/* 6 KPI Summary Cards */}
				<div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
					<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
						<span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1">
							{isArtifact ? (
								<Database className="w-3 h-3 text-sky-400" />
							) : (
								<FileSpreadsheet className="w-3 h-3 text-emerald-400" />
							)}
							Total Scanned
						</span>
						<div className="text-xl font-bold font-mono text-slate-100 mt-1">
							{job?.total_records?.toLocaleString() ?? '—'}
						</div>
						<div className="text-[10px] text-slate-500 font-mono mt-0.5">
							Runtime: {job?.execution_time_seconds != null ? `${job.execution_time_seconds.toFixed(2)}s` : '—'}
						</div>
					</div>

					<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
						<span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
							Total Flagged
						</span>
						<div className="text-xl font-bold font-mono text-amber-400 mt-1">
							{job?.fraud_records?.toLocaleString() ?? '—'}
						</div>
						<div className="text-[10px] text-slate-400 font-mono mt-0.5">
							Rate: {flagRatePct}%
						</div>
					</div>

					<div className="p-3.5 rounded-xl bg-dark-900 border border-rose-500/25">
						<span className="text-[10px] font-semibold uppercase tracking-wider text-rose-300">
							Immediate Block (REJECT)
						</span>
						<div className="text-xl font-bold font-mono text-rose-400 mt-1">
							{rejectCount.toLocaleString()}
						</div>
						<div className="text-[10px] text-slate-500 mt-0.5">
							Hard rule violation
						</div>
					</div>

					<div className="p-3.5 rounded-xl bg-dark-900 border border-amber-500/25">
						<span className="text-[10px] font-semibold uppercase tracking-wider text-amber-300">
							Manual Review (REVIEW)
						</span>
						<div className="text-xl font-bold font-mono text-amber-400 mt-1">
							{reviewCount.toLocaleString()}
						</div>
						<div className="text-[10px] text-slate-500 mt-0.5">
							Score ≥ θ or Review Rule
						</div>
					</div>

					<div className="p-3.5 rounded-xl bg-dark-900 border border-emerald-500/25">
						<span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
							Clean Pass (ALLOW)
						</span>
						<div className="text-xl font-bold font-mono text-emerald-400 mt-1">
							{allowCount.toLocaleString()}
						</div>
						<div className="text-[10px] text-slate-500 mt-0.5">
							Below risk threshold
						</div>
					</div>

					<div className="p-3.5 rounded-xl bg-dark-900 border border-dark-800">
						<span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
							Amount at Risk
						</span>
						<div className="text-xl font-bold font-mono text-rose-300 mt-1">
							${(amountAtRisk ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
						</div>
						<div className="text-[10px] text-slate-500 mt-0.5">
							Flagged volume sum
						</div>
					</div>
				</div>

				{/* Analytics Row: Score Distribution Histogram + Rule Trigger Breakdown */}
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
					{/* AI Score Distribution */}
					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 space-y-3">
						<div className="flex items-center justify-between">
							<div className="flex items-center gap-2">
								<BarChart3 className="w-4 h-4 text-brand-400" />
								<h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
									AI Risk Score Distribution
								</h3>
							</div>
							<span className="text-[11px] font-mono text-brand-300">
								Threshold θ = {job?.score_threshold?.toFixed(2) ?? '0.50'}
							</span>
						</div>

						<div className="h-36 flex items-end gap-2 pt-4 pb-1 px-2 bg-dark-950 rounded-lg border border-dark-800">
							{scoreDistribution.map((bin, idx) => {
								const lowerVal = bin?.lower ?? idx * 0.1;
								const upperVal = bin?.upper ?? (idx + 1) * 0.1;
								const binLabel = bin?.bin ?? `${lowerVal.toFixed(1)}-${upperVal.toFixed(1)}`;
								const heightPct = Math.max(
									6,
									Math.round(((bin?.count ?? 0) / maxBinCount) * 100)
								);
								const isAboveThreshold =
									job?.score_threshold != null && bin?.upper != null
										? bin.upper > job.score_threshold
										: false;
								return (
									<div
										key={binLabel || idx}
										className="flex-1 flex flex-col items-center gap-1 h-full justify-end group"
									>
										<span className="text-[9px] font-mono text-slate-400">
											{bin?.count ?? 0}
										</span>
										<div
											style={{ height: `${heightPct}%` }}
											title={`${binLabel}: ${bin?.count ?? 0} transactions (${bin?.flagged_count ?? 0} flagged)`}
											className={`w-full rounded-t transition ${
												isAboveThreshold
													? 'bg-rose-500/70 group-hover:bg-rose-400 border-t border-rose-300'
													: 'bg-brand-500/50 group-hover:bg-brand-400 border-t border-brand-300'
											}`}
										/>
										<span className="text-[9px] font-mono text-slate-500 truncate">
											{bin?.lower?.toFixed(1) ?? lowerVal.toFixed(1)}
										</span>
									</div>
								);
							})}
						</div>
					</div>

					{/* Rule Trigger Breakdown */}
					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 space-y-3">
						<div className="flex items-center justify-between">
							<div className="flex items-center gap-2">
								<ShieldAlert className="w-4 h-4 text-amber-400" />
								<h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
									Active Rule Trigger Breakdown
								</h3>
							</div>
							{ruleCodeFilter && (
								<button
									type="button"
									onClick={() => setRuleCodeFilter('')}
									className="text-[11px] text-brand-400 hover:underline font-mono"
								>
									Clear filter ({ruleCodeFilter})
								</button>
							)}
						</div>

						{ruleBreakdown.length === 0 ? (
							<div className="h-36 flex items-center justify-center bg-dark-950 rounded-lg border border-dark-800 text-xs text-slate-500">
								No active rules evaluated in this job.
							</div>
						) : (
							<div className="max-h-36 overflow-y-auto rounded-lg border border-dark-800 bg-dark-950">
								<table className="w-full text-left text-xs">
									<thead className="bg-dark-900 text-[10px] font-semibold uppercase text-slate-400 border-b border-dark-800">
										<tr>
											<th className="py-2 px-3">Rule</th>
											<th className="py-2 px-3">Action</th>
											<th className="py-2 px-3 text-right">Hits</th>
											<th className="py-2 px-3 text-right">Hit Rate</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-dark-800/60">
										{ruleBreakdown.map((rb) => {
											const isSelected = ruleCodeFilter === rb.rule_code;
											return (
												<tr
													key={rb.rule_code}
													onClick={() =>
														setRuleCodeFilter(
															isSelected ? '' : rb.rule_code
														)
													}
													className={`cursor-pointer transition ${
														isSelected
															? 'bg-brand-500/15'
															: 'hover:bg-dark-900/70'
													}`}
												>
													<td className="py-2 px-3">
														<span className="font-mono font-semibold text-slate-200">
															{rb.rule_code}
														</span>
														<span className="text-slate-400 ml-2 text-[11px]">
															{rb.rule_name}
														</span>
													</td>
													<td className="py-2 px-3">
														<span
															className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${
																ACTION_BADGE_STYLES[rb.action] ||
																ACTION_BADGE_STYLES.REVIEW
															}`}
														>
															{rb.action}
														</span>
													</td>
													<td className="py-2 px-3 text-right font-mono text-slate-200">
														{rb?.hit_count?.toLocaleString() ?? '0'}
													</td>
													<td className="py-2 px-3 text-right font-mono text-slate-400">
														{rb?.hit_rate != null ? (rb.hit_rate * 100).toFixed(1) : '0.0'}%
													</td>
												</tr>
											);
										})}
									</tbody>
								</table>
							</div>
						)}
					</div>
				</div>

				{/* Filter & Bulk Action Bar */}
				<div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3.5 rounded-xl bg-dark-900 border border-dark-800">
					<div className="flex flex-wrap items-center gap-2">
						{(
							[
								{ id: 'ALL', label: 'All Records' },
								{ id: 'FLAGGED', label: 'Flagged (REJECT + REVIEW)' },
								{ id: 'REJECT', label: 'REJECT Only' },
								{ id: 'REVIEW', label: 'REVIEW Only' },
								{ id: 'ALLOW', label: 'ALLOW Only' },
							] as const
						).map((tab) => (
							<button
								key={tab.id}
								type="button"
								onClick={() => setActionFilter(tab.id)}
								className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
									actionFilter === tab.id
										? 'bg-brand-600/20 text-brand-300 border border-brand-500/40'
										: 'bg-dark-950 text-slate-400 border border-dark-800 hover:text-slate-200'
								}`}
							>
								{tab.label}
							</button>
						))}

						<div className="relative w-64">
							<Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
							<input
								type="text"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
								placeholder="Search event_id or user_id..."
								className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-dark-950 border border-dark-700 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500"
							/>
						</div>
					</div>

					<div className="flex items-center gap-2">
						<button
							type="button"
							onClick={selectAllFlaggedInView}
							className="px-3 py-1.5 rounded-lg bg-dark-950 hover:bg-dark-850 border border-dark-700 text-xs text-slate-300 transition"
						>
							Select All Flagged
						</button>
						{selectedEventIds.length > 0 && (
							<button
								type="button"
								onClick={() => {
									setDispatchSuccessCount(null);
									setIsDispatchModalOpen(true);
								}}
								className="px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-dark-950 text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-amber-500/20 transition"
							>
								<Send className="w-3.5 h-3.5" />
								Send to Investigation ({selectedEventIds.length})
							</button>
						)}
					</div>
				</div>

				{/* Transactions Table */}
				<div className="rounded-xl bg-dark-900 border border-dark-800 overflow-hidden">
					<div className="px-4 py-2.5 border-b border-dark-800 bg-dark-950/50 flex items-center justify-between text-[11px] text-slate-400">
						<span className="flex items-center gap-1.5">
							<Filter className="w-3.5 h-3.5 text-brand-400" />
							Showing <strong className="text-slate-200 font-mono">{transactions.length}</strong> of{' '}
							<strong className="text-slate-200 font-mono">{totalFiltered}</strong> matching transactions
						</span>
						<span>Click any row to inspect full AI + Rule Evidence</span>
					</div>

					<div className="overflow-x-auto">
						<table className="w-full text-left border-collapse">
							<thead>
								<tr className="border-b border-dark-800 bg-dark-950/70 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
									<th className="py-3 px-3 w-9">
										<input
											type="checkbox"
											checked={
												transactions.length > 0 &&
												selectedEventIds.length === transactions.length
											}
											onChange={(e) => {
												if (e.target.checked) {
													setSelectedEventIds(
														transactions.map((t) => t.event_id)
													);
												} else {
													setSelectedEventIds([]);
												}
											}}
											className="rounded border-dark-700 bg-dark-950 text-brand-500"
										/>
									</th>
									<th className="py-3 px-3">Event ID</th>
									<th className="py-3 px-3">User / Entity</th>
									<th className="py-3 px-3">Timestamp</th>
									<th className="py-3 px-3 text-right">Amount</th>
									<th className="py-3 px-3">AI Model Score</th>
									<th className="py-3 px-3">Triggered Rules</th>
									<th className="py-3 px-3">Final Decision</th>
									<th className="py-3 px-3 text-right">Investigation</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-dark-800/70 text-xs">
								{transactions.map((tx) => {
									const isChecked = selectedEventIds.includes(tx.event_id);
									const scorePct = Math.min(
										100,
										Math.max(0, Math.round(tx.model_score * 100))
									);
									const isOverThreshold =
										hasModel &&
										job.score_threshold != null &&
										tx.model_score >= job.score_threshold;

									return (
										<tr
											key={`${tx.row_index}-${tx.event_id}`}
											onClick={() => setActiveRecord(tx)}
											className={`cursor-pointer transition ${
												activeRecord?.event_id === tx.event_id
													? 'bg-brand-500/15'
													: 'hover:bg-dark-850/70'
											}`}
										>
											<td
												className="py-3 px-3"
												onClick={(e) => e.stopPropagation()}
											>
												<input
													type="checkbox"
													checked={isChecked}
													onChange={() => toggleSelectEvent(tx.event_id)}
													className="rounded border-dark-700 bg-dark-950 text-brand-500"
												/>
											</td>
											<td className="py-3 px-3 font-mono font-semibold text-slate-200">
												{tx.event_id}
											</td>
											<td className="py-3 px-3 font-mono text-slate-300">
												{tx.user_id}
											</td>
											<td className="py-3 px-3 font-mono text-[11px] text-slate-400">
												{tx.timestamp}
											</td>
											<td className="py-3 px-3 text-right font-mono font-semibold text-slate-200">
												${(tx.amount ?? 0).toLocaleString(undefined, {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</td>
											<td className="py-3 px-3">
												{hasModel ? (
													<div className="flex items-center gap-2">
														<div className="w-20 h-1.5 rounded-full bg-dark-800 overflow-hidden">
															<div
																style={{ width: `${scorePct}%` }}
																className={`h-full rounded-full ${
																	isOverThreshold
																		? 'bg-rose-500'
																		: 'bg-emerald-500'
																}`}
															/>
														</div>
														<span
															className={`font-mono font-semibold ${
																isOverThreshold
																	? 'text-rose-300'
																	: 'text-slate-300'
															}`}
														>
															{tx.model_score != null ? tx.model_score.toFixed(4) : '—'}
														</span>
													</div>
												) : (
													<span className="text-[11px] font-mono text-slate-500">
														N/A (Rule-Only)
													</span>
												)}
											</td>
											<td className="py-3 px-3">
												{tx.triggered_rules.length === 0 ? (
													<span className="text-[11px] text-slate-500">
														None
													</span>
												) : (
													<div className="flex flex-wrap gap-1">
														{tx.triggered_rules.map((rc) => (
															<span
																key={rc}
																className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono text-[10px]"
															>
																{rc}
															</span>
														))}
													</div>
												)}
											</td>
											<td className="py-3 px-3">
												<span
													className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
														ACTION_BADGE_STYLES[tx.final_action] ||
														ACTION_BADGE_STYLES.ALLOW
													}`}
												>
													{tx.final_action}
												</span>
											</td>
											<td
												className="py-3 px-3 text-right"
												onClick={(e) => e.stopPropagation()}
											>
												{tx.case_id ? (
													<button
														type="button"
														onClick={() => navigate('/investigation')}
														className="px-2 py-1 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono inline-flex items-center gap-1"
													>
														<CheckCircle2 className="w-3 h-3" />
														Dispatched
													</button>
												) : (
													<button
														type="button"
														onClick={() => {
															setSelectedEventIds([tx.event_id]);
															setDispatchSuccessCount(null);
															setIsDispatchModalOpen(true);
														}}
														className="px-2 py-1 rounded bg-dark-850 hover:bg-amber-500/20 text-slate-300 hover:text-amber-300 border border-dark-700 text-[10px] font-medium inline-flex items-center gap-1 transition"
													>
														<Send className="w-3 h-3" />
														Dispatch
													</button>
												)}
											</td>
										</tr>
									);
								})}
							</tbody>
						</table>
					</div>
				</div>
			</div>

			{/* Slide-Over Detection Evidence Drawer */}
			{activeRecord && (
				<div className="fixed inset-y-0 right-0 z-40 w-full max-w-lg bg-dark-900 border-l border-dark-700 shadow-2xl flex flex-col">
					<div className="p-5 border-b border-dark-800 bg-dark-950 flex items-center justify-between">
						<div>
							<div className="flex items-center gap-2">
								<span className="text-sm font-bold font-mono text-slate-100">
									Event #{activeRecord.event_id}
								</span>
								<span
									className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
										ACTION_BADGE_STYLES[activeRecord.final_action]
									}`}
								>
									{activeRecord.final_action}
								</span>
							</div>
							<p className="text-[11px] text-slate-400 font-mono mt-0.5">
								User: {activeRecord.user_id} • Amount: $
								{(activeRecord.amount ?? 0).toLocaleString()}
							</p>
						</div>
						<button
							type="button"
							onClick={() => setActiveRecord(null)}
							className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800"
						>
							<X className="w-4 h-4" />
						</button>
					</div>

					<div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
						{/* AI Model Score Card */}
						<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2">
							<div className="flex items-center justify-between">
								<span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
									<Cpu className="w-3.5 h-3.5 text-brand-400" />
									AI Model Evaluation
								</span>
								<span className="font-mono text-slate-400">
									Threshold θ = {job?.score_threshold?.toFixed(2) ?? '0.50'}
								</span>
							</div>
							{hasModel ? (
								<div className="flex items-baseline justify-between pt-1">
									<span className="text-2xl font-bold font-mono text-slate-100">
										{activeRecord?.model_score?.toFixed(4) ?? '—'}
									</span>
									<span
										className={`text-xs font-mono ${
											job?.score_threshold != null &&
											activeRecord?.model_score != null &&
											activeRecord.model_score >= job.score_threshold
												? 'text-rose-400'
												: 'text-emerald-400'
										}`}
									>
										{job?.score_threshold != null &&
										activeRecord?.model_score != null &&
										activeRecord.model_score >= job.score_threshold
											? 'Exceeds Threshold (Flagged)'
											: 'Below Threshold'}
									</span>
								</div>
							) : (
								<p className="text-slate-500">
									Job executed in Rule-Only mode (no AI model score).
								</p>
							)}
						</div>

						{/* Triggered Rules Card */}
						<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-3">
							<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
								<ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
								Triggered Business Rules (
								{activeRecord.triggered_rule_details.length})
							</div>

							{activeRecord.triggered_rule_details.length === 0 ? (
								<p className="text-slate-500">
									No active business rules triggered for this transaction.
								</p>
							) : (
								<div className="space-y-2">
									{activeRecord.triggered_rule_details.map((rd) => (
										<div
											key={rd.rule_code}
											className="p-3 rounded-lg bg-dark-900 border border-dark-800 space-y-1.5"
										>
											<div className="flex items-center justify-between">
												<span className="font-mono font-bold text-slate-200">
													{rd.rule_code} — {rd.rule_name}
												</span>
												<span
													className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${
														ACTION_BADGE_STYLES[rd.action]
													}`}
												>
													{rd.action}
												</span>
											</div>
											{rd.matched_clauses && rd.matched_clauses.length > 0 && (
												<div className="text-[11px] font-mono text-amber-300/90 space-y-0.5">
													{rd.matched_clauses.map((clause, idx) => (
														<div key={idx}>• {clause}</div>
													))}
												</div>
											)}
										</div>
									))}
								</div>
							)}
						</div>

						{/* Full Feature Snapshot */}
						<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2.5">
							<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
								Transaction Feature Snapshot
							</div>
							<div className="divide-y divide-dark-800/70 max-h-72 overflow-y-auto pr-1">
								{Object.entries(activeRecord.features || {}).map(([k, v]) => (
									<div
										key={k}
										className="py-1.5 flex items-center justify-between gap-4 font-mono text-[11px]"
									>
										<span className="text-slate-400">{k}</span>
										<span className="text-slate-200 truncate max-w-[220px]">
											{v === null || v === undefined ? 'null' : String(v)}
										</span>
									</div>
								))}
							</div>
						</div>
					</div>

					<div className="p-4 border-t border-dark-800 bg-dark-950 flex items-center justify-between">
						{activeRecord.case_id ? (
							<button
								type="button"
								onClick={() => navigate('/investigation')}
								className="w-full py-2 rounded-lg bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 text-xs font-semibold flex items-center justify-center gap-2"
							>
								<ExternalLink className="w-3.5 h-3.5" />
								Open Dispatched Case in Investigation Queue
							</button>
						) : (
							<button
								type="button"
								onClick={() => {
									setSelectedEventIds([activeRecord.event_id]);
									setDispatchSuccessCount(null);
									setIsDispatchModalOpen(true);
								}}
								className="w-full py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-dark-950 text-xs font-bold flex items-center justify-center gap-2 transition"
							>
								<Send className="w-3.5 h-3.5" />
								Send Transaction to Investigation
							</button>
						)}
					</div>
				</div>
			)}

			{/* Send to Investigation Modal */}
			{isDispatchModalOpen && (
				<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
					<div className="w-full max-w-md rounded-2xl bg-dark-900 border border-dark-700 shadow-2xl overflow-hidden">
						<div className="p-5 border-b border-dark-800 bg-dark-950 flex items-center justify-between">
							<h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
								<Send className="w-4 h-4 text-amber-400" />
								Send to Investigation Queue
							</h3>
							<button
								type="button"
								onClick={() => setIsDispatchModalOpen(false)}
								className="text-slate-400 hover:text-slate-200"
							>
								<X className="w-4 h-4" />
							</button>
						</div>

						<div className="p-5 space-y-4 text-xs">
							{dispatchSuccessCount !== null ? (
								<div className="space-y-4 text-center py-2">
									<CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
									<div>
										<h4 className="text-sm font-bold text-slate-100">
											{dispatchSuccessCount} Case(s) Dispatched
										</h4>
										<p className="text-xs text-slate-400 mt-1">
											Các giao dịch đã được chuyển sang hàng đợi Investigation kèm đầy đủ bằng chứng AI Score và Rules.
										</p>
									</div>
									<div className="flex items-center justify-center gap-2 pt-2">
										<button
											type="button"
											onClick={() => setIsDispatchModalOpen(false)}
											className="px-4 py-2 rounded-lg bg-dark-800 text-slate-200 font-medium"
										>
											Stay on Results
										</button>
										<button
											type="button"
											onClick={() => navigate('/investigation')}
											className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold flex items-center gap-1.5"
										>
											Open Investigation Queue
											<ExternalLink className="w-3.5 h-3.5" />
										</button>
									</div>
								</div>
							) : (
								<>
									<p className="text-slate-300">
										Create{' '}
										<strong className="font-mono text-amber-300">
											{selectedEventIds.length}
										</strong>{' '}
										Investigation Case(s) for manual fraud review.
									</p>
									<div className="space-y-1.5">
										<label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
											Analyst Triage Notes (Optional)
										</label>
										<textarea
											rows={3}
											value={analystNotes}
											onChange={(e) => setAnalystNotes(e.target.value)}
											placeholder="Add context or investigation instructions for the case reviewer..."
											className="w-full p-3 rounded-lg bg-dark-950 border border-dark-700 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
										/>
									</div>
									<div className="flex items-center justify-end gap-2 pt-2">
										<button
											type="button"
											onClick={() => setIsDispatchModalOpen(false)}
											className="px-4 py-2 rounded-lg bg-dark-850 text-slate-300"
										>
											Cancel
										</button>
										<button
											type="button"
											disabled={dispatchMutation.isPending}
											onClick={() =>
												dispatchMutation.mutate(selectedEventIds)
											}
											className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-dark-950 font-bold flex items-center gap-1.5"
										>
											{dispatchMutation.isPending ? (
												<Loader2 className="w-3.5 h-3.5 animate-spin" />
											) : (
												<Send className="w-3.5 h-3.5" />
											)}
											Confirm Dispatch
										</button>
									</div>
								</>
							)}
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
