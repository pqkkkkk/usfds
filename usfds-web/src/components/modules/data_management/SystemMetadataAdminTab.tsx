import { useState } from 'react';
import type { FormEvent } from 'react';
import {
	AlertTriangle,
	Check,
	Database,
	Edit3,
	Lock,
	Plus,
	Trash2,
	X,
} from 'lucide-react';
import { useSystemMetadata } from '@/hooks/useSystemMetadata';
import type {
	ColumnMlRole,
	LogicalDataType,
	SystemColumnMetadata,
} from '@/types/systemMetadata';

const LOGICAL_TYPE_OPTIONS: Array<{ value: LogicalDataType; label: string }> = [
	{ value: 'STRING', label: 'STRING (Chuỗi)' },
	{ value: 'NUMERIC', label: 'NUMERIC (Số)' },
	{ value: 'BOOLEAN', label: 'BOOLEAN (Luận lý)' },
	{ value: 'DATETIME', label: 'DATETIME (Thời gian)' },
];

const ML_ROLE_OPTIONS: Array<{ value: ColumnMlRole; label: string }> = [
	{ value: 'FEATURE', label: 'FEATURE (Đặc trưng ML)' },
	{ value: 'IDENTIFIER', label: 'IDENTIFIER (Định danh / Phi-ML)' },
	{ value: 'TIMESTAMP', label: 'TIMESTAMP (Thời gian / Phi-ML)' },
	{ value: 'LABEL', label: 'LABEL (Nhãn mục tiêu)' },
];

function parseAliasInput(raw: string): string[] {
	return raw
		.split(',')
		.map((item) => item.trim())
		.filter(Boolean);
}

