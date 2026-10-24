import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
	Layers,
	Plus,
	RefreshCw,
	Search,
	Lock,
	Unlock,
	CheckCircle2,
	Archive,
	ArchiveRestore,
	Edit3,
	Trash2,
	Database,
	ShieldCheck,
	Terminal,
	ShieldAlert,
	Eye,
	ArrowRight,
} from 'lucide-react';
import { useProject } from '../../../hooks/useProjects';
import type { ProjectResponse, ProjectStatus } from '../../../types/project';
import { ProjectFormModal } from './ProjectFormModal';
import { ProjectSchemaDrawer } from './ProjectSchemaDrawer';

type StatusTab = 'ALL' | ProjectStatus;

export const ProjectManagementView: React.FC = () => {
	const navigate = useNavigate();
	const {
		projects,
		currentProject,
		isLoading,
		error,
		openCreateModal,
		selectProject,
		refetchProjects,
		createProject,
		updateProject,
		resetProjectSchema,
		deleteProject,
	} = useProject();

	const [statusTab, setStatusTab] = useState<StatusTab>('ALL');
	const [searchQuery, setSearchQuery] = useState('');
	const [editingProject, setEditingProject] = useState<ProjectResponse | null>(null);
	const [inspectingProjectId, setInspectingProjectId] = useState<string | null>(null);
	const [actionError, setActionError] = useState<string | null>(null);

	const inspectingProject = useMemo(() => {
		if (!inspectingProjectId) {
			return null;
		}
		return projects.find((p) => p.project_id === inspectingProjectId) || null;
	}, [projects, inspectingProjectId]);

	const metrics = useMemo(() => {
		const totalCount = projects.length;
		const activeCount = projects.filter((p) => p.status === 'ACTIVE').length;
		const archivedCount = projects.filter((p) => p.status === 'ARCHIVED').length;
		const schemaLockedCount = projects.filter((p) => p.is_schema_locked).length;
		return { totalCount, activeCount, archivedCount, schemaLockedCount };
	}, [projects]);

	const filteredProjects = useMemo(() => {
		const q = searchQuery.trim().toLowerCase();
		return projects.filter((p) => {
			if (statusTab !== 'ALL' && p.status !== statusTab) {
				return false;
			}
			if (!q) {
				return true;
			}
			return (
				p.project_name.toLowerCase().includes(q) ||
				(p.description && p.description.toLowerCase().includes(q)) ||
				p.project_id.toLowerCase().includes(q)
			);
		});
	}, [projects, statusTab, searchQuery]);

	const handleEnterWorkspace = (proj: ProjectResponse) => {
		selectProject(proj);
		navigate('/datasets');
	};

	const handleToggleArchive = async (proj: ProjectResponse, e: React.MouseEvent) => {
		e.stopPropagation();
		const nextStatus: ProjectStatus = proj.status === 'ACTIVE' ? 'ARCHIVED' : 'ACTIVE';
		const actionLabel = nextStatus === 'ARCHIVED' ? 'lưu trữ (Archive)' : 'khôi phục (Restore)';
		if (!window.confirm(`Bạn có chắc muốn ${actionLabel} dự án "${proj.project_name}"?`)) {
			return;
		}
		setActionError(null);
		try {
			await updateProject(proj.project_id, { status: nextStatus });
		} catch (err: any) {
			setActionError(err?.message || `Không thể ${actionLabel} dự án.`);
		}
	};

	const handleDeleteProject = async (proj: ProjectResponse, e: React.MouseEvent) => {
		e.stopPropagation();
		if (
			!window.confirm(
				`Xác nhận xóa vĩnh viễn dự án "${proj.project_name}"?\nToàn bộ tài nguyên thuộc dự án (${proj.datasets_count} Datasets, ${proj.rules_count} Rules) sẽ bị xóa dây chuyền (BR-PM-08).`
			)
		) {
			return;
		}
		setActionError(null);
		try {
			await deleteProject(proj.project_id);
			if (inspectingProjectId === proj.project_id) {
				setInspectingProjectId(null);
			}
		} catch (err: any) {
			setActionError(err?.message || 'Không thể xóa dự án.');
		}
	};

	return (
		<div className="h-screen w-screen overflow-hidden flex flex-col bg-dark-950 text-slate-100 font-sans">
			{/* Standalone Portal Topbar (No Left Sidebar) */}
			<header className="h-[56px] min-h-[56px] bg-dark-900 border-b border-dark-700/80 px-6 flex items-center justify-between select-none">
				<div className="flex items-center gap-3">
					<div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400 shadow-glow-blue">
						<ShieldAlert className="w-5 h-5 text-brand-400" />
					</div>
					<div className="flex items-center gap-2.5">
						<span className="font-bold tracking-wider text-sm text-slate-100 font-mono">
							USFDS
						</span>
						<span className="text-dark-700">|</span>
						<span className="text-xs font-medium text-slate-400">
							Project Management Portal
						</span>
					</div>
				</div>

				<div className="flex items-center gap-3">
					<button
						type="button"
						onClick={() => refetchProjects()}
						disabled={isLoading}
						className="p-2 rounded-xl bg-dark-850 hover:bg-dark-800 border border-dark-700 text-slate-400 hover:text-slate-200 transition"
						title="Làm mới danh sách dự án"
						aria-label="Làm mới danh sách dự án"
					>
						<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-brand-400' : ''}`} />
					</button>
					<button
						type="button"
						onClick={openCreateModal}
						className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2"
					>
						<Plus className="w-4 h-4" />
						<span>New Project</span>
					</button>
				</div>
			</header>

			{/* Main Standalone Portal Content */}
			<div className="flex-1 overflow-y-auto p-6 md:p-8">
				<div className="max-w-7xl mx-auto space-y-6">
					{/* Portal Title Banner */}
					<div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
						<div>
							<h1 className="text-xl font-bold text-slate-100 tracking-tight">
								Fraud Detection Projects
							</h1>
							<p className="text-xs text-slate-400 mt-1">
								Chọn một dự án bên dưới để vào không gian làm việc (Data Management, Model
								Management, Rule Engine, Detection & Investigation).
							</p>
						</div>
					</div>

					{(error || actionError) && (
						<div
							role="alert"
							className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center justify-between gap-3"
						>
							<div className="flex items-center gap-2.5">
								<ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
								<span>{actionError || error}</span>
							</div>
							{actionError && (
								<button
									type="button"
									onClick={() => setActionError(null)}
									className="text-[11px] text-rose-300 hover:text-white underline"
								>
									Đóng
								</button>
							)}
						</div>
					)}

					{/* KPI Summary Cards */}
					<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
						<div className="p-4 rounded-2xl bg-dark-900 border border-dark-800 space-y-1.5">
							<div className="flex items-center justify-between text-slate-400">
								<span className="text-[11px] font-bold uppercase tracking-wider">
									Total Projects
								</span>
								<Layers className="w-4 h-4 text-brand-400" />
							</div>
							<div className="flex items-baseline gap-2">
								<span className="text-2xl font-black text-slate-100 font-mono">
									{metrics.totalCount}
								</span>
								<span className="text-xs text-slate-400">Projects</span>
							</div>
						</div>

						<div className="p-4 rounded-2xl bg-dark-900 border border-dark-800 space-y-1.5">
							<div className="flex items-center justify-between text-slate-400">
								<span className="text-[11px] font-bold uppercase tracking-wider">
									Last Active Project
								</span>
								<CheckCircle2 className="w-4 h-4 text-emerald-400" />
							</div>
							<div className="text-sm font-bold text-slate-100 truncate">
								{currentProject ? currentProject.project_name : 'Chưa chọn dự án'}
							</div>
							<div className="text-[10px] text-slate-500 font-mono truncate">
								{currentProject ? currentProject.project_id : '—'}
							</div>
						</div>

						<div className="p-4 rounded-2xl bg-dark-900 border border-dark-800 space-y-1.5">
							<div className="flex items-center justify-between text-slate-400">
								<span className="text-[11px] font-bold uppercase tracking-wider">
									RAW Schema Locked
								</span>
								<Lock className="w-4 h-4 text-emerald-400" />
							</div>
							<div className="flex items-baseline gap-2">
								<span className="text-2xl font-black text-emerald-400 font-mono">
									{metrics.schemaLockedCount}
								</span>
								<span className="text-xs text-slate-400">/ {metrics.totalCount} Locked</span>
							</div>
						</div>

						<div className="p-4 rounded-2xl bg-dark-900 border border-dark-800 space-y-1.5">
							<div className="flex items-center justify-between text-slate-400">
								<span className="text-[11px] font-bold uppercase tracking-wider">
									Active / Archived
								</span>
								<Archive className="w-4 h-4 text-amber-400" />
							</div>
							<div className="flex items-baseline gap-2 font-mono">
								<span className="text-2xl font-black text-slate-100">{metrics.activeCount}</span>
								<span className="text-xs text-emerald-400">Active</span>
								<span className="text-slate-600">•</span>
								<span className="text-sm font-bold text-amber-400">{metrics.archivedCount}</span>
								<span className="text-xs text-slate-400">Archived</span>
							</div>
						</div>
					</div>

					{/* Filter & Search Bar */}
					<div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
						<div className="flex items-center gap-1.5 p-1 rounded-xl bg-dark-900 border border-dark-800">
							<button
								type="button"
								onClick={() => setStatusTab('ALL')}
								className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
									statusTab === 'ALL'
										? 'bg-brand-500 text-white font-bold shadow-glow-blue'
										: 'text-slate-400 hover:text-slate-200'
								}`}
							>
								All ({metrics.totalCount})
							</button>
							<button
								type="button"
								onClick={() => setStatusTab('ACTIVE')}
								className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
									statusTab === 'ACTIVE'
										? 'bg-emerald-600 text-white font-bold'
										: 'text-slate-400 hover:text-slate-200'
								}`}
							>
								Active ({metrics.activeCount})
							</button>
							<button
								type="button"
								onClick={() => setStatusTab('ARCHIVED')}
								className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
									statusTab === 'ARCHIVED'
										? 'bg-amber-600 text-white font-bold'
										: 'text-slate-400 hover:text-slate-200'
								}`}
							>
								Archived ({metrics.archivedCount})
							</button>
						</div>

						<div className="relative w-full md:w-80">
							<Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-3" />
							<input
								type="search"
								aria-label="Tìm kiếm dự án"
								placeholder="Tìm theo tên dự án, mô tả hoặc ID..."
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
								className="w-full pl-9 pr-3 py-2 bg-dark-900 border border-dark-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500"
							/>
						</div>
					</div>

					{/* Projects Catalog Table */}
					<div className="border border-dark-800 rounded-2xl overflow-hidden bg-dark-900/60 shadow-xl">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<caption className="sr-only">Danh sách dự án phát hiện gian lận</caption>
								<thead>
									<tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
										<th scope="col" className="py-3.5 px-4 font-semibold">
											Dự án (Project)
										</th>
										<th scope="col" className="py-3.5 px-4 font-semibold">
											Trạng thái
										</th>
										<th scope="col" className="py-3.5 px-4 font-semibold">
											RAW Schema Contract
										</th>
										<th scope="col" className="py-3.5 px-4 font-semibold">
											Tài nguyên (Resources)
										</th>
										<th scope="col" className="py-3.5 px-4 font-semibold">
											Cập nhật
										</th>
										<th scope="col" className="py-3.5 px-4 font-semibold text-right">
											Thao tác
										</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-850">
									{filteredProjects.length === 0 ? (
										<tr>
											<td colSpan={6} className="py-12 text-center text-slate-400 space-y-3">
												<div className="text-xs">
													{projects.length === 0
														? 'Chưa có dự án nào trong hệ thống. Hãy khởi tạo dự án đầu tiên để bắt đầu.'
														: 'Không tìm thấy dự án nào khớp với bộ lọc hiện tại.'}
												</div>
												{projects.length === 0 && (
													<button
														type="button"
														onClick={openCreateModal}
														className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold inline-flex items-center gap-2"
													>
														<Plus className="w-4 h-4" />
														<span>Tạo Dự án Đầu tiên</span>
													</button>
												)}
											</td>
										</tr>
									) : (
										filteredProjects.map((proj) => {
											const isCurrent = currentProject?.project_id === proj.project_id;
											const columnCount = Object.keys(proj.raw_schema?.columns || {}).length;

											return (
												<tr
													key={proj.project_id}
													onClick={() => handleEnterWorkspace(proj)}
													className={`hover:bg-dark-850/70 transition cursor-pointer group ${
														isCurrent ? 'bg-brand-500/5' : ''
													}`}
												>
													{/* Project Name & Description */}
													<td className="py-3.5 px-4">
														<div className="space-y-0.5">
															<div className="flex items-center gap-2">
																<span className="font-bold text-slate-100 group-hover:text-brand-300 transition">
																	{proj.project_name}
																</span>
																{isCurrent && (
																	<span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-brand-500/20 text-brand-300 border border-brand-500/40">
																		RECENT
																	</span>
																)}
															</div>
															<div className="text-[11px] text-slate-400 line-clamp-1">
																{proj.description || 'Chưa có mô tả'}
															</div>
															<div className="text-[10px] text-slate-500 font-mono">
																{proj.project_id}
															</div>
														</div>
													</td>

													{/* Status Badge (Dual-Encoded) */}
													<td className="py-3.5 px-4 font-mono">
														{proj.status === 'ACTIVE' ? (
															<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
																<CheckCircle2 className="w-3 h-3 text-emerald-400" />
																ACTIVE
															</span>
														) : (
															<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
																<Archive className="w-3 h-3 text-amber-400" />
																ARCHIVED
															</span>
														)}
													</td>

													{/* RAW Schema Contract */}
													<td
														className="py-3.5 px-4 font-mono"
														onClick={(e) => e.stopPropagation()}
													>
														<button
															type="button"
															onClick={() => setInspectingProjectId(proj.project_id)}
															className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold border transition ${
																proj.is_schema_locked
																	? 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
																	: 'bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border-amber-500/30'
															}`}
															title="Xem chi tiết hoặc đặt lại RAW Schema"
														>
															{proj.is_schema_locked ? (
																<>
																	<Lock className="w-3 h-3 text-emerald-400" />
																	<span>LOCKED ({columnCount} cols)</span>
																</>
															) : (
																<>
																	<Unlock className="w-3 h-3 text-amber-400" />
																	<span>UNLOCKED</span>
																</>
															)}
														</button>
													</td>

													{/* Resource Counts */}
													<td className="py-3.5 px-4 font-mono">
														<div className="flex items-center gap-3 text-[11px] text-slate-300">
															<span
																className="inline-flex items-center gap-1"
																title="Datasets"
															>
																<Database className="w-3.5 h-3.5 text-brand-400" />
																{proj.datasets_count}
															</span>
															<span
																className="inline-flex items-center gap-1"
																title="Rules"
															>
																<ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
																{proj.rules_count}
															</span>
															<span
																className="inline-flex items-center gap-1"
																title="Detection Jobs"
															>
																<Terminal className="w-3.5 h-3.5 text-purple-400" />
																{proj.detection_jobs_count}
															</span>
														</div>
													</td>

													{/* Updated At */}
													<td className="py-3.5 px-4 text-slate-400 text-[11px] font-mono">
														{proj.updated_at
															? new Date(proj.updated_at).toLocaleDateString()
															: '—'}
													</td>

													{/* Actions */}
													<td
														className="py-3.5 px-4 text-right"
														onClick={(e) => e.stopPropagation()}
													>
														<div className="flex items-center justify-end gap-1.5">
															<button
																type="button"
																onClick={() => handleEnterWorkspace(proj)}
																className="px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold transition inline-flex items-center gap-1 shadow-glow-blue"
															>
																<span>Open Workspace</span>
																<ArrowRight className="w-3 h-3" />
															</button>

															<button
																type="button"
																onClick={() => setInspectingProjectId(proj.project_id)}
																title="Inspect RAW Schema"
																aria-label={`Inspect schema for ${proj.project_name}`}
																className="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-300 hover:text-white transition"
															>
																<Eye className="w-3.5 h-3.5" />
															</button>

															<button
																type="button"
																onClick={() => setEditingProject(proj)}
																title="Edit Project"
																aria-label={`Edit ${proj.project_name}`}
																className="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-300 hover:text-white transition"
															>
																<Edit3 className="w-3.5 h-3.5" />
															</button>

															<button
																type="button"
																onClick={(e) => handleToggleArchive(proj, e)}
																title={
																	proj.status === 'ACTIVE'
																		? 'Archive Project'
																		: 'Restore Project'
																}
																aria-label={
																	proj.status === 'ACTIVE'
																		? `Archive ${proj.project_name}`
																		: `Restore ${proj.project_name}`
																}
																className="p-1.5 rounded-lg bg-dark-800 hover:bg-amber-500/20 border border-dark-700 text-slate-400 hover:text-amber-300 transition"
															>
																{proj.status === 'ACTIVE' ? (
																	<Archive className="w-3.5 h-3.5" />
																) : (
																	<ArchiveRestore className="w-3.5 h-3.5" />
																)}
															</button>

															<button
																type="button"
																onClick={(e) => handleDeleteProject(proj, e)}
																title="Delete Project"
																aria-label={`Delete ${proj.project_name}`}
																className="p-1.5 rounded-lg bg-dark-800 hover:bg-rose-500/20 border border-dark-700 text-slate-400 hover:text-rose-400 transition"
															>
																<Trash2 className="w-3.5 h-3.5" />
															</button>
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
				</div>
			</div>

			{/* Edit Project Modal */}
			<ProjectFormModal
				isOpen={Boolean(editingProject)}
				editingProject={editingProject}
				onClose={() => setEditingProject(null)}
				onCreate={createProject}
				onUpdate={updateProject}
			/>

			{/* Inspect & Reset RAW Schema Drawer */}
			<ProjectSchemaDrawer
				project={inspectingProject}
				onClose={() => setInspectingProjectId(null)}
				onResetSchema={resetProjectSchema}
			/>
		</div>
	);
};
