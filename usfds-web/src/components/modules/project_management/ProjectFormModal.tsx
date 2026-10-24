import React, { useState } from 'react';
import {
	FolderPlus,
	Edit3,
	X,
	ShieldAlert,
	Loader2,
	CheckCircle2,
	Archive,
} from 'lucide-react';
import type {
	CreateProjectRequest,
	ProjectResponse,
	ProjectStatus,
	UpdateProjectRequest,
} from '../../../types/project';

interface ProjectFormModalProps {
	isOpen: boolean;
	editingProject?: ProjectResponse | null;
	onClose: () => void;
	onCreate: (payload: CreateProjectRequest) => Promise<ProjectResponse>;
	onUpdate?: (projectId: string, payload: UpdateProjectRequest) => Promise<ProjectResponse>;
}

const ProjectFormDialogContent: React.FC<Omit<ProjectFormModalProps, 'isOpen'>> = ({
	editingProject = null,
	onClose,
	onCreate,
	onUpdate,
}) => {
	const isEditMode = Boolean(editingProject);
	const [projectName, setProjectName] = useState(editingProject?.project_name || '');
	const [description, setDescription] = useState(editingProject?.description || '');
	const [status, setStatus] = useState<ProjectStatus>(editingProject?.status || 'ACTIVE');
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		const trimmedName = projectName.trim();
		if (!trimmedName) {
			setErrorMsg('Tên dự án (project_name) không được để trống.');
			return;
		}

		setIsSubmitting(true);
		setErrorMsg(null);
		try {
			if (isEditMode && editingProject && onUpdate) {
				await onUpdate(editingProject.project_id, {
					project_name: trimmedName,
					description: description.trim() || undefined,
					status,
				});
			} else {
				await onCreate({
					project_name: trimmedName,
					description: description.trim() || undefined,
				});
			}
			onClose();
		} catch (err: any) {
			setErrorMsg(err?.message || 'Thao tác lưu dự án thất bại.');
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div
			className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
			role="dialog"
			aria-modal="true"
			aria-labelledby="project-modal-title"
		>
			<div className="w-full max-w-lg bg-dark-900 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
				{/* Modal Header */}
				<div className="flex items-start justify-between p-5 border-b border-dark-800 bg-dark-950/60">
					<div className="flex items-center gap-3">
						<div className="w-9 h-9 rounded-xl bg-brand-500/15 border border-brand-500/30 flex items-center justify-center text-brand-400">
							{isEditMode ? <Edit3 className="w-4 h-4" /> : <FolderPlus className="w-4 h-4" />}
						</div>
						<div>
							<h2 id="project-modal-title" className="text-sm font-bold text-slate-100">
								{isEditMode ? 'Cập nhật Thông tin Dự án' : 'Khởi tạo Dự án Mới'}
							</h2>
							<p className="text-[11px] text-slate-400 mt-0.5">
								{isEditMode
									? 'Chỉnh sửa tên hiển thị, mô tả hoặc trạng thái vận hành của dự án'
									: 'RAW Schema sẽ tự động khóa khi nạp Dataset đầu tiên (Schema-on-First-Upload)'}
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						aria-label="Đóng hộp thoại"
						className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
					>
						<X className="w-4 h-4" />
					</button>
				</div>

				{/* Form Body */}
				<form onSubmit={handleSubmit} className="p-5 space-y-4">
					{errorMsg && (
						<div
							role="alert"
							className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2.5"
						>
							<ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
							<span>{errorMsg}</span>
						</div>
					)}

					<div>
						<label
							htmlFor="project-name-input"
							className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
						>
							Tên dự án (Project Name) <span className="text-rose-400">*</span>
						</label>
						<input
							id="project-name-input"
							type="text"
							value={projectName}
							onChange={(e) => setProjectName(e.target.value)}
							placeholder="Ví dụ: E-Commerce Card Fraud 2026"
							maxLength={255}
							required
							autoFocus
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100 focus:border-brand-500 focus:outline-none transition"
						/>
					</div>

					<div>
						<label
							htmlFor="project-desc-input"
							className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
						>
							Mô tả nghiệp vụ (Description)
						</label>
						<textarea
							id="project-desc-input"
							rows={3}
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							placeholder="Mô tả phạm vi dữ liệu giao dịch, mục tiêu phát hiện gian lận..."
							maxLength={2000}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-200 focus:border-brand-500 focus:outline-none transition resize-none"
						/>
					</div>

					{isEditMode && (
						<div>
							<label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
								Trạng thái Dự án (Status)
							</label>
							<div className="grid grid-cols-2 gap-2.5">
								<button
									type="button"
									onClick={() => setStatus('ACTIVE')}
									className={`p-2.5 rounded-xl border text-left flex items-center gap-2.5 transition ${
										status === 'ACTIVE'
											? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
											: 'bg-dark-950 border-dark-800 text-slate-400 hover:text-slate-200'
									}`}
								>
									<CheckCircle2 className="w-4 h-4 shrink-0" />
									<div>
										<div className="text-xs font-bold font-mono">ACTIVE</div>
										<div className="text-[10px] opacity-80">Đang hoạt động</div>
									</div>
								</button>

								<button
									type="button"
									onClick={() => setStatus('ARCHIVED')}
									className={`p-2.5 rounded-xl border text-left flex items-center gap-2.5 transition ${
										status === 'ARCHIVED'
											? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
											: 'bg-dark-950 border-dark-800 text-slate-400 hover:text-slate-200'
									}`}
								>
									<Archive className="w-4 h-4 shrink-0" />
									<div>
										<div className="text-xs font-bold font-mono">ARCHIVED</div>
										<div className="text-[10px] opacity-80">Lưu trữ (Read-only)</div>
									</div>
								</button>
							</div>
						</div>
					)}

					{/* Modal Footer */}
					<div className="flex items-center justify-end gap-2.5 pt-3 border-t border-dark-800">
						<button
							type="button"
							onClick={onClose}
							disabled={isSubmitting}
							className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
						>
							Hủy
						</button>
						<button
							type="submit"
							disabled={isSubmitting}
							className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2"
						>
							{isSubmitting ? (
								<>
									<Loader2 className="w-3.5 h-3.5 animate-spin" />
									<span>Đang lưu...</span>
								</>
							) : (
								<span>{isEditMode ? 'Lưu thay đổi' : 'Tạo dự án'}</span>
							)}
						</button>
					</div>
				</form>
			</div>
		</div>
	);
};

export const ProjectFormModal: React.FC<ProjectFormModalProps> = ({
	isOpen,
	editingProject = null,
	onClose,
	onCreate,
	onUpdate,
}) => {
	if (!isOpen) {
		return null;
	}
	return (
		<ProjectFormDialogContent
			key={editingProject?.project_id || 'new-project'}
			editingProject={editingProject}
			onClose={onClose}
			onCreate={onCreate}
			onUpdate={onUpdate}
		/>
	);
};
