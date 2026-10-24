import React, { useState } from 'react';
import {
	Lock,
	Unlock,
	X,
	RotateCcw,
	ShieldAlert,
	CheckCircle2,
	Database,
	ShieldCheck,
	Terminal,
	Loader2,
	FileSpreadsheet,
} from 'lucide-react';
import type { LogicalDataType, ProjectResponse } from '../../../types/project';

interface ProjectSchemaDrawerProps {
	project: ProjectResponse | null;
	onClose: () => void;
	onResetSchema: (projectId: string) => Promise<ProjectResponse>;
}

const LOGICAL_TYPE_STYLES: Record<LogicalDataType, string> = {
	NUMERIC: 'bg-brand-500/15 text-brand-300 border-brand-500/30',
	STRING: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
	BOOLEAN: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
	DATETIME: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
};

export const ProjectSchemaDrawer: React.FC<ProjectSchemaDrawerProps> = ({
	project,
	onClose,
	onResetSchema,
}) => {
	const [isResetting, setIsResetting] = useState(false);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);
	const [successMsg, setSuccessMsg] = useState<string | null>(null);

	if (!project) {
		return null;
	}

	const columnsMap = project.raw_schema?.columns || {};
	const columnEntries = Object.entries(columnsMap);
	const hasDependentResources =
		project.datasets_count > 0 ||
		project.rules_count > 0 ||
		project.detection_jobs_count > 0;
	const canResetSchema = project.is_schema_locked && !hasDependentResources;

	const handleResetSchema = async () => {
		if (!canResetSchema) {
			return;
		}
		if (
			!window.confirm(
				`Bạn có chắc muốn mở khóa và đặt lại (Reset) RAW Schema của dự án "${project.project_name}"?`
			)
		) {
			return;
		}

		setIsResetting(true);
		setErrorMsg(null);
		setSuccessMsg(null);
		try {
			await onResetSchema(project.project_id);
			setSuccessMsg('Đã mở khóa và đặt lại RAW Schema thành công.');
		} catch (err: any) {
			setErrorMsg(err?.message || 'Không thể đặt lại RAW Schema.');
		} finally {
			setIsResetting(false);
		}
	};

	return (
		<div
			className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs animate-fade-in"
			role="dialog"
			aria-modal="true"
			aria-labelledby="schema-drawer-title"
		>
			<div className="w-full max-w-[540px] h-full bg-dark-900 border-l border-dark-700 shadow-2xl flex flex-col overflow-hidden">
				{/* Drawer Header */}
				<div className="flex items-start justify-between p-5 border-b border-dark-800 bg-dark-950">
					<div className="space-y-1">
						<div className="flex items-center gap-2">
							{project.is_schema_locked ? (
								<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
									<Lock className="w-3 h-3" />
									SCHEMA LOCKED
								</span>
							) : (
								<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-amber-500/15 text-amber-300 border border-amber-500/30">
									<Unlock className="w-3 h-3" />
									SCHEMA UNLOCKED
								</span>
							)}
							<span className="text-[11px] text-slate-500 font-mono">
								v{project.raw_schema?.version || 1}
							</span>
						</div>
						<h2 id="schema-drawer-title" className="text-base font-bold text-slate-100">
							{project.project_name} — RAW Schema Contract
						</h2>
						<p className="text-[11px] text-slate-400 font-mono">{project.project_id}</p>
					</div>

					<button
						type="button"
						onClick={onClose}
						aria-label="Đóng bảng chi tiết Schema"
						className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
					>
						<X className="w-4 h-4" />
					</button>
				</div>

				{/* Drawer Body */}
				<div className="flex-1 overflow-y-auto p-5 space-y-5">
					{errorMsg && (
						<div
							role="alert"
							className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2"
						>
							<ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
							<span>{errorMsg}</span>
						</div>
					)}

					{successMsg && (
						<div
							role="status"
							className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 flex items-start gap-2"
						>
							<CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
							<span>{successMsg}</span>
						</div>
					)}

					{/* Resource Dependency Summary */}
					<div className="grid grid-cols-3 gap-2.5">
						<div className="p-3 rounded-xl bg-dark-950 border border-dark-800">
							<div className="flex items-center justify-between text-slate-400 text-[10px] uppercase font-mono">
								<span>Datasets</span>
								<Database className="w-3.5 h-3.5 text-brand-400" />
							</div>
							<div className="text-lg font-bold text-slate-100 font-mono mt-1">
								{project.datasets_count}
							</div>
						</div>
						<div className="p-3 rounded-xl bg-dark-950 border border-dark-800">
							<div className="flex items-center justify-between text-slate-400 text-[10px] uppercase font-mono">
								<span>Rules</span>
								<ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
							</div>
							<div className="text-lg font-bold text-slate-100 font-mono mt-1">
								{project.rules_count}
							</div>
						</div>
						<div className="p-3 rounded-xl bg-dark-950 border border-dark-800">
							<div className="flex items-center justify-between text-slate-400 text-[10px] uppercase font-mono">
								<span>Jobs</span>
								<Terminal className="w-3.5 h-3.5 text-purple-400" />
							</div>
							<div className="text-lg font-bold text-slate-100 font-mono mt-1">
								{project.detection_jobs_count}
							</div>
						</div>
					</div>

					{/* Schema Contract Table or Empty State */}
					{!project.is_schema_locked || columnEntries.length === 0 ? (
						<div className="p-6 rounded-2xl bg-dark-950/70 border border-dashed border-dark-700 text-center space-y-2">
							<Unlock className="w-8 h-8 text-amber-400 mx-auto" />
							<h3 className="text-xs font-bold text-slate-200">
								RAW Schema đang Mở khóa (UNLOCKED)
							</h3>
							<p className="text-xs text-slate-400 leading-relaxed">
								Dự án này chưa khóa cấu trúc cột. Ngay khi bạn tải lên Dataset đầu tiên trong
								phân hệ <strong>Data Management</strong>, hệ thống sẽ tự động trích xuất tên cột
								và kiểu dữ liệu logic để khóa làm chuẩn cho toàn bộ dự án (BR-PM-01).
							</p>
						</div>
					) : (
						<div className="space-y-3">
							<div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 space-y-1.5 text-xs">
								<div className="flex items-center justify-between">
									<span className="text-slate-400">Tổng số cột chuẩn:</span>
									<span className="font-mono font-bold text-slate-100">
										{columnEntries.length} columns
									</span>
								</div>
								<div className="flex items-center justify-between">
									<span className="text-slate-400">Dataset cơ sở (Base Dataset):</span>
									<span className="font-mono text-[11px] text-brand-300 truncate max-w-[260px]">
										{project.base_dataset_id || project.raw_schema?.source_dataset_id || 'N/A'}
									</span>
								</div>
								{project.raw_schema?.locked_at && (
									<div className="flex items-center justify-between">
										<span className="text-slate-400">Thời điểm khóa Schema:</span>
										<span className="font-mono text-[11px] text-slate-300">
											{new Date(project.raw_schema.locked_at).toLocaleString()}
										</span>
									</div>
								)}
							</div>

							<div className="border border-dark-800 rounded-xl overflow-hidden bg-dark-950/60">
								<table className="w-full text-left text-xs">
									<caption className="sr-only">Bảng cấu trúc cột RAW Schema của dự án</caption>
									<thead>
										<tr className="border-b border-dark-800 bg-dark-950 text-[10px] uppercase tracking-wider text-slate-400 font-mono">
											<th scope="col" className="py-2.5 px-3 font-semibold">
												Column Name
											</th>
											<th scope="col" className="py-2.5 px-3 font-semibold">
												Logical Type
											</th>
											<th scope="col" className="py-2.5 px-3 font-semibold">
												Physical Dtype
											</th>
											<th scope="col" className="py-2.5 px-3 font-semibold text-right">
												Nullable
											</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-dark-850 font-mono">
										{columnEntries.map(([colName, spec]) => {
											const badgeClass =
												LOGICAL_TYPE_STYLES[spec.logical_type] ||
												LOGICAL_TYPE_STYLES.STRING;
											return (
												<tr key={colName} className="hover:bg-dark-900/80 transition">
													<td className="py-2.5 px-3 text-slate-100 font-semibold flex items-center gap-1.5">
														<FileSpreadsheet className="w-3.5 h-3.5 text-slate-500 shrink-0" />
														<span className="truncate">{colName}</span>
													</td>
													<td className="py-2.5 px-3">
														<span
															className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeClass}`}
														>
															{spec.logical_type}
														</span>
													</td>
													<td className="py-2.5 px-3 text-slate-400 text-[11px]">
														{spec.physical_dtype}
													</td>
													<td className="py-2.5 px-3 text-right">
														{spec.nullable ? (
															<span className="text-[10px] text-slate-400">YES</span>
														) : (
															<span className="text-[10px] text-amber-400 font-bold">
																REQUIRED
															</span>
														)}
													</td>
												</tr>
											);
										})}
									</tbody>
								</table>
							</div>
						</div>
					)}

					{/* Schema Governance & Reset Box (BR-PM-03) */}
					<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2.5">
						<div className="text-xs font-bold text-slate-200 flex items-center gap-2">
							<RotateCcw className="w-3.5 h-3.5 text-amber-400" />
							<span>Đặt lại / Mở khóa RAW Schema (BR-PM-03)</span>
						</div>
						<p className="text-[11px] text-slate-400 leading-relaxed">
							Chỉ có thể đặt lại <code className="font-mono text-slate-300">raw_schema</code> khi
							dự án không còn Dataset, Rule hoặc Detection Job phụ thuộc (ví dụ khi bạn vừa tải
							nhầm file đầu tiên và đã xóa file đó).
						</p>
						{hasDependentResources && project.is_schema_locked && (
							<div className="text-[11px] text-amber-300/90 font-mono bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
								Đang khóa bởi tài nguyên phụ thuộc: {project.datasets_count} Datasets •{' '}
								{project.rules_count} Rules • {project.detection_jobs_count} Jobs
							</div>
						)}
						<div className="pt-1">
							<button
								type="button"
								onClick={handleResetSchema}
								disabled={!canResetSchema || isResetting}
								className="w-full py-2 px-3 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 disabled:opacity-40 disabled:cursor-not-allowed border border-amber-500/30 text-amber-300 text-xs font-semibold transition flex items-center justify-center gap-2"
							>
								{isResetting ? (
									<>
										<Loader2 className="w-3.5 h-3.5 animate-spin" />
										<span>Đang mở khóa Schema...</span>
									</>
								) : (
									<>
										<Unlock className="w-3.5 h-3.5" />
										<span>Reset / Unlock RAW Schema</span>
									</>
								)}
							</button>
						</div>
					</div>
				</div>

				{/* Drawer Footer */}
				<div className="p-4 border-t border-dark-800 bg-dark-950 flex justify-end">
					<button
						type="button"
						onClick={onClose}
						className="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-slate-200 text-xs font-medium transition"
					>
						Đóng
					</button>
				</div>
			</div>
		</div>
	);
};
