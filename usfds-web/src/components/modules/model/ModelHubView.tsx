import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
	BrainCircuit,
	Play,
	Plus,
	Search,
	CheckCircle2,
	XCircle,
	Clock,
	ChevronDown,
	ChevronRight,
	Rocket,
	Eye,
	Code2,
	Cpu,
	Layers,
	Award,
	RefreshCw,
} from 'lucide-react';
import { trainingApi } from '../../../api/trainingApi';
import { useProject } from '../../../hooks/useProjects';
import type {
	ModelResponse,
	ModelVersionResponse,
	TrainingRunResponse,
} from '../../../types/model';
import { ImportCustomModelModal } from './ImportCustomModelModal';
import { ActivateModelModal } from './ActivateModelModal';

export const ModelHubView: React.FC = () => {
	const navigate = useNavigate();
	const { currentProject } = useProject();
	const projectId = currentProject?.project_id;

	const [activeTab, setActiveTab] = useState<'runs' | 'registry'>('runs');
	const [models, setModels] = useState<ModelResponse[]>([]);
	const [runs, setRuns] = useState<TrainingRunResponse[]>([]);
	const [versionsByModel, setVersionsByModel] = useState<Record<string, ModelVersionResponse[]>>({});
	const [expandedModels, setExpandedModels] = useState<Record<string, boolean>>({});
	const [isLoading, setIsLoading] = useState<boolean>(true);

	// Filters
	const [searchQuery, setSearchQuery] = useState<string>('');
	const [statusFilter, setStatusFilter] = useState<string>('ALL');
	const [modelFilter, setModelFilter] = useState<string>('ALL');

	// Modals
	const [isImportModalOpen, setIsImportModalOpen] = useState<boolean>(false);
	const [activatingVersion, setActivatingVersion] = useState<{
		version: ModelVersionResponse;
		model?: ModelResponse | null;
	} | null>(null);

	const fetchHubData = useCallback(async () => {
		setIsLoading(true);
		try {
			const [modelsRes, runsRes] = await Promise.all([
				trainingApi.listModels(projectId),
				trainingApi.listTrainingRuns({ projectId }),
			]);
			const loadedModels = modelsRes.success && modelsRes.data ? modelsRes.data : [];
			const loadedRuns = runsRes.success && runsRes.data ? runsRes.data : [];
			setModels(loadedModels);
			setRuns(loadedRuns);

			// Load versions for all models so we can show active badges and version counts
			const versionEntries = await Promise.all(
				loadedModels.map(async (m) => {
					const vRes = await trainingApi.listModelVersions(m.model_id);
					return [m.model_id, vRes.success && vRes.data ? vRes.data : []] as const;
				})
			);
			const versionMap: Record<string, ModelVersionResponse[]> = {};
			for (const [mId, vList] of versionEntries) {
				versionMap[mId] = vList;
			}
			setVersionsByModel(versionMap);
		} finally {
			setIsLoading(false);
		}
	}, [projectId]);

	useEffect(() => {
		fetchHubData();
	}, [fetchHubData]);

	const modelMap = useMemo(() => {
		const map: Record<string, ModelResponse> = {};
		for (const m of models) {
			map[m.model_id] = m;
		}
		return map;
	}, [models]);

	const versionByIdMap = useMemo(() => {
		const map: Record<string, ModelVersionResponse> = {};
		for (const list of Object.values(versionsByModel)) {
			for (const v of list) {
				map[v.version_id] = v;
			}
		}
		return map;
	}, [versionsByModel]);

	// KPI Computations
	const kpiStats = useMemo(() => {
		const totalRuns = runs.length;
		const completedRuns = runs.filter((r) => r.status === 'COMPLETED');
		let bestPrAuc: number | null = null;
		let bestRunName = '—';

		for (const r of completedRuns) {
			const prAuc = r.custom_metrics?.pr_auc ?? null;
			if (typeof prAuc === 'number' && (bestPrAuc === null || prAuc > bestPrAuc)) {
				bestPrAuc = prAuc;
				bestRunName = r.run_name;
			}
		}

		let approvedCount = 0;
		for (const list of Object.values(versionsByModel)) {
			for (const v of list) {
				if (v.status === 'APPROVED') {
					approvedCount += 1;
				}
			}
		}

		return {
			totalRuns,
			completedCount: completedRuns.length,
			registeredModelsCount: models.length,
			approvedCount,
			bestPrAuc,
			bestRunName,
		};
	}, [runs, models, versionsByModel]);

	const filteredRuns = useMemo(() => {
		return runs.filter((run) => {
			if (statusFilter !== 'ALL' && run.status !== statusFilter) {
				return false;
			}
			if (modelFilter !== 'ALL' && run.model_id !== modelFilter) {
				return false;
			}
			if (searchQuery.trim()) {
				const q = searchQuery.toLowerCase();
				const modelName = run.model_id ? modelMap[run.model_id]?.display_name || modelMap[run.model_id]?.model_name || '' : '';
				return (
					run.run_name.toLowerCase().includes(q) ||
					modelName.toLowerCase().includes(q) ||
					run.run_id.toLowerCase().includes(q)
				);
			}
			return true;
		});
	}, [runs, statusFilter, modelFilter, searchQuery, modelMap]);

	const filteredModels = useMemo(() => {
		if (!searchQuery.trim()) {
			return models;
		}
		const q = searchQuery.toLowerCase();
		return models.filter(
			(m) =>
				m.model_name.toLowerCase().includes(q) ||
				(m.display_name || '').toLowerCase().includes(q) ||
				(m.description || '').toLowerCase().includes(q)
		);
	}, [models, searchQuery]);

	const toggleExpandModel = (modelId: string) => {
		setExpandedModels((prev) => ({
			...prev,
			[modelId]: !prev[modelId],
		}));
	};

	const renderRunStatusBadge = (status: string) => {
		switch (status) {
			case 'COMPLETED':
				return (
					<span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
						<CheckCircle2 className="w-3 h-3" />
						COMPLETED
					</span>
				);
			case 'FAILED':
				return (
					<span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
						<XCircle className="w-3 h-3" />
						FAILED
					</span>
				);
			default:
				return (
					<span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
						<Clock className="w-3 h-3" />
						{status}
					</span>
				);
		}
	};

	const renderVersionStatusBadge = (status: string) => {
		if (status === 'APPROVED') {
			return (
				<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
					<CheckCircle2 className="w-3 h-3" />
					APPROVED
				</span>
			);
		}
		return (
			<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-brand-500/15 text-brand-400 border border-brand-500/30">
				{status}
			</span>
		);
	};

	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden bg-dark-950">
			{/* Top Header */}
			<div className="px-6 py-4 border-b border-dark-800 bg-dark-900/60 flex flex-wrap items-center justify-between gap-4">
				<div className="flex items-center gap-3">
					<div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/30 flex items-center justify-center text-brand-400">
						<BrainCircuit className="w-5 h-5" />
					</div>
					<div>
						<div className="flex items-center gap-2">
							<h1 className="text-base font-bold text-slate-100">
								Model Hub — Registry & Training Runs
							</h1>
						</div>
						<p className="text-xs text-slate-400 mt-0.5">
							Quản lý danh mục mô hình học máy (`BUILTIN` & `SCRIPT`), khởi chạy huấn luyện và kích hoạt phiên bản mô hình
						</p>
					</div>
				</div>

				<div className="flex items-center gap-2.5">
					<button
						type="button"
						onClick={fetchHubData}
						title="Làm mới dữ liệu"
						className="p-2 rounded-xl bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-300 transition"
					>
						<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
					</button>
					<button
						type="button"
						onClick={() => setIsImportModalOpen(true)}
						className="px-3.5 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 border border-dark-700 text-xs font-semibold text-slate-200 transition flex items-center gap-2"
					>
						<Code2 className="w-4 h-4 text-brand-400" />
						<span>Import Custom Model</span>
					</button>
					<button
						type="button"
						onClick={() => navigate('/models/train')}
						className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2"
					>
						<Plus className="w-4 h-4" />
						<span>New Training Run</span>
					</button>
				</div>
			</div>

			{/* Main Content */}
			<div className="flex-1 overflow-y-auto p-6 space-y-5">
				{/* KPI Summary Cards */}
				<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 flex items-center justify-between">
						<div>
							<div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
								Training Runs
							</div>
							<div className="text-xl font-bold font-mono text-slate-100 mt-1">
								{kpiStats.totalRuns}
							</div>
							<div className="text-[11px] text-emerald-400 mt-0.5 font-mono">
								{kpiStats.completedCount} completed
							</div>
						</div>
						<div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
							<Play className="w-5 h-5" />
						</div>
					</div>

					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 flex items-center justify-between">
						<div>
							<div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
								Registered Models
							</div>
							<div className="text-xl font-bold font-mono text-slate-100 mt-1">
								{kpiStats.registeredModelsCount}
							</div>
							<div className="text-[11px] text-slate-400 mt-0.5">
								Built-in & Custom Plugins
							</div>
						</div>
						<div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
							<Cpu className="w-5 h-5" />
						</div>
					</div>

					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 flex items-center justify-between">
						<div>
							<div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
								Active Versions (Approved)
							</div>
							<div className="text-xl font-bold font-mono text-emerald-400 mt-1">
								{kpiStats.approvedCount}
							</div>
							<div className="text-[11px] text-slate-400 mt-0.5">
								Ready for Detection
							</div>
						</div>
						<div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
							<Layers className="w-5 h-5" />
						</div>
					</div>

					<div className="p-4 rounded-xl bg-dark-900 border border-dark-800 flex items-center justify-between">
						<div>
							<div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
								Best PR-AUC
							</div>
							<div className="text-xl font-bold font-mono text-amber-400 mt-1">
								{kpiStats.bestPrAuc !== null ? kpiStats.bestPrAuc.toFixed(4) : '—'}
							</div>
							<div className="text-[11px] text-slate-400 mt-0.5 truncate max-w-[160px]">
								{kpiStats.bestRunName}
							</div>
						</div>
						<div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
							<Award className="w-5 h-5" />
						</div>
					</div>
				</div>

				{/* Tabs & Filter Bar */}
				<div className="flex flex-wrap items-center justify-between gap-3 border-b border-dark-800 pb-3">
					<div className="flex items-center gap-2">
						<button
							type="button"
							onClick={() => setActiveTab('runs')}
							className={`px-4 py-2 rounded-xl text-xs font-semibold transition ${activeTab === 'runs'
								? 'bg-brand-500 text-white shadow-glow-blue'
								: 'bg-dark-900 text-slate-400 hover:text-slate-200 border border-dark-800'
								}`}
						>
							Training Runs ({runs.length})
						</button>
						<button
							type="button"
							onClick={() => setActiveTab('registry')}
							className={`px-4 py-2 rounded-xl text-xs font-semibold transition ${activeTab === 'registry'
								? 'bg-brand-500 text-white shadow-glow-blue'
								: 'bg-dark-900 text-slate-400 hover:text-slate-200 border border-dark-800'
								}`}
						>
							Model Registry ({models.length})
						</button>
					</div>

					<div className="flex flex-wrap items-center gap-2.5">
						<div className="relative">
							<Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
							<input
								type="text"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
								placeholder="Tìm tên lần chạy hoặc mô hình..."
								className="pl-8 pr-3 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-slate-100 focus:border-brand-500 focus:outline-none w-56"
							/>
						</div>

						{activeTab === 'runs' && (
							<>
								<select
									value={statusFilter}
									onChange={(e) => setStatusFilter(e.target.value)}
									aria-label="Lọc theo trạng thái"
									className="px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-slate-200 focus:border-brand-500 focus:outline-none"
								>
									<option value="ALL">Status: All</option>
									<option value="COMPLETED">COMPLETED</option>
									<option value="FAILED">FAILED</option>
									<option value="RUNNING">RUNNING</option>
								</select>

								<select
									value={modelFilter}
									onChange={(e) => setModelFilter(e.target.value)}
									aria-label="Lọc theo mô hình"
									className="px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-slate-200 focus:border-brand-500 focus:outline-none"
								>
									<option value="ALL">Model: All</option>
									{models.map((m) => (
										<option key={m.model_id} value={m.model_id}>
											{m.display_name || m.model_name}
										</option>
									))}
								</select>
							</>
						)}
					</div>
				</div>

				{/* Tab 1: Training Runs Table */}
				{activeTab === 'runs' ? (
					<div className="bg-dark-900 border border-dark-800 rounded-xl overflow-hidden">
						<div className="overflow-x-auto">
							<table className="w-full text-left border-collapse">
								<caption className="sr-only">Danh sách các lần chạy huấn luyện mô hình</caption>
								<thead>
									<tr className="border-b border-dark-800 bg-dark-950/60 text-[11px] font-bold uppercase tracking-wider text-slate-400">
										<th scope="col" className="py-3 px-4">Run Name</th>
										<th scope="col" className="py-3 px-4">Algorithm / Model</th>
										<th scope="col" className="py-3 px-4">Version</th>
										<th scope="col" className="py-3 px-4">Status</th>
										<th scope="col" className="py-3 px-4 text-right">PR-AUC</th>
										<th scope="col" className="py-3 px-4 text-right">ROC-AUC</th>
										<th scope="col" className="py-3 px-4 text-right">F1-Score</th>
										<th scope="col" className="py-3 px-4 text-right">Duration</th>
										<th scope="col" className="py-3 px-4 text-right">Actions</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800/70 text-xs">
									{filteredRuns.length === 0 ? (
										<tr>
											<td colSpan={9} className="py-12 text-center text-slate-400">
												Chưa có lần chạy huấn luyện nào khớp bộ lọc. Nhấn{' '}
												<button
													type="button"
													onClick={() => navigate('/models/train')}
													className="text-brand-400 font-semibold hover:underline"
												>
													+ New Training Run
												</button>{' '}
												để bắt đầu.
											</td>
										</tr>
									) : (
										filteredRuns.map((run) => {
											const modelObj = run.model_id ? modelMap[run.model_id] : undefined;
											const versionObj = run.version_id ? versionByIdMap[run.version_id] : undefined;
											const prAuc = run.custom_metrics?.pr_auc;
											const rocAuc = run.custom_metrics?.roc_auc;

											return (
												<tr
													key={run.run_id}
													className="hover:bg-white/[0.02] transition"
												>
													<td className="py-3 px-4">
														<button
															type="button"
															onClick={() => navigate(`/models/runs/${run.run_id}`)}
															className="font-semibold text-slate-100 hover:text-brand-400 transition text-left"
														>
															{run.run_name}
														</button>
														<div className="text-[10px] font-mono text-slate-500 mt-0.5">
															{new Date(run.created_at).toLocaleString('vi-VN')}
														</div>
													</td>
													<td className="py-3 px-4">
														<div className="font-medium text-slate-200">
															{modelObj?.display_name || modelObj?.model_name || 'Unknown Model'}
														</div>
														{modelObj && (
															<span className="text-[10px] font-mono text-slate-400">
																{modelObj.execution_type}
															</span>
														)}
													</td>
													<td className="py-3 px-4 font-mono">
														{versionObj ? (
															<div className="flex items-center gap-1.5">
																<span className="text-slate-200">v{versionObj.semver}</span>
																{renderVersionStatusBadge(versionObj.status)}
															</div>
														) : (
															<span className="text-slate-500">—</span>
														)}
													</td>
													<td className="py-3 px-4">{renderRunStatusBadge(run.status)}</td>
													<td className="py-3 px-4 text-right font-mono text-slate-100">
														{typeof prAuc === 'number' ? prAuc.toFixed(4) : '—'}
													</td>
													<td className="py-3 px-4 text-right font-mono text-slate-200">
														{typeof rocAuc === 'number' ? rocAuc.toFixed(4) : '—'}
													</td>
													<td className="py-3 px-4 text-right font-mono text-slate-200">
														{typeof run.f1_score === 'number' ? run.f1_score.toFixed(4) : '—'}
													</td>
													<td className="py-3 px-4 text-right font-mono text-slate-400">
														{typeof run.duration_seconds === 'number'
															? `${run.duration_seconds}s`
															: '—'}
													</td>
													<td className="py-3 px-4 text-right">
														<div className="inline-flex items-center gap-1.5">
															<button
																type="button"
																onClick={() => navigate(`/models/runs/${run.run_id}`)}
																className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-[11px] font-medium text-slate-200 transition inline-flex items-center gap-1"
															>
																<Eye className="w-3.5 h-3.5 text-brand-400" />
																<span>View</span>
															</button>
															{versionObj && versionObj.status !== 'APPROVED' && (
																<button
																	type="button"
																	onClick={() =>
																		setActivatingVersion({
																			version: versionObj,
																			model: modelObj,
																		})
																	}
																	className="px-2.5 py-1 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 text-[11px] font-semibold text-emerald-300 transition inline-flex items-center gap-1"
																>
																	<Rocket className="w-3 h-3" />
																	<span>Activate</span>
																</button>
															)}
														</div>
													</td>
												</tr>
											);
										})
									)}
								</tbody>
							</table>
						</div>
					</div>
				) : (
					/* Tab 2: Model Registry */
					<div className="space-y-3">
						{filteredModels.map((model) => {
							const versions = versionsByModel[model.model_id] || [];
							const isExpanded = Boolean(expandedModels[model.model_id]);
							const approvedCount = versions.filter((v) => v.status === 'APPROVED').length;

							return (
								<div
									key={model.model_id}
									className="bg-dark-900 border border-dark-800 rounded-xl overflow-hidden"
								>
									<div
										onClick={() => toggleExpandModel(model.model_id)}
										className="p-4 flex flex-wrap items-center justify-between gap-4 cursor-pointer hover:bg-white/[0.02] transition"
									>
										<div className="flex items-start gap-3">
											<button
												type="button"
												aria-label="Mở rộng danh sách phiên bản"
												className="mt-0.5 text-slate-400 hover:text-slate-200"
											>
												{isExpanded ? (
													<ChevronDown className="w-4 h-4 text-brand-400" />
												) : (
													<ChevronRight className="w-4 h-4" />
												)}
											</button>
											<div>
												<div className="flex items-center gap-2">
													<span className="text-sm font-bold text-slate-100">
														{model.display_name || model.model_name}
													</span>
													<span className="text-xs font-mono text-slate-400">
														({model.model_name})
													</span>
													<span
														className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${model.execution_type === 'BUILTIN'
															? 'bg-brand-500/15 text-brand-400 border border-brand-500/30'
															: 'bg-purple-500/15 text-purple-400 border border-purple-500/30'
															}`}
													>
														{model.execution_type}
													</span>
													{approvedCount > 0 && (
														<span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
															{approvedCount} APPROVED
														</span>
													)}
												</div>
												<p className="text-xs text-slate-400 mt-1">
													{model.description || 'Không có mô tả'}
												</p>
											</div>
										</div>

										<div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
											<span className="text-xs font-mono text-slate-400">
												{versions.length} versions
											</span>
											<button
												type="button"
												onClick={() => navigate(`/models/train?modelId=${model.model_id}`)}
												className="px-3 py-1.5 rounded-lg bg-brand-500/15 hover:bg-brand-500/25 border border-brand-500/30 text-xs font-semibold text-brand-300 transition flex items-center gap-1.5"
											>
												<Play className="w-3.5 h-3.5" />
												<span>Train Model</span>
											</button>
										</div>
									</div>

									{isExpanded && (
										<div className="border-t border-dark-800 bg-dark-950/60 p-4">
											{versions.length === 0 ? (
												<p className="text-xs text-slate-500 text-center py-4">
													Mô hình này chưa có phiên bản (`ModelVersion`) nào được huấn luyện.
												</p>
											) : (
												<div className="overflow-x-auto">
													<table className="w-full text-left border-collapse text-xs">
														<thead>
															<tr className="border-b border-dark-800 text-[10px] font-bold uppercase tracking-wider text-slate-400">
																<th scope="col" className="py-2 px-3">SemVer</th>
																<th scope="col" className="py-2 px-3">Status</th>
																<th scope="col" className="py-2 px-3">Framework</th>
																<th scope="col" className="py-2 px-3">Threshold</th>
																<th scope="col" className="py-2 px-3">SHA-256 Checksum</th>
																<th scope="col" className="py-2 px-3">Registered At</th>
																<th scope="col" className="py-2 px-3 text-right">Actions</th>
															</tr>
														</thead>
														<tbody className="divide-y divide-dark-800/60">
															{versions.map((ver) => (
																<tr key={ver.version_id} className="hover:bg-white/[0.02]">
																	<td className="py-2.5 px-3 font-mono font-bold text-slate-100">
																		v{ver.semver}
																	</td>
																	<td className="py-2.5 px-3">
																		{renderVersionStatusBadge(ver.status)}
																	</td>
																	<td className="py-2.5 px-3 font-mono text-slate-300">
																		{ver.framework || 'scikit-learn'}
																	</td>
																	<td className="py-2.5 px-3 font-mono text-amber-400">
																		{Number(ver.decision_threshold).toFixed(4)}
																	</td>
																	<td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
																		{ver.checksum_sha256
																			? `${ver.checksum_sha256.slice(0, 12)}...`
																			: '—'}
																	</td>
																	<td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
																		{new Date(ver.registered_at).toLocaleString('vi-VN')}
																	</td>
																	<td className="py-2.5 px-3 text-right">
																		<div className="inline-flex items-center gap-1.5">
																			{ver.run_id && (
																				<button
																					type="button"
																					onClick={() => navigate(`/models/runs/${ver.run_id}`)}
																					className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-[11px] text-slate-200 transition"
																				>
																					View Run
																				</button>
																			)}
																			<button
																				type="button"
																				onClick={() =>
																					setActivatingVersion({
																						version: ver,
																						model,
																					})
																				}
																				className="px-2.5 py-1 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 text-[11px] font-semibold text-emerald-300 transition inline-flex items-center gap-1"
																			>
																				<Rocket className="w-3 h-3" />
																				<span>
																					{ver.status === 'APPROVED'
																						? 'Update Threshold'
																						: 'Activate'}
																				</span>
																			</button>
																		</div>
																	</td>
																</tr>
															))}
														</tbody>
													</table>
												</div>
											)}
										</div>
									)}
								</div>
							);
						})}
					</div>
				)}
			</div>

			{/* Import Custom Model Plugin Modal (SUC-17) */}
			<ImportCustomModelModal
				isOpen={isImportModalOpen}
				projectId={projectId}
				onClose={() => setIsImportModalOpen(false)}
				onSuccess={() => {
					fetchHubData();
				}}
			/>

			{/* Activate Model Version Modal (SUC-10) */}
			<ActivateModelModal
				isOpen={Boolean(activatingVersion)}
				version={activatingVersion?.version || null}
				model={activatingVersion?.model}
				onClose={() => setActivatingVersion(null)}
				onSuccess={() => {
					fetchHubData();
				}}
			/>
		</div>
	);
};
