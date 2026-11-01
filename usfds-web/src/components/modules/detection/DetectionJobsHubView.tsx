import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
	Play,
	Search,
	RefreshCw,
	ShieldAlert,
	CheckCircle2,
	Clock,
	AlertTriangle,
	Database,
	FileSpreadsheet,
	Cpu,
	ShieldCheck,
	ArrowUpRight,
	Layers,
	Briefcase,
} from 'lucide-react';
import { PageHeader } from '../../layout/PageHeader';
import { detectionApi } from '@/api';
import { useProject } from '@/hooks';
import type { DetectionJobResponse, DetectionJobStatusType } from '@/types';

const STATUS_BADGE_MAP: Record<
	DetectionJobStatusType,
	{ label: string; className: string; icon: typeof CheckCircle2 }
> = {
	COMPLETED: {
		label: 'COMPLETED',
		className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
		icon: CheckCircle2,
	},
	RUNNING: {
		label: 'RUNNING',
		className: 'bg-brand-500/10 text-brand-400 border-brand-500/30',
		icon: RefreshCw,
	},
	PENDING: {
		label: 'PENDING',
		className: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
		icon: Clock,
	},
	FAILED: {
		label: 'FAILED',
		className: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
		icon: AlertTriangle,
	},
};

export function DetectionJobsHubView() {
	const navigate = useNavigate();
	const { currentProject } = useProject();
	const projectId = currentProject?.project_id || '';

	const [searchQuery, setSearchQuery] = useState('');
	const [statusFilter, setStatusFilter] = useState<string>('ALL');

	const {
		data: jobsRes,
		isLoading,
		refetch,
		isFetching,
	} = useQuery({
		queryKey: ['detection-jobs', projectId],
		queryFn: () => detectionApi.listJobs({ projectId }),
		enabled: Boolean(projectId),
	});

	const { data: casesRes } = useQuery({
		queryKey: ['investigation-cases', projectId],
		queryFn: () => detectionApi.listCases({ projectId }),
		enabled: Boolean(projectId),
	});

	const jobs: DetectionJobResponse[] = useMemo(() => {
		return jobsRes?.data || [];
	}, [jobsRes]);

	const totalCases = casesRes?.data?.length || 0;

	const filteredJobs = useMemo(() => {
		return jobs.filter((job) => {
			if (statusFilter !== 'ALL' && job.status !== statusFilter) {
				return false;
			}
			if (searchQuery.trim()) {
				const q = searchQuery.trim().toLowerCase();
				const nameMatch = (job.job_name || '').toLowerCase().includes(q);
				const idMatch = job.job_id.toLowerCase().includes(q);
				const inputLabel = (
					job.summary_metrics?.input_label ||
					job.input_path ||
					''
				).toLowerCase();
				const modelLabel = (
					job.summary_metrics?.model_display_name ||
					job.summary_metrics?.model_name ||
					''
				).toLowerCase();
				return (
					nameMatch ||
					idMatch ||
					inputLabel.includes(q) ||
					modelLabel.includes(q)
				);
			}
			return true;
		});
	}, [jobs, statusFilter, searchQuery]);

	const kpis = useMemo(() => {
		const completed = jobs.filter((j) => j.status === 'COMPLETED');
		const totalScanned = completed.reduce((acc, j) => acc + (j.total_records || 0), 0);
		const totalFlagged = completed.reduce((acc, j) => acc + (j.fraud_records || 0), 0);
		const overallFlagRate =
			totalScanned > 0 ? ((totalFlagged / totalScanned) * 100).toFixed(2) : '0.00';

		return {
			totalJobs: jobs.length,
			completedJobs: completed.length,
			totalScanned,
			totalFlagged,
			overallFlagRate,
		};
	}, [jobs]);

	return (
		<div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
			<PageHeader
				title="Detection & Batch Inference Hub"
				subtitle={
					currentProject
						? `Quản lý các phiên quét phát hiện gian lận kết hợp AI Model & Active Rules cho dự án "${currentProject.project_name}"`
						: 'Quản lý các phiên quét phát hiện gian lận theo lô (Hybrid Batch Detection)'
				}
				badge="Detection Engine"
				badgeColor="blue"
				breadcrumbs={[
					{ label: currentProject?.project_name || 'Project' },
					{ label: 'Detection Jobs' },
				]}
				actions={
					<div className="flex items-center gap-2.5">
						<button
							type="button"
							onClick={() => refetch()}
							disabled={isFetching}
							className="px-3 py-2 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs font-medium text-slate-300 flex items-center gap-1.5 transition"
						>
							<RefreshCw
								className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-brand-400' : ''}`}
							/>
							Refresh
						</button>
						<button
							type="button"
							onClick={() => navigate('/detection/new')}
							className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white flex items-center gap-2 shadow-lg shadow-brand-600/20 transition"
						>
							<Play className="w-3.5 h-3.5 fill-current" />
							New Detection Job
						</button>
					</div>
				}
			/>

			<div className="flex-1 overflow-y-auto p-6 space-y-6">
				{/* KPI Summary Row */}
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 flex items-start justify-between">
						<div>
							<p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
								Total Detection Jobs
							</p>
							<p className="text-2xl font-bold font-mono text-slate-100 mt-1">
								{kpis.totalJobs}
							</p>
							<p className="text-[11px] text-slate-500 mt-1">
								<span className="text-emerald-400 font-mono">
									{kpis.completedJobs}
								</span>{' '}
								completed scans
							</p>
						</div>
						<div className="w-9 h-9 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
							<Layers className="w-4 h-4" />
						</div>
					</div>

					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 flex items-start justify-between">
						<div>
							<p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
								Transactions Scanned
							</p>
							<p className="text-2xl font-bold font-mono text-slate-100 mt-1">
								{kpis.totalScanned.toLocaleString()}
							</p>
							<p className="text-[11px] text-slate-500 mt-1">
								RAW artifacts & uploaded files
							</p>
						</div>
						<div className="w-9 h-9 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
							<Database className="w-4 h-4" />
						</div>
					</div>

					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 flex items-start justify-between">
						<div>
							<p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
								Flagged Anomalies
							</p>
							<p className="text-2xl font-bold font-mono text-rose-400 mt-1">
								{kpis.totalFlagged.toLocaleString()}
							</p>
							<p className="text-[11px] text-slate-500 mt-1">
								Flagged rate:{' '}
								<span className="text-amber-400 font-mono">
									{kpis.overallFlagRate}%
								</span>
							</p>
						</div>
						<div className="w-9 h-9 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
							<ShieldAlert className="w-4 h-4" />
						</div>
					</div>

					<div
						onClick={() => navigate('/investigation')}
						className="p-4 rounded-xl bg-dark-900 border border-dark-800 hover:border-amber-500/40 cursor-pointer transition flex items-start justify-between group"
					>
						<div>
							<p className="text-[11px] font-medium uppercase tracking-wider text-slate-400 group-hover:text-amber-300 transition">
								Dispatched Cases
							</p>
							<p className="text-2xl font-bold font-mono text-amber-400 mt-1">
								{totalCases}
							</p>
							<p className="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
								View in Investigation Queue
								<ArrowUpRight className="w-3 h-3 text-amber-400" />
							</p>
						</div>
						<div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
							<Briefcase className="w-4 h-4" />
						</div>
					</div>
				</div>

				{/* Filter & Search Toolbar */}
				<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-dark-900/90 border border-dark-800 p-3.5 rounded-xl">
					<div className="relative flex-1 max-w-md">
						<Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
						<input
							type="text"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							placeholder="Search by job name, input dataset/file, or model..."
							className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-dark-950 border border-dark-700 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500"
						/>
					</div>

					<div className="flex items-center gap-1.5">
						{(['ALL', 'COMPLETED', 'RUNNING', 'FAILED'] as const).map((st) => (
							<button
								key={st}
								type="button"
								onClick={() => setStatusFilter(st)}
								className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${statusFilter === st
									? 'bg-brand-600/20 text-brand-300 border border-brand-500/40'
									: 'bg-dark-950 text-slate-400 border border-dark-800 hover:text-slate-200'
									}`}
							>
								{st}
							</button>
						))}
					</div>
				</div>

				{/* Jobs Table */}
				<div className="rounded-xl bg-dark-900 border border-dark-800 overflow-hidden">
					{isLoading ? (
						<div className="p-12 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
							<RefreshCw className="w-5 h-5 animate-spin text-brand-400" />
							<span>Loading detection jobs...</span>
						</div>
					) : filteredJobs.length === 0 ? (
						<div className="p-12 text-center space-y-3 max-w-md mx-auto">
							<div className="w-11 h-11 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 mx-auto">
								<ShieldCheck className="w-5 h-5" />
							</div>
							<h3 className="text-sm font-semibold text-slate-200">
								No Detection Jobs Found
							</h3>
							<p className="text-xs text-slate-400 leading-relaxed">
								Khởi tạo một phiên quét phát hiện gian lận mới bằng cách chọn tập dữ liệu ở bước RAW hoặc tải trực tiếp tệp giao dịch lên để chấm điểm với AI Model và bộ luật ACTIVE.
							</p>
							<button
								type="button"
								onClick={() => navigate('/detection/new')}
								className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white inline-flex items-center gap-2 transition"
							>
								<Play className="w-3.5 h-3.5 fill-current" />
								Start First Detection Job
							</button>
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-left border-collapse">
								<thead>
									<tr className="border-b border-dark-800 bg-dark-950/60 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
										<th className="py-3 px-4">Detection Job</th>
										<th className="py-3 px-4">Input Source</th>
										<th className="py-3 px-4">Hybrid Engine Config</th>
										<th className="py-3 px-4">Status</th>
										<th className="py-3 px-4 text-right">Records</th>
										<th className="py-3 px-4 text-right">Decision Breakdown</th>
										<th className="py-3 px-4 text-right">Runtime</th>
										<th className="py-3 px-4 text-right">Actions</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800/70 text-xs">
									{filteredJobs.map((job) => {
										const meta = job.summary_metrics || {};
										const statusInfo =
											STATUS_BADGE_MAP[job.status] || STATUS_BADGE_MAP.PENDING;
										const StatusIcon = statusInfo.icon;

										const isArtifactSource =
											meta.input_source_type === 'ARTIFACT' ||
											Boolean(job.target_artifact_id);
										const inputLabel =
											meta.input_label ||
											meta.dataset_name ||
											meta.input_file_name ||
											job.input_path.split(/[/\\]/).pop() ||
											'Batch Input';

										const hasModel = Boolean(job.model_version_id);
										const modelTitle = hasModel
											? `${meta.model_display_name || meta.model_name || 'AI Model'} (v${meta.semver || '1.0.0'})`
											: 'Rule-Only Mode';

										const rejectCount = meta.reject_count ?? 0;
										const reviewCount = meta.review_count ?? 0;
										const allowCount =
											meta.allow_count ??
											Math.max(0, (job.total_records || 0) - (job.fraud_records || 0));
										const flagPct = (((job.fraud_rate ?? 0)) * 100).toFixed(1);

										return (
											<tr
												key={job.job_id}
												onClick={() => navigate(`/detection/jobs/${job.job_id}`)}
												className="hover:bg-dark-850/70 cursor-pointer transition group"
											>
												<td className="py-3.5 px-4">
													<div className="font-semibold text-slate-100 group-hover:text-brand-300 transition">
														{job.job_name || `Job-${job.job_id.slice(0, 8)}`}
													</div>
													<div className="text-[11px] text-slate-500 font-mono mt-0.5">
														{new Date(job.created_at).toLocaleString()}
													</div>
													{job.status === 'FAILED' && job.error_message && (
														<div
															className="text-[11px] text-rose-400 mt-1 max-w-xs truncate"
															title={job.error_message}
														>
															Error: {job.error_message}
														</div>
													)}
												</td>

												<td className="py-3.5 px-4">
													<div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-dark-950 border border-dark-700 text-[11px] text-slate-300">
														{isArtifactSource ? (
															<Database className="w-3 h-3 text-sky-400 shrink-0" />
														) : (
															<FileSpreadsheet className="w-3 h-3 text-emerald-400 shrink-0" />
														)}
														<span className="truncate max-w-[180px]">
															{inputLabel}
														</span>
													</div>
													<div className="text-[10px] text-slate-500 mt-0.5">
														{isArtifactSource
															? 'Project RAW Artifact'
															: 'Direct File Upload'}
													</div>
												</td>

												<td className="py-3.5 px-4">
													<div className="flex items-center gap-1.5 text-slate-200 font-medium">
														<Cpu className="w-3.5 h-3.5 text-brand-400 shrink-0" />
														<span>{modelTitle}</span>
													</div>
													<div className="flex items-center gap-2 mt-1 text-[11px] text-slate-400">
														{hasModel && (
															<span className="font-mono text-slate-300">
																θ = {job.score_threshold != null ? job.score_threshold.toFixed(2) : '0.50'}
															</span>
														)}
														<span
															className={`px-1.5 py-0.2 rounded text-[10px] font-medium ${job.use_rules
																? 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
																: 'bg-dark-800 text-slate-500'
																}`}
														>
															{job.use_rules
																? `Rules: ${meta.active_rules_count ?? 'ACTIVE'}`
																: 'Rules Disabled'}
														</span>
													</div>
												</td>

												<td className="py-3.5 px-4">
													<span
														className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold border ${statusInfo.className}`}
													>
														<StatusIcon className="w-3 h-3" />
														{statusInfo.label}
													</span>
												</td>

												<td className="py-3.5 px-4 text-right font-mono text-slate-200">
													{job.total_records != null ? job.total_records.toLocaleString() : '—'}
												</td>

												<td className="py-3.5 px-4 text-right">
													{job.status === 'FAILED' ? (
														<div className="text-[11px] text-rose-400 font-mono flex items-center justify-end gap-1">
															<AlertTriangle className="w-3.5 h-3.5 shrink-0" />
															<span>Scan Failed</span>
														</div>
													) : (
														<>
															<div className="flex items-center justify-end gap-1.5 font-mono text-[11px]">
																<span
																	title="Immediate Block (REJECT)"
																	className="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30"
																>
																	R: {rejectCount}
																</span>
																<span
																	title="Manual Review (REVIEW)"
																	className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30"
																>
																	V: {reviewCount}
																</span>
																<span
																	title="Clean (ALLOW)"
																	className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
																>
																	A: {allowCount}
																</span>
															</div>
															<div className="text-[10px] text-slate-400 font-mono mt-1">
																Flagged: {job.fraud_records != null ? job.fraud_records.toLocaleString() : 0} ({flagPct}%)
															</div>
														</>
													)}
												</td>

												<td className="py-3.5 px-4 text-right font-mono text-slate-400">
													{job.execution_time_seconds != null
														? `${job.execution_time_seconds.toFixed(2)}s`
														: '—'}
												</td>

												<td
													className="py-3.5 px-4 text-right"
													onClick={(e) => e.stopPropagation()}
												>
													<button
														type="button"
														onClick={() =>
															navigate(`/detection/jobs/${job.job_id}`)
														}
														className="px-2.5 py-1.5 rounded-lg bg-dark-800 hover:bg-brand-600 text-slate-200 hover:text-white text-[11px] font-medium inline-flex items-center gap-1 transition"
													>
														View Results
														<ArrowUpRight className="w-3.5 h-3.5" />
													</button>
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
		</div>
	);
}