export function SystemMetadataAdminTab() {
	const {
		columns,
		isLoading,
		isError,
		error,
		createColumn,
		isCreating,
		updateColumn,
		isUpdating,
		deleteColumn,
		isDeleting,
	} = useSystemMetadata({ includeInactive: true });

	const [actionError, setActionError] = useState<string | null>(null);

	// Create form state
	const [columnKey, setColumnKey] = useState('');
	const [displayName, setDisplayName] = useState('');
	const [logicalType, setLogicalType] = useState<LogicalDataType>('STRING');
	const [mlRole, setMlRole] = useState<ColumnMlRole>('FEATURE');
	const [isRequired, setIsRequired] = useState(false);
	const [aliasesInput, setAliasesInput] = useState('');
	const [description, setDescription] = useState('');

	// Inline edit state
	const [editingId, setEditingId] = useState<string | null>(null);
	const [editDisplayName, setEditDisplayName] = useState('');
	const [editLogicalType, setEditLogicalType] = useState<LogicalDataType>('STRING');
	const [editMlRole, setEditMlRole] = useState<ColumnMlRole>('FEATURE');
	const [editIsRequired, setEditIsRequired] = useState(false);
	const [editIsActive, setEditIsActive] = useState(true);
	const [editAliases, setEditAliases] = useState('');
	const [editDescription, setEditDescription] = useState('');

	const handleCreate = async (e: FormEvent) => {
		e.preventDefault();
		setActionError(null);
		try {
			await createColumn({
				column_key: columnKey.trim().toLowerCase(),
				display_name: displayName.trim(),
				logical_type: logicalType,
				ml_role: mlRole,
				is_required: isRequired,
				aliases: parseAliasInput(aliasesInput),
				description: description.trim() || null,
				is_active: true,
			});
			setColumnKey('');
			setDisplayName('');
			setLogicalType('STRING');
			setMlRole('FEATURE');
			setIsRequired(false);
			setAliasesInput('');
			setDescription('');
		} catch (err) {
			setActionError(err instanceof Error ? err.message : 'Không thể thêm cột nghiệp vụ mới');
		}
	};

	const startEdit = (col: SystemColumnMetadata) => {
		setActionError(null);
		setEditingId(col.metadata_id);
		setEditDisplayName(col.display_name);
		setEditLogicalType(col.logical_type);
		setEditMlRole(col.ml_role);
		setEditIsRequired(col.is_required);
		setEditIsActive(col.is_active);
		setEditAliases((col.aliases || []).join(', '));
		setEditDescription(col.description || '');
	};

	const cancelEdit = () => {
		setEditingId(null);
		setActionError(null);
	};

	const handleSaveEdit = async (col: SystemColumnMetadata) => {
		setActionError(null);
		try {
			const isCore = col.category === 'CORE';
			await updateColumn({
				metadataId: col.metadata_id,
				payload: isCore
					? {
						display_name: editDisplayName.trim(),
						aliases: parseAliasInput(editAliases),
						description: editDescription.trim() || null,
					}
					: {
						display_name: editDisplayName.trim(),
						logical_type: editLogicalType,
						ml_role: editMlRole,
						is_required: editIsRequired,
						is_active: editIsActive,
						aliases: parseAliasInput(editAliases),
						description: editDescription.trim() || null,
					},
			});
			setEditingId(null);
		} catch (err) {
			setActionError(err instanceof Error ? err.message : 'Không thể lưu thay đổi siêu dữ liệu');
		}
	};

	const handleDelete = async (col: SystemColumnMetadata) => {
		if (col.category === 'CORE') {
			return;
		}
		setActionError(null);
		try {
			await deleteColumn(col.metadata_id);
		} catch (err) {
			setActionError(err instanceof Error ? err.message : 'Không thể xóa cột nghiệp vụ');
		}
	};

	const displayError = actionError || (isError ? error?.message || 'Không thể tải siêu dữ liệu hệ thống' : null);

	return (
		<div className="space-y-5">
			{displayError && (
				<div
					role="alert"
					className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-center gap-2"
				>
					<AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
					<span>{displayError}</span>
				</div>
			)}

			<form
				onSubmit={handleCreate}
				className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 space-y-4"
			>
				<div className="flex items-center justify-between">
					<div>
						<h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
							<Database className="w-4 h-4 text-brand-400" aria-hidden="true" />
							Thêm cột chuẩn nghiệp vụ mở rộng (DOMAIN)
						</h2>
						<p className="text-xs text-slate-400 mt-0.5">
							Các cột mới sẽ áp dụng cho các lần ánh xạ lược đồ tiếp theo (không làm gián đoạn artifact cũ).
						</p>
					</div>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-4 gap-3">
					<div>
						<label htmlFor="meta-col-key" className="block text-xs text-slate-400 mb-1">
							Mã cột chuẩn (column_key)
						</label>
						<input
							id="meta-col-key"
							type="text"
							required
							placeholder="vd: device_id"
							value={columnKey}
							onChange={(e) => setColumnKey(e.target.value)}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs font-mono text-slate-100"
						/>
					</div>
					<div>
						<label htmlFor="meta-display-name" className="block text-xs text-slate-400 mb-1">
							Tên hiển thị
						</label>
						<input
							id="meta-display-name"
							type="text"
							required
							placeholder="vd: Mã thiết bị"
							value={displayName}
							onChange={(e) => setDisplayName(e.target.value)}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
						/>
					</div>
					<div>
						<label htmlFor="meta-logical-type" className="block text-xs text-slate-400 mb-1">
							Kiểu dữ liệu logic
						</label>
						<select
							id="meta-logical-type"
							value={logicalType}
							onChange={(e) => setLogicalType(e.target.value as LogicalDataType)}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
						>
							{LOGICAL_TYPE_OPTIONS.map((opt) => (
								<option key={opt.value} value={opt.value}>
									{opt.label}
								</option>
							))}
						</select>
					</div>
					<div>
						<label htmlFor="meta-ml-role" className="block text-xs text-slate-400 mb-1">
							Vai trò ML
						</label>
						<select
							id="meta-ml-role"
							value={mlRole}
							onChange={(e) => setMlRole(e.target.value as ColumnMlRole)}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
						>
							{ML_ROLE_OPTIONS.map((opt) => (
								<option key={opt.value} value={opt.value}>
									{opt.label}
								</option>
							))}
						</select>
					</div>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
					<div>
						<label htmlFor="meta-aliases" className="block text-xs text-slate-400 mb-1">
							Danh sách alias gợi ý (phân tách bằng dấu phẩy)
						</label>
						<input
							id="meta-aliases"
							type="text"
							placeholder="vd: dev_hash, device_fp"
							value={aliasesInput}
							onChange={(e) => setAliasesInput(e.target.value)}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs font-mono text-slate-100"
						/>
					</div>
					<div>
						<label htmlFor="meta-description" className="block text-xs text-slate-400 mb-1">
							Mô tả nghiệp vụ
						</label>
						<input
							id="meta-description"
							type="text"
							placeholder="Mô tả ngắn gọn mục đích sử dụng cột"
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
						/>
					</div>
					<div className="flex items-center justify-between gap-3">
						<label htmlFor="meta-is-required" className="inline-flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
							<input
								id="meta-is-required"
								type="checkbox"
								checked={isRequired}
								onChange={(e) => setIsRequired(e.target.checked)}
								className="rounded border-dark-600 bg-dark-950 text-brand-500"
							/>
							Bắt buộc ánh xạ
						</label>
						<button
							type="submit"
							disabled={isCreating}
							className="px-3.5 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-xs font-medium inline-flex items-center gap-1.5"
						>
							<Plus className="w-3.5 h-3.5" aria-hidden="true" />
							Thêm cột nghiệp vụ
						</button>
					</div>
				</div>
			</form>

			<div className="bg-dark-900 border border-dark-700/80 rounded-xl overflow-hidden">
				{isLoading ? (
					<div className="p-6 text-xs text-slate-400">Đang tải danh sách siêu dữ liệu cột...</div>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-left text-xs">
							<caption className="sr-only">Danh sách cột siêu dữ liệu hệ thống và cột nghiệp vụ mở rộng</caption>
							<thead className="bg-dark-800/70 text-slate-400 border-b border-dark-700">
								<tr>
									<th scope="col" className="px-4 py-3">Mã cột & Tên hiển thị</th>
									<th scope="col" className="px-4 py-3">Nhóm</th>
									<th scope="col" className="px-4 py-3">Kiểu & Vai trò ML</th>
									<th scope="col" className="px-4 py-3">Ràng buộc</th>
									<th scope="col" className="px-4 py-3">Alias gợi ý</th>
									<th scope="col" className="px-4 py-3 text-right">Thao tác</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-dark-800">
								{columns.map((col) => {
									const isCore = col.category === 'CORE';
									const isEditing = editingId === col.metadata_id;

									return (
										<tr key={col.metadata_id} className="hover:bg-dark-800/40 align-top">
											<td className="px-4 py-3">
												<div className="flex items-center gap-1.5">
													<span className="font-mono font-semibold text-slate-100">{col.column_key}</span>
													{isCore && (
														<Lock className="w-3 h-3 text-amber-400" aria-hidden="true" />
													)}
												</div>
												{isEditing ? (
													<div className="mt-1.5 space-y-1.5">
														<input
															type="text"
															value={editDisplayName}
															onChange={(e) => setEditDisplayName(e.target.value)}
															aria-label={`Tên hiển thị cho ${col.column_key}`}
															className="w-full px-2 py-1 bg-dark-950 border border-dark-700 rounded text-xs text-slate-100"
														/>
														<input
															type="text"
															value={editDescription}
															onChange={(e) => setEditDescription(e.target.value)}
															placeholder="Mô tả"
															aria-label={`Mô tả cho ${col.column_key}`}
															className="w-full px-2 py-1 bg-dark-950 border border-dark-700 rounded text-xs text-slate-300"
														/>
													</div>
												) : (
													<>
														<div className="text-slate-300 mt-0.5">{col.display_name}</div>
														{col.description && (
															<div className="text-[11px] text-slate-500 mt-0.5">{col.description}</div>
														)}
													</>
												)}
											</td>

											<td className="px-4 py-3 whitespace-nowrap">
												<span
													className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium whitespace-nowrap ${
														isCore
															? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
															: 'bg-brand-500/15 text-brand-300 border border-brand-500/30'
													}`}
												>
													{isCore ? 'CORE (Cốt lõi)' : 'DOMAIN (Mở rộng)'}
												</span>
											</td>

											<td className="px-4 py-3">
												{isEditing && !isCore ? (
													<div className="space-y-1.5">
														<select
															value={editLogicalType}
															onChange={(e) => setEditLogicalType(e.target.value as LogicalDataType)}
															className="w-full px-2 py-1 bg-dark-950 border border-dark-700 rounded text-xs text-slate-100"
														>
															{LOGICAL_TYPE_OPTIONS.map((opt) => (
																<option key={opt.value} value={opt.value}>
																	{opt.value}
																</option>
															))}
														</select>
														<select
															value={editMlRole}
															onChange={(e) => setEditMlRole(e.target.value as ColumnMlRole)}
															className="w-full px-2 py-1 bg-dark-950 border border-dark-700 rounded text-xs text-slate-100"
														>
															{ML_ROLE_OPTIONS.map((opt) => (
																<option key={opt.value} value={opt.value}>
																	{opt.value}
																</option>
															))}
														</select>
													</div>
												) : (
													<div className="space-y-1">
														<div>
															<span className="px-1.5 py-0.5 rounded bg-dark-950 border border-dark-700 font-mono text-[11px] text-slate-200">
																{col.logical_type}
															</span>
														</div>
														<div>
															<span
																className={`px-1.5 py-0.5 rounded font-mono text-[10px] ${
																	col.ml_role === 'FEATURE'
																		? 'bg-emerald-500/15 text-emerald-300'
																		: 'bg-slate-700/60 text-slate-300'
																}`}
															>
																{col.ml_role}
															</span>
														</div>
													</div>
												)}
											</td>

											<td className="px-4 py-3 whitespace-nowrap">
												{isEditing && !isCore ? (
													<div className="space-y-1.5 text-[11px]">
														<label className="flex items-center gap-1.5 text-slate-300">
															<input
																type="checkbox"
																checked={editIsRequired}
																onChange={(e) => setEditIsRequired(e.target.checked)}
															/>
															Bắt buộc
														</label>
														<label className="flex items-center gap-1.5 text-slate-300">
															<input
																type="checkbox"
																checked={editIsActive}
																onChange={(e) => setEditIsActive(e.target.checked)}
															/>
															Kích hoạt
														</label>
													</div>
												) : (
													<div className="flex flex-col items-start gap-1">
														<span
															className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium whitespace-nowrap ${
																col.is_required
																	? 'bg-rose-500/15 text-rose-300'
																	: 'bg-dark-800 text-slate-400'
															}`}
														>
															{col.is_required ? 'Bắt buộc' : 'Tùy chọn'}
														</span>
														<span
															className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium whitespace-nowrap ${
																col.is_active
																	? 'bg-emerald-500/15 text-emerald-400'
																	: 'bg-slate-700/50 text-slate-400'
															}`}
														>
															{col.is_active ? 'Đang bật' : 'Đã tắt'}
														</span>
													</div>
												)}
											</td>

											<td className="px-4 py-3 max-w-xs">
												{isEditing ? (
													<input
														type="text"
														data-testid="edit-aliases-input"
														value={editAliases}
														onChange={(e) => setEditAliases(e.target.value)}
														placeholder="alias1, alias2"
														className="w-full px-2 py-1 bg-dark-950 border border-dark-700 rounded text-xs font-mono text-slate-100"
													/>
												) : (
													<div className="flex flex-wrap gap-1">
														{(col.aliases || []).map((alias) => (
															<span
																key={`${col.metadata_id}-${alias}`}
																className="px-1.5 py-0.5 rounded bg-dark-950 border border-dark-700 font-mono text-[10px] text-slate-300"
															>
																{alias}
															</span>
														))}
													</div>
												)}
											</td>

											<td className="px-4 py-3 text-right whitespace-nowrap">
												{isEditing ? (
													<div className="inline-flex items-center gap-1.5">
														<button
															type="button"
															disabled={isUpdating}
															onClick={() => void handleSaveEdit(col)}
															className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"
														>
															<Check className="w-3 h-3" aria-hidden="true" />
															Lưu thay đổi
														</button>
														<button
															type="button"
															onClick={cancelEdit}
															className="inline-flex items-center gap-1 px-2 py-1 rounded bg-dark-800 border border-dark-700 text-slate-300 hover:text-white text-xs"
														>
															<X className="w-3 h-3" aria-hidden="true" />
															Hủy
														</button>
													</div>
												) : (
													<div className="inline-flex items-center gap-1.5">
														<button
															type="button"
															data-testid={`edit-column-${col.column_key}`}
															onClick={() => startEdit(col)}
															className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-dark-800 border border-dark-700 text-slate-300 hover:text-white"
														>
															<Edit3 className="w-3 h-3" aria-hidden="true" />
															Sửa
														</button>
														<button
															type="button"
															data-testid={`delete-column-${col.column_key}`}
															disabled={isCore || isDeleting}
															onClick={() => void handleDelete(col)}
															title={
																isCore
																	? 'Không thể xóa cột hệ thống cốt lõi'
																	: `Xóa cột ${col.column_key}`
															}
															className={`inline-flex items-center gap-1 px-2.5 py-1 rounded border text-xs ${
																isCore
																	? 'bg-dark-900 border-dark-800 text-slate-600 cursor-not-allowed'
																	: 'bg-dark-800 border-dark-700 text-rose-400 hover:bg-rose-500/10'
															}`}
														>
															{isCore ? (
																<Lock className="w-3 h-3" aria-hidden="true" />
															) : (
																<Trash2 className="w-3 h-3" aria-hidden="true" />
															)}
															Xóa
														</button>
													</div>
												)}
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
	);
}

export default SystemMetadataAdminTab;
