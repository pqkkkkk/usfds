import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
	Lock,
	Unlock,
	RefreshCw,
	Edit3,
	RotateCcw,
	Database,
	ShieldCheck,
	Terminal,
	CheckCircle2,
	Archive,
	ShieldAlert,
	FileSpreadsheet,
	Search,
	Loader2,
	ArrowRight,
	Calendar,
	Hash,
} from 'lucide-react';
import { PageHeader } from '../../layout/PageHeader';
import { useProject } from '../../../hooks/useProjects';
import type { LogicalDataType } from '../../../types/project';
import { ProjectFormModal } from './ProjectFormModal';

const LOGICAL_TYPE_STYLES: Record<LogicalDataType, string> = {
	NUMERIC: 'bg-brand-500/15 text-brand-300 border-brand-500/30',
	STRING: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
	BOOLEAN: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
	DATETIME: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
};

export const ProjectSettingsView: React.FC = () => {
	const navigate = useNavigate();
	const {
		currentProject,
		isLoading,
		refetchProjects,
		createProject,
		updateProject,
		resetProjectSchema,
	} = useProject();

	const [isEditModalOpen, setIsEditModalOpen] = useState(false);
	const [colSearch, setColSearch] = useState('');
	const [isResetting, setIsResetting] = useState(false);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);
	const [successMsg, setSuccessMsg] = useState<string | null>(null);

	const columnEntries = useMemo(() => {
		const cols = currentProject?.raw_schema?.columns || {};
		const entries = Object.entries(cols);
		const q = colSearch.trim().toLowerCase();
		if (!q) {
			return entries;
		}
		return entries.filter(
			([name, spec]) =>
				name.toLowerCase().includes(q) ||
				spec.logical_type.toLowerCase().includes(q) ||
				spec.physical_dtype.toLowerCase().includes(q)
		);
	}, [currentProject, colSearch]);

	if (!currentProject) {
		return null;
	}

	const totalColumnsCount = Object.keys(currentProject.raw_schema?.columns || {}).length;
	const hasDependentResources =
		currentProject.datasets_count > 0 ||
		currentProject.rules_count > 0 ||
		currentProject.detection_jobs_count > 0;
	const canResetSchema = currentProject.is_schema_locked && !hasDependentResources;

	const handleResetSchema = async () => {
		if (!canResetSchema) {
			return;
		}
		if (
			!window.confirm(
				`Bạn có chắc muốn mở khóa và đặt lại lược đồ thô của dự án "${currentProject.project_name}"?`
			)
		) {
			return;
		}
		setIsResetting(true);
		setErrorMsg(null);
		setSuccessMsg(null);
		try {
			await resetProjectSchema(currentProject.project_id);
			setSuccessMsg('Đã mở khóa và đặt lại lược đồ thô về trạng thái chưa khóa.');
		} catch (err: any) {
			setErrorMsg(err?.message || 'Không thể đặt lại lược đồ thô.');
		} finally {
			setIsResetting(false);
		}
	};

	return (
		<div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
			<PageHeader
				title="Cài đặt dự án & Lược đồ"
				breadcrumbs={[
					{ label: currentProject.project_name },
					{ label: 'Cài đặt dự án' },
				]}
				actions={
					<div className="flex items-center gap-2.5">
						<button
							type="button"
							onClick={() => refetchProjects()}
							disabled={isLoading}
							className="p-2 rounded-xl bg-dark-850 hover:bg-dark-800 border border-dark-700 text-slate-400 hover:text-slate-200 transition"
							title="Làm mới thông tin dự án"
							aria-label="Làm mới thông tin dự án"
						>
							<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-brand-400' : ''}`} />
						</button>
						<button
							type="button"
							onClick={() => setIsEditModalOpen(true)}
							className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2"
						>
							<Edit3 className="w-3.5 h-3.5" />
							<span>Chỉnh sửa thông tin dự án</span>
						</button>
					</div>
				}
			/>

			<div className="flex-1 overflow-y-auto p-6 space-y-6">
				{errorMsg && (
					<div
						role="alert"
						className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2.5"
					>
						<ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
						<span>{errorMsg}</span>
					</div>
				)}

				{successMsg && (
					<div
						role="status"
						className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 flex items-center gap-2.5"
					>
						<CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
						<span>{successMsg}</span>
					</div>
				)}

				{/* Section 1: Basic Project Information & Resource Counters */}
				<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
					{/* Basic Metadata Card */}
					<div className="lg:col-span-2 p-5 rounded-2xl bg-dark-900 border border-dark-800 space-y-4">
						<div className="flex items-start justify-between gap-4">
							<div className="space-y-1">
								<div className="flex items-center gap-2.5">
									<h2 className="text-base font-bold text-slate-100">
										{currentProject.project_name}
									</h2>
									{currentProject.status === 'ACTIVE' ? (
										<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
											<CheckCircle2 className="w-3 h-3 text-emerald-400" />
											ACTIVE
										</span>
									) : (
										<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
											<Archive className="w-3 h-3 text-amber-400" />
											ARCHIVED
										</span>
									)}
								</div>
								<p className="text-xs text-slate-400 leading-relaxed">
									{currentProject.description || 'Chưa có mô tả chi tiết cho dự án này.'}
								</p>
							</div>
						</div>

						<div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-dark-800 text-xs">
							<div className="p-3 rounded-xl bg-dark-950/70 border border-dark-800/80 space-y-1">
								<div className="text-[10px] uppercase tracking-wider text-slate-500 font-mono flex items-center gap-1.5">
									<Hash className="w-3 h-3" />
									<span>Mã dự án</span>
								</div>
								<div className="font-mono text-[11px] text-slate-200 truncate">
									{currentProject.project_id}
								</div>
							</div>

							<div className="p-3 rounded-xl bg-dark-950/70 border border-dark-800/80 space-y-1">
								<div className="text-[10px] uppercase tracking-wider text-slate-500 font-mono flex items-center gap-1.5">
									<Calendar className="w-3 h-3" />
									<span>Ngày tạo</span>
								</div>
								<div className="font-mono text-[11px] text-slate-200">
									{new Date(currentProject.created_at).toLocaleString()}
								</div>
							</div>

							<div className="p-3 rounded-xl bg-dark-950/70 border border-dark-800/80 space-y-1">
								<div className="text-[10px] uppercase tracking-wider text-slate-500 font-mono flex items-center gap-1.5">
									<Calendar className="w-3 h-3" />
									<span>Cập nhật gần nhất</span>
								</div>
								<div className="font-mono text-[11px] text-slate-200">
									{new Date(currentProject.updated_at).toLocaleString()}
								</div>
							</div>
						</div>
					</div>

					{/* Resource Isolation Summary Card */}
					<div className="p-5 rounded-2xl bg-dark-900 border border-dark-800 flex flex-col justify-between space-y-4">
						<div>
							<h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">
								Tài nguyên dự án
							</h3>
							<p className="text-[11px] text-slate-500 mt-0.5">
								Tài nguyên cô lập thuộc dự án hiện tại (BR-PM-06)
							</p>
						</div>

						<div className="grid grid-cols-3 gap-2.5">
							<div className="p-3 rounded-xl bg-dark-950 border border-dark-800">
								<div className="flex items-center justify-between text-slate-400 text-[10px] uppercase font-mono">
									<span>Tập dữ liệu</span>
									<Database className="w-3.5 h-3.5 text-brand-400" />
								</div>
								<div className="text-xl font-black text-slate-100 font-mono mt-1">
									{currentProject.datasets_count}
								</div>
							</div>

							<div className="p-3 rounded-xl bg-dark-950 border border-dark-800">
								<div className="flex items-center justify-between text-slate-400 text-[10px] uppercase font-mono">
									<span>Luật</span>
									<ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
								</div>
								<div className="text-xl font-black text-slate-100 font-mono mt-1">
									{currentProject.rules_count}
								</div>
							</div>

							<div className="p-3 rounded-xl bg-dark-950 border border-dark-800">
								<div className="flex items-center justify-between text-slate-400 text-[10px] uppercase font-mono">
									<span>Tác vụ</span>
									<Terminal className="w-3.5 h-3.5 text-purple-400" />
								</div>
								<div className="text-xl font-black text-slate-100 font-mono mt-1">
									{currentProject.detection_jobs_count}
								</div>
							</div>
						</div>
					</div>
				</div>

				{/* Section 2: Project RAW Schema Contract */}
				<div className="rounded-2xl bg-dark-900 border border-dark-800 overflow-hidden shadow-xl">
					{/* Schema Header Bar */}
					<div className="p-5 border-b border-dark-800 bg-dark-950/60 flex flex-col md:flex-row md:items-center justify-between gap-4">
						<div className="space-y-1">
							<div className="flex items-center gap-2.5">
								<h3 className="text-sm font-bold text-slate-100">
									Hợp đồng lược đồ thô dự án
								</h3>
								{currentProject.is_schema_locked ? (
									<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
										<Lock className="w-3 h-3" />
										Đã khóa ({totalColumnsCount} cột)
									</span>
								) : (
									<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-amber-500/15 text-amber-300 border border-amber-500/30">
										<Unlock className="w-3 h-3" />
										UNLOCKED
									</span>
								)}
							</div>
							<p className="text-xs text-slate-400">
								{currentProject.is_schema_locked ? (
									<>
										Xác lập từ tập dữ liệu cơ sở:{' '}
										<code className="font-mono text-brand-300">
											{currentProject.base_dataset_id ||
												currentProject.raw_schema?.source_dataset_id ||
												'Không có'}
										</code>
										{currentProject.raw_schema?.locked_at && (
											<>
												{' '}
												• Khóa lúc{' '}
												<span className="font-mono text-slate-300">
													{new Date(currentProject.raw_schema.locked_at).toLocaleString()}
												</span>
											</>
										)}
									</>
								) : (
									'Chưa có tập dữ liệu cơ sở. Cấu trúc lược đồ thô sẽ tự động khóa khi bạn tải lên tập dữ liệu đầu tiên (BR-PM-01).'
								)}
							</p>
						</div>

						<div className="flex items-center gap-2.5">
							{currentProject.is_schema_locked && (
								<div className="relative w-64">
									<Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
									<input
										type="search"
										aria-label="Tìm cột trong lược đồ thô"
										placeholder="Tìm tên cột hoặc kiểu dữ liệu..."
										value={colSearch}
										onChange={(e) => setColSearch(e.target.value)}
										className="w-full pl-8 pr-3 py-1.5 bg-dark-900 border border-dark-700 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500"
									/>
								</div>
							)}

							<button
								type="button"
								onClick={handleResetSchema}
								disabled={!canResetSchema || isResetting}
								title={
									!currentProject.is_schema_locked
										? 'Lược đồ đang ở trạng thái mở khóa'
										: hasDependentResources
											? 'Cần xóa toàn bộ tập dữ liệu, luật, tác vụ trước khi đặt lại lược đồ (BR-PM-03)'
											: 'Mở khóa và đặt lại lược đồ thô'
								}
								className="py-1.5 px-3 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 disabled:opacity-40 disabled:cursor-not-allowed border border-amber-500/30 text-amber-300 text-xs font-semibold transition flex items-center gap-1.5 shrink-0"
							>
								{isResetting ? (
									<>
										<Loader2 className="w-3.5 h-3.5 animate-spin" />
										<span>Đang đặt lại...</span>
									</>
								) : (
									<>
										<RotateCcw className="w-3.5 h-3.5" />
										<span>Đặt lại lược đồ thô</span>
									</>
								)}
							</button>
						</div>
					</div>

					{/* Schema Body: Table or Unlocked Empty State */}
					{!currentProject.is_schema_locked || totalColumnsCount === 0 ? (
						<div className="p-10 text-center space-y-3">
							<div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mx-auto">
								<Unlock className="w-6 h-6" />
							</div>
							<div className="space-y-1 max-w-lg mx-auto">
								<h4 className="text-sm font-bold text-slate-200">
									Lược đồ thô chưa được khóa (tự khóa khi tải lên đầu tiên)
								</h4>
								<p className="text-xs text-slate-400 leading-relaxed">
									Hãy chuyển sang phân hệ <strong>Quản lý dữ liệu</strong> và tải lên tập dữ
									liệu giao dịch đầu tiên. Hệ thống sẽ tự động trích xuất danh sách cột cùng kiểu
									dữ liệu logic (<code className="font-mono">NUMERIC</code>,{' '}
									<code className="font-mono">STRING</code>,{' '}
									<code className="font-mono">BOOLEAN</code>,{' '}
									<code className="font-mono">DATETIME</code>) để khóa làm chuẩn cho toàn bộ
									Tập dữ liệu và luật trong dự án.
								</p>
							</div>
							<div className="pt-2">
								<button
									type="button"
									onClick={() => navigate('/datasets')}
									className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition inline-flex items-center gap-2"
								>
									<span>Đi tới Quản lý dữ liệu</span>
									<ArrowRight className="w-3.5 h-3.5" />
								</button>
							</div>
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<caption className="sr-only">Bảng chi tiết các cột trong lược đồ thô</caption>
								<thead>
									<tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
										<th scope="col" className="py-3 px-4 w-14 font-semibold">
											#
										</th>
										<th scope="col" className="py-3 px-4 font-semibold">
											Tên cột — trường thô
										</th>
										<th scope="col" className="py-3 px-4 font-semibold">
											Kiểu logic
										</th>
										<th scope="col" className="py-3 px-4 font-semibold">
											Kiểu vật lý
										</th>
										<th scope="col" className="py-3 px-4 font-semibold text-right">
											Ràng buộc rỗng
										</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-850 font-mono">
									{columnEntries.length === 0 ? (
										<tr>
											<td colSpan={5} className="py-8 text-center text-slate-500 font-sans">
												Không tìm thấy cột nào khớp với từ khóa "{colSearch}".
											</td>
										</tr>
									) : (
										columnEntries.map(([colName, spec], idx) => {
											const badgeClass =
												LOGICAL_TYPE_STYLES[spec.logical_type] ||
												LOGICAL_TYPE_STYLES.STRING;
											return (
												<tr key={colName} className="hover:bg-dark-850/60 transition">
													<td className="py-3 px-4 text-slate-500 text-[11px]">
														{idx + 1}
													</td>
													<td className="py-3 px-4 text-slate-100 font-bold flex items-center gap-2">
														<FileSpreadsheet className="w-3.5 h-3.5 text-slate-500 shrink-0" />
														<span>{colName}</span>
													</td>
													<td className="py-3 px-4">
														<span
															className={`px-2.5 py-0.5 rounded text-[10px] font-bold border ${badgeClass}`}
														>
															{spec.logical_type}
														</span>
													</td>
													<td className="py-3 px-4 text-slate-400 text-[11px]">
														{spec.physical_dtype}
													</td>
													<td className="py-3 px-4 text-right">
														{spec.nullable ? (
															<span className="px-2 py-0.5 rounded text-[10px] bg-dark-800 text-slate-400 border border-dark-700">
																NULLABLE
															</span>
														) : (
															<span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30 font-bold">
																NOT NULL
															</span>
														)}
													</td>
												</tr>
											);
										})
									)}
								</tbody>
							</table>
						</div>
					)}
				</div>
			</div>

			{/* Edit Project Modal */}
			<ProjectFormModal
				isOpen={isEditModalOpen}
				editingProject={currentProject}
				onClose={() => setIsEditModalOpen(false)}
				onCreate={createProject}
				onUpdate={updateProject}
			/>
		</div>
	);
};
