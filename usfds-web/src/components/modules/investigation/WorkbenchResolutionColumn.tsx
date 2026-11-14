import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
	ArrowUpRight,
	CheckCircle2,
	ClipboardCheck,
	FilePlus2,
	Save,
	ShieldAlert,
	Unlock,
	UserCheck,
} from 'lucide-react';
import type { CaseAction, EntityType, Workbench } from '../../../types/investigation';
import {
	BUTTON_DANGER_CLASS,
	BUTTON_PRIMARY_CLASS,
	BUTTON_SECONDARY_CLASS,
	ENTITY_TYPES,
	FRAUD_REASONS,
	FormField,
	INPUT_CLASS,
	LEGITIMATE_REASONS,
	SectionCard,
	StatusBadge,
	formatDateTime,
	formatLabel,
} from './investigationShared';

export function DecisionAndAuditColumn({
	data,
	disabled,
	draftPending,
	onMutate,
	onCreateRuleDraft,
}: {
	data: Workbench;
	disabled: boolean;
	draftPending: boolean;
	onMutate: (action: string, payload: CaseAction, noteText?: string) => void;
	onCreateRuleDraft: () => void;
}) {
	const { case: item, audit_logs: logs } = data;
	const isResolved = item.status.startsWith('RESOLVED');

	const [verdict, setVerdict] = useState<'FRAUD' | 'LEGITIMATE'>('FRAUD');
	const [reason, setReason] = useState('');
	const [resolutionSummary, setResolutionSummary] = useState('');
	const [blocked, setBlocked] = useState<EntityType[]>(['USER_ID']);

	const [workflowNote, setWorkflowNote] = useState('');
	const [assignee, setAssignee] = useState('');
	const [investigationNote, setInvestigationNote] = useState('');

	const entities = ENTITY_TYPES.map((entityType) => ({
		entity_type: entityType,
		entity_value:
			entityType === 'USER_ID'
				? item.user_id
				: String(item.attributes[entityType.toLowerCase()] ?? ''),
	})).filter((entity) => Boolean(entity.entity_value));

	const handleResolveSubmit = (event: React.FormEvent) => {
		event.preventDefault();
		onMutate('resolve', {
			expected_version: item.version,
			verdict,
			reason,
			summary: resolutionSummary,
			block_entities:
				verdict === 'FRAUD'
					? entities.filter((entity) => blocked.includes(entity.entity_type))
					: [],
		});
		setResolutionSummary('');
	};

	const handleReopen = () => {
		onMutate('reopen', {
			expected_version: item.version,
			summary: resolutionSummary,
		});
		setResolutionSummary('');
	};

	const handlePendingCustomer = () => {
		onMutate('pending-customer', {
			expected_version: item.version,
			summary: workflowNote,
		});
		setWorkflowNote('');
	};

	const handleEscalate = () => {
		onMutate('escalate', {
			expected_version: item.version,
			summary: workflowNote,
			assignee,
		});
		setWorkflowNote('');
	};

	const handleAddNote = (event: React.FormEvent) => {
		event.preventDefault();
		onMutate('note', { expected_version: item.version }, investigationNote);
		setInvestigationNote('');
	};

	return (
		<div className="min-w-0 space-y-4">
			<SectionCard
				title="Xử lý & giảm thiểu hồ sơ"
				subtitle={
					isResolved
						? 'Đã ghi kết luận kiểm toán cuối cùng & nhãn thực tế'
						: 'Ghi kết luận cuối, nhãn thực tế và chặn thực thể khẩn cấp'
				}
			>
				{isResolved ? (
					<div className="space-y-3 text-xs">
						<div className="rounded-lg border border-dark-700/80 bg-dark-950 p-3 space-y-2">
							<div className="flex items-center justify-between gap-2">
								<span className="text-[11px] text-slate-400">Trạng thái kết luận</span>
								<StatusBadge value={item.status} />
							</div>
							<div className="flex items-center justify-between gap-2">
								<span className="text-[11px] text-slate-400">Reason Code</span>
								<span className="font-mono font-semibold text-slate-100">
									{formatLabel(item.resolution_reason || '--')}
								</span>
							</div>
							<div className="flex items-center justify-between gap-2">
								<span className="text-[11px] text-slate-400">Ground Truth Label</span>
								<span className="rounded border border-dark-700 bg-dark-900 px-2 py-0.5 font-mono font-bold text-slate-100">
									verified_label = {item.verified_label}
								</span>
							</div>
							<div className="border-t border-dark-800 pt-2">
								<p className="text-[11px] text-slate-400">Tóm tắt bằng chứng</p>
								<p className="mt-1 break-words text-slate-200">
									{item.resolution_summary}
								</p>
							</div>
							<p className="text-[11px] text-slate-400">
								Resolved by <strong className="text-slate-200">{item.resolved_by}</strong> on{' '}
								{formatDateTime(item.resolved_at)}
							</p>
						</div>

						<div className="flex flex-wrap gap-2">
							{item.status === 'RESOLVED_FRAUD' && (
								<button
									type="button"
									className={BUTTON_PRIMARY_CLASS}
									disabled={draftPending || disabled}
									onClick={onCreateRuleDraft}
								>
									<FilePlus2 size={14} />
									<span>Tạo luật từ hồ sơ</span>
								</button>
							)}
							<Link
								to={`/reports?tab=compliance&caseId=${item.case_id}`}
								className={BUTTON_SECONDARY_CLASS}
							>
								<span>Xuất hồ sơ SAR</span>
								<ArrowUpRight size={14} />
							</Link>
							{item.status === 'RESOLVED_LEGITIMATE' && item.triggered_rules.length > 0 && (
								<Link
									to="/investigation/policies?tab=feedback"
									className={BUTTON_SECONDARY_CLASS}
								>
									<span>Xem lại luật nhiễu</span>
									<ArrowUpRight size={14} />
								</Link>
							)}
						</div>

						<div className="space-y-2.5 border-t border-dark-800 pt-3">
							<FormField name="Lý do mở lại" hint="Tối thiểu 10 ký tự (BR-IV-02)">
								<textarea
									className={INPUT_CLASS}
									rows={2}
									placeholder="Giải thích vì sao hồ sơ đã xử lý này cần mở lại..."
									value={resolutionSummary}
									onChange={(event) => setResolutionSummary(event.target.value)}
								/>
							</FormField>
							<button
								type="button"
								className={BUTTON_SECONDARY_CLASS}
								disabled={disabled || resolutionSummary.trim().length < 10}
								onClick={handleReopen}
							>
								<Unlock size={14} />
								<span>Mở lại hồ sơ</span>
							</button>
						</div>
					</div>
				) : (
					<div className="space-y-3.5">
						{item.assigned_to !== 'local-analyst' && (
							<button
								type="button"
								className={`${BUTTON_SECONDARY_CLASS} w-full`}
								disabled={disabled}
								onClick={() =>
									onMutate('claim', { expected_version: item.version })
								}
							>
								<UserCheck size={14} />
								<span>Nhận / giao cho tôi</span>
							</button>
						)}

						<form className="space-y-3" onSubmit={handleResolveSubmit}>
							<div
								role="group"
								aria-label="Chọn kết luận xử lý"
								className="grid grid-cols-2 gap-2 rounded-lg border border-dark-700 bg-dark-950 p-1"
							>
								<button
									type="button"
									onClick={() => {
										setVerdict('FRAUD');
										setReason('');
									}}
									className={`flex items-center justify-center gap-1.5 rounded-md px-2.5 py-2 text-xs font-semibold transition-colors cursor-pointer ${
										verdict === 'FRAUD'
											? 'bg-rose-600 text-white shadow-sm'
											: 'text-slate-300 hover:text-slate-100'
									}`}
								>
									<ShieldAlert size={14} aria-hidden="true" />
									<span>Xác nhận gian lận</span>
								</button>
								<button
									type="button"
									onClick={() => {
										setVerdict('LEGITIMATE');
										setReason('');
									}}
									className={`flex items-center justify-center gap-1.5 rounded-md px-2.5 py-2 text-xs font-semibold transition-colors cursor-pointer ${
										verdict === 'LEGITIMATE'
											? 'bg-emerald-600 text-white shadow-sm'
											: 'text-slate-300 hover:text-slate-100'
									}`}
								>
									<CheckCircle2 size={14} aria-hidden="true" />
									<span>Đánh dấu hợp lệ</span>
								</button>
							</div>

							<FormField
								name={
									verdict === 'FRAUD'
										? 'Mã loại hình gian lận'
										: 'Lý do cảnh báo sai'
								}
							>
								<select
									aria-label="Lý do xử lý"
									className={INPUT_CLASS}
									value={reason}
									required
									onChange={(event) => setReason(event.target.value)}
								>
									<option value="">Chọn lý do</option>
									{(verdict === 'FRAUD' ? FRAUD_REASONS : LEGITIMATE_REASONS).map(
										(value) => (
											<option key={value} value={value}>
												{formatLabel(value)}
											</option>
										)
									)}
								</select>
							</FormField>

							<FormField name="Tóm tắt bằng chứng" hint="Tối thiểu 10 ký tự (BR-IV-03)">
								<textarea
									aria-label="Tóm tắt bằng chứng"
									className={INPUT_CLASS}
									rows={3}
									value={resolutionSummary}
									required
									minLength={10}
									maxLength={10000}
									placeholder="Tóm tắt kết quả điều tra phục vụ kiểm toán & tuân thủ SAR..."
									onChange={(event) => setResolutionSummary(event.target.value)}
								/>
							</FormField>

							{verdict === 'FRAUD' ? (
								<fieldset className="space-y-2 rounded-lg border border-dark-800 bg-dark-950/60 p-3 text-xs">
									<legend className="px-1 text-[11px] font-semibold uppercase tracking-wide text-slate-300">
										Giảm thiểu khẩn cấp (chặn thực thể)
									</legend>
									{entities.map((entity) => (
										<label
											key={entity.entity_type}
											className="flex items-start gap-2 break-all text-slate-200 cursor-pointer"
										>
											<input
												type="checkbox"
												className="mt-0.5 rounded border-dark-600"
												checked={blocked.includes(entity.entity_type)}
												onChange={(event) =>
													setBlocked(
														event.target.checked
															? [...blocked, entity.entity_type]
															: blocked.filter((value) => value !== entity.entity_type)
													)
												}
											/>
											<span>
												<strong className="font-mono text-[11px] text-slate-300">
													{formatLabel(entity.entity_type)}:
												</strong>{' '}
												<span className="font-mono">{entity.entity_value}</span>
											</span>
										</label>
									))}
								</fieldset>
							) : (
								item.triggered_rules.length > 0 && (
									<div className="flex items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-950/20 p-2.5 text-xs text-amber-200">
										<span>Luật đã kích hoạt gây cảnh báo sai?</span>
										<Link
											to="/investigation/policies?tab=feedback"
											className="inline-flex items-center gap-1 font-semibold text-amber-300 hover:underline"
										>
											<span>Gắn cờ luật nhiễu</span>
											<ArrowUpRight size={13} />
										</Link>
									</div>
								)
							)}

							<button
								className={
									verdict === 'FRAUD'
										? `${BUTTON_DANGER_CLASS} w-full`
										: `${BUTTON_PRIMARY_CLASS} w-full`
								}
								type="submit"
								disabled={
									disabled || !reason || resolutionSummary.trim().length < 10
								}
							>
								<CheckCircle2 size={14} />
								<span>
									{verdict === 'FRAUD'
										? 'Gửi xác nhận gian lận'
										: 'Gửi xác nhận hợp lệ (cảnh báo sai)'}
								</span>
							</button>
						</form>
					</div>
				)}
			</SectionCard>

			{!isResolved && (
				<SectionCard
					title="Xác minh khách hàng & leo thang"
					subtitle="Ghi trạng thái liên hệ khách hàng (BUC-06) hoặc chuyển cho chuyên viên cấp cao"
				>
					<FormField name="Ghi chú xác minh / leo thang" hint="Tối thiểu 10 ký tự">
						<textarea
							className={INPUT_CLASS}
							rows={2}
							placeholder="Nhập kết quả liên hệ khách hàng hoặc lý do leo thang..."
							value={workflowNote}
							onChange={(event) => setWorkflowNote(event.target.value)}
						/>
					</FormField>
					<button
						type="button"
						className={`${BUTTON_SECONDARY_CLASS} w-full`}
						disabled={disabled || workflowNote.trim().length < 10}
						onClick={handlePendingCustomer}
					>
						<ClipboardCheck size={14} />
						<span>Đánh dấu chờ phản hồi khách hàng</span>
					</button>

					<div className="space-y-2 border-t border-dark-800 pt-2.5">
						<FormField name="Người được giao leo thang">
							<input
								className={INPUT_CLASS}
								maxLength={100}
								placeholder="e.g. senior-risk-manager"
								value={assignee}
								onChange={(event) => setAssignee(event.target.value)}
							/>
						</FormField>
						<button
							type="button"
							className={`${BUTTON_SECONDARY_CLASS} w-full`}
							disabled={
								disabled ||
								!assignee.trim() ||
								workflowNote.trim().length < 10
							}
							onClick={handleEscalate}
						>
							<ShieldAlert size={14} />
							<span>Leo thang lên mức ưu tiên nghiêm trọng</span>
						</button>
					</div>
				</SectionCard>
			)}

			<SectionCard
				title="Ghi chú điều tra"
				subtitle="Thêm quan sát có dấu thời gian vào nhật ký kiểm toán"
			>
				<form className="space-y-2.5" onSubmit={handleAddNote}>
					<FormField name="Ghi chú">
						<textarea
							className={INPUT_CLASS}
							rows={2}
							maxLength={10000}
							required
							placeholder="Thêm ghi chú điều tra nội bộ..."
							value={investigationNote}
							onChange={(event) => setInvestigationNote(event.target.value)}
						/>
					</FormField>
					<button
						type="submit"
						className={BUTTON_SECONDARY_CLASS}
						disabled={disabled || !investigationNote.trim()}
					>
						<Save size={14} />
						<span>Thêm ghi chú</span>
					</button>
				</form>
			</SectionCard>

			<SectionCard
				title={`Nhật ký kiểm toán (${logs.length})`}
				subtitle="Nhật ký bất biến về chuyển trạng thái & thao tác của hồ sơ"
			>
				<ol className="max-h-72 space-y-3 overflow-y-auto pr-1">
					{logs.map((log) => (
						<li
							key={log.log_id}
							className="rounded-lg border border-dark-800 bg-dark-950/60 p-3 text-xs space-y-1"
						>
							<div className="flex items-center justify-between gap-2">
								<span className="font-mono font-semibold text-brand-300">
									{formatLabel(log.action)}
								</span>
								<span className="text-[11px] text-slate-400">
									{formatDateTime(log.created_at)}
								</span>
							</div>
							<p className="font-mono text-[11px] text-slate-400">
								Actor: {log.actor}
							</p>
							{log.note && (
								<p className="break-words text-slate-200">{log.note}</p>
							)}
							{Object.keys(log.details || {}).length > 0 && (
								<details className="pt-1">
									<summary className="cursor-pointer text-[11px] font-medium text-brand-400 hover:underline">
										Kiểm tra khác biệt siêu dữ liệu
									</summary>
									<pre className="mt-1.5 max-h-36 overflow-auto rounded border border-dark-800 bg-dark-900 p-2 font-mono text-[11px] text-slate-300">
										{JSON.stringify(log.details, null, 2)}
									</pre>
								</details>
							)}
						</li>
					))}
				</ol>
			</SectionCard>
		</div>
	);
}

