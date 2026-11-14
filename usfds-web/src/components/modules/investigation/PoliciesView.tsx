import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import {
	AlertTriangle,
	ArrowRight,
	CheckCircle2,
	Plus,
	ShieldAlert,
	Sliders,
	Unlock,
} from 'lucide-react';
import { investigationApi } from '../../../api/investigationApi';
import type { EntityType } from '../../../types/investigation';
import {
	BUTTON_DANGER_CLASS,
	BUTTON_PRIMARY_CLASS,
	BUTTON_SECONDARY_CLASS,
	ENTITY_TYPES,
	ErrorNotice,
	FormField,
	INPUT_CLASS,
	ScoreBar,
	SectionCard,
	StatusBadge,
	formatDateTime,
	formatLabel,
	formatNumber,
} from './investigationShared';

export function PoliciesView({
	projectId,
	readOnly,
}: {
	projectId: string;
	readOnly: boolean;
}) {
	const queryClient = useQueryClient();
	const [searchParams, setSearchParams] = useSearchParams();
	const activeTab =
		searchParams.get('tab') === 'feedback' ? 'feedback' : 'blacklist';

	const [search, setSearch] = useState('');
	const [statusFilter, setStatusFilter] = useState('ACTIVE');
	const [typeFilter, setTypeFilter] = useState('');
	const [entityType, setEntityType] = useState<EntityType>('USER_ID');
	const [value, setValue] = useState('');
	const [reason, setReason] = useState('');
	const [removingId, setRemovingId] = useState<string | null>(null);
	const [removeReason, setRemoveReason] = useState('');

	const entriesQuery = useQuery({
		queryKey: ['investigation', projectId, 'blacklist'],
		queryFn: () => investigationApi.blacklist(projectId),
	});
	const feedbackQuery = useQuery({
		queryKey: ['investigation', projectId, 'feedback'],
		queryFn: () => investigationApi.feedback(projectId),
	});

	const addMutation = useMutation({
		mutationFn: () =>
			investigationApi.addBlacklist(projectId, entityType, value, reason),
		onSuccess: () => {
			setValue('');
			setReason('');
			void queryClient.invalidateQueries({
				queryKey: ['investigation', projectId],
			});
		},
	});

	const removeMutation = useMutation({
		mutationFn: () =>
			investigationApi.removeBlacklist(projectId, removingId!, removeReason),
		onSuccess: () => {
			setRemovingId(null);
			setRemoveReason('');
			void queryClient.invalidateQueries({
				queryKey: ['investigation', projectId],
			});
		},
	});

	const allEntries = entriesQuery.data || [];
	const activeBlacklistCount = allEntries.filter(
		(e) => e.status === 'ACTIVE'
	).length;
	const removedBlacklistCount = allEntries.filter(
		(e) => e.status === 'REMOVED'
	).length;
	const allFeedback = feedbackQuery.data || [];
	const noisyRuleCount = allFeedback.filter(
		(r) =>
			r.verified_false_positive_ratio != null &&
			r.verified_false_positive_ratio > 0.8
	).length;

	const filteredEntries = allEntries.filter(
		(entry) =>
			(!statusFilter || entry.status === statusFilter) &&
			(!typeFilter || entry.entity_type === typeFilter) &&
			`${entry.entity_type} ${entry.entity_value} ${entry.reason}`
				.toLowerCase()
				.includes(search.toLowerCase())
	);

	const switchTab = (nextTab: 'blacklist' | 'feedback') => {
		setSearchParams(nextTab === 'feedback' ? { tab: 'feedback' } : {});
	};

	return (
		<div className="space-y-5">
			<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<div className="flex items-start justify-between rounded-xl border border-dark-700/80 bg-dark-900 p-4">
					<div>
						<p className="text-xs text-slate-400">Thực thể đang bị chặn</p>
						<p className="mt-1 font-mono text-2xl font-bold text-slate-100">
							{formatNumber(activeBlacklistCount, 0)}
						</p>
						<p className="mt-0.5 text-[11px] text-slate-400">
							Đang thực thi trong danh sách đen của dự án
						</p>
					</div>
					<span className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-2.5 text-rose-400">
						<ShieldAlert size={18} aria-hidden="true" />
					</span>
				</div>
				<div className="flex items-start justify-between rounded-xl border border-dark-700/80 bg-dark-900 p-4">
					<div>
						<p className="text-xs text-slate-400">Unblocked / Historical</p>
						<p className="mt-1 font-mono text-2xl font-bold text-slate-100">
							{formatNumber(removedBlacklistCount, 0)}
						</p>
						<p className="mt-0.5 text-[11px] text-slate-400">
							Được giữ trong lịch sử kiểm toán
						</p>
					</div>
					<span className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-2.5 text-emerald-400">
						<CheckCircle2 size={18} aria-hidden="true" />
					</span>
				</div>
				<div className="flex items-start justify-between rounded-xl border border-dark-700/80 bg-dark-900 p-4">
					<div>
						<p className="text-xs text-slate-400">Luật trong vòng phản hồi</p>
						<p className="mt-1 font-mono text-2xl font-bold text-slate-100">
							{formatNumber(allFeedback.length, 0)}
						</p>
						<p className="mt-0.5 text-[11px] text-slate-400">
							Được kích hoạt qua các hồ sơ điều tra
						</p>
					</div>
					<span className="rounded-lg border border-sky-500/20 bg-sky-500/10 p-2.5 text-sky-400">
						<Sliders size={18} aria-hidden="true" />
					</span>
				</div>
				<div className="flex items-start justify-between rounded-xl border border-dark-700/80 bg-dark-900 p-4">
					<div>
						<p className="text-xs text-slate-400">Luật nhiễu (FPR &gt; 80%)</p>
						<p className="mt-1 font-mono text-2xl font-bold text-slate-100">
							{formatNumber(noisyRuleCount, 0)}
						</p>
						<p className="mt-0.5 text-[11px] text-slate-400">
							Nên điều chỉnh ngưỡng
						</p>
					</div>
					<span className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-2.5 text-amber-400">
						<AlertTriangle size={18} aria-hidden="true" />
					</span>
				</div>
			</div>

			<div
				role="tablist"
				aria-label="Chính sách điều tra"
				className="flex gap-2 border-b border-dark-700/80"
			>
				<button
					role="tab"
					aria-selected={activeTab === 'blacklist'}
					className={`border-b-2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors cursor-pointer ${
						activeTab === 'blacklist'
							? 'border-brand-400 text-brand-300'
							: 'border-transparent text-slate-400 hover:text-slate-200'
					}`}
					onClick={() => switchTab('blacklist')}
				>
					Danh sách đen thực thể ({activeBlacklistCount} đang hoạt động)
				</button>
				<button
					role="tab"
					aria-selected={activeTab === 'feedback'}
					className={`border-b-2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors cursor-pointer ${
						activeTab === 'feedback'
							? 'border-brand-400 text-brand-300'
							: 'border-transparent text-slate-400 hover:text-slate-200'
					}`}
					onClick={() => switchTab('feedback')}
				>
					Phản hồi điều tra theo luật ({allFeedback.length})
				</button>
			</div>

			<ErrorNotice
				error={
					entriesQuery.error ||
					feedbackQuery.error ||
					addMutation.error ||
					removeMutation.error
				}
			/>

			{activeTab === 'blacklist' ? (
				<div className="space-y-4">
					<SectionCard
						title="Thêm thực thể vào danh sách đen"
						subtitle="Chặn người dùng, thẻ, thiết bị, địa chỉ IP hoặc đơn vị bán hàng móc nối bị xâm phạm (BUC-07)"
					>
						<form
							className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
							onSubmit={(event) => {
								event.preventDefault();
								addMutation.mutate();
							}}
						>
							<FormField name="Loại thực thể">
								<select
									className={INPUT_CLASS}
									value={entityType}
									onChange={(event) =>
										setEntityType(event.target.value as EntityType)
									}
								>
									{ENTITY_TYPES.map((kind) => (
										<option key={kind} value={kind}>
											{kind}
										</option>
									))}
								</select>
							</FormField>
							<FormField name="Giá trị định danh thực thể">
								<input
									className={INPUT_CLASS}
									value={value}
									maxLength={255}
									required
									placeholder="e.g. usr_1092, dev_88a..."
									onChange={(event) => setValue(event.target.value)}
								/>
							</FormField>
							<FormField name="Lý do chặn" hint="Tối thiểu 10 ký tự">
								<input
									className={INPUT_CLASS}
									value={reason}
									minLength={10}
									maxLength={10000}
									required
									placeholder="Lý do chặn thực thể..."
									onChange={(event) => setReason(event.target.value)}
								/>
							</FormField>
							<button
								type="submit"
								className={`${BUTTON_DANGER_CLASS} self-end`}
								disabled={
									readOnly ||
									addMutation.isPending ||
									!value.trim() ||
									reason.trim().length < 10
								}
							>
								<Plus size={15} />
								<span>Thêm vào danh sách đen</span>
							</button>
						</form>
					</SectionCard>

					{removingId && (
						<SectionCard
							title="Xác nhận gỡ khỏi danh sách đen"
							subtitle="Gỡ thực thể sẽ giữ bản ghi với trạng thái REMOVED trong nhật ký kiểm toán"
						>
							<form
								className="flex flex-col gap-3 sm:flex-row sm:items-end"
								onSubmit={(event) => {
									event.preventDefault();
									removeMutation.mutate();
								}}
							>
								<div className="flex-1">
									<FormField name="Lý do gỡ" hint="Bắt buộc tối thiểu 10 ký tự">
										<input
											className={INPUT_CLASS}
											required
											minLength={10}
											placeholder="Giải thích vì sao thực thể này được gỡ chặn..."
											value={removeReason}
											onChange={(event) => setRemoveReason(event.target.value)}
										/>
									</FormField>
								</div>
								<button
									type="submit"
									className={BUTTON_PRIMARY_CLASS}
									disabled={
										removeMutation.isPending ||
										removeReason.trim().length < 10 ||
										readOnly
									}
								>
									<Unlock size={14} />
									<span>Xác nhận gỡ</span>
								</button>
								<button
									type="button"
									className={BUTTON_SECONDARY_CLASS}
									onClick={() => setRemovingId(null)}
								>
									Hủy
								</button>
							</form>
						</SectionCard>
					)}

					<SectionCard
						title="Sổ danh sách đen thực thể"
						subtitle={`Đang hiển thị ${filteredEntries.length} mục khớp`}
					>
						<div className="grid gap-3 sm:grid-cols-3">
							<FormField name="Tìm trong danh sách đen">
								<input
									className={INPUT_CLASS}
									placeholder="Tìm theo giá trị hoặc lý do..."
									value={search}
									onChange={(event) => setSearch(event.target.value)}
								/>
							</FormField>
							<FormField name="Lọc loại thực thể">
								<select
									className={INPUT_CLASS}
									value={typeFilter}
									onChange={(event) => setTypeFilter(event.target.value)}
								>
									<option value="">Tất cả loại thực thể</option>
									{ENTITY_TYPES.map((kind) => (
										<option key={kind} value={kind}>
											{kind}
										</option>
									))}
								</select>
							</FormField>
							<FormField name="Trạng thái mục">
								<select
									className={INPUT_CLASS}
									value={statusFilter}
									onChange={(event) => setStatusFilter(event.target.value)}
								>
									<option value="">Tất cả trạng thái</option>
									<option value="ACTIVE">ACTIVE</option>
									<option value="REMOVED">REMOVED</option>
								</select>
							</FormField>
						</div>

						<div className="overflow-x-auto pt-2">
							<table className="w-full min-w-[720px] text-left text-xs">
								<caption className="sr-only">Danh sách đen thực thể</caption>
								<thead className="border-b border-dark-700/80 text-[11px] uppercase text-slate-400">
									<tr>
										<th scope="col" className="py-3 pr-3">Loại &amp; giá trị thực thể</th>
										<th scope="col" className="py-3 pr-3">Trạng thái</th>
										<th scope="col" className="py-3 pr-3">Lý do &amp; hồ sơ nguồn</th>
										<th scope="col" className="py-3 pr-3">Siêu dữ liệu kiểm toán</th>
										<th scope="col" className="py-3 text-right">Thao tác</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800">
									{filteredEntries.map((entry) => (
										<tr key={entry.blacklist_id} className="hover:bg-dark-850/40">
											<td className="max-w-56 break-all py-3 pr-3">
												<span className="text-[11px] font-semibold text-slate-400">
													{formatLabel(entry.entity_type)}
												</span>
												<p className="mt-0.5 font-mono font-bold text-slate-100">
													{entry.entity_value}
												</p>
											</td>
											<td className="py-3 pr-3">
												<StatusBadge value={entry.status} />
											</td>
											<td className="max-w-80 break-words py-3 pr-3 text-slate-200">
												<p>{entry.reason}</p>
												{entry.source_case_id && (
													<Link
														className="mt-1 inline-block font-mono text-[11px] text-brand-400 hover:underline"
														to={`/investigation/cases/${entry.source_case_id}`}
													>
														Xem hồ sơ nguồn &rarr;
													</Link>
												)}
											</td>
											<td className="py-3 pr-3 text-[11px] text-slate-400">
												<p>
													Added by <strong className="text-slate-300">{entry.created_by}</strong>{' '}
													({formatDateTime(entry.created_at)})
												</p>
												{entry.removed_at && (
													<p className="mt-0.5 text-slate-500">
														Gỡ bởi {entry.removed_by} ({formatDateTime(entry.removed_at)})
													</p>
												)}
											</td>
											<td className="py-3 text-right">
												{entry.status === 'ACTIVE' && (
													<button
														type="button"
														className={BUTTON_SECONDARY_CLASS}
														disabled={readOnly || removeMutation.isPending}
														onClick={() => {
															setRemovingId(entry.blacklist_id);
															setRemoveReason('');
														}}
													>
														<Unlock size={14} />
														<span>Gỡ</span>
													</button>
												)}
											</td>
										</tr>
									))}
								</tbody>
							</table>
							{entriesQuery.isPending ? (
								<p role="status" className="py-6 text-center text-sm text-slate-400">
									Đang tải danh sách đen thực thể...
								</p>
							) : (
								!filteredEntries.length &&
								!entriesQuery.error && (
									<p className="py-6 text-center text-sm text-slate-400">
										Không có mục danh sách đen nào khớp bộ lọc hiện tại.
									</p>
								)
							)}
						</div>
					</SectionCard>
				</div>
			) : (
				<SectionCard
					title="Bảng phản hồi xác minh luật"
					subtitle="Đánh giá độ chính xác thực tế của luật dựa trên dữ liệu xác minh bởi chuyên viên (SUC-18 -> SUC-20)"
				>
					<div className="overflow-x-auto">
						<table className="w-full min-w-[740px] text-left text-xs">
							<caption className="sr-only">Verified rule feedback by version</caption>
							<thead className="border-b border-dark-700/80 text-[11px] uppercase text-slate-400">
								<tr>
									<th scope="col" className="py-3 pr-3">Phiên bản luật</th>
									<th scope="col" className="py-3 pr-3">Số hồ sơ được kích hoạt</th>
									<th scope="col" className="py-3 pr-3">Gian lận đã xác nhận (TP)</th>
									<th scope="col" className="py-3 pr-3">Cảnh báo sai (FP)</th>
									<th scope="col" className="py-3 pr-3">Đang chờ xem xét</th>
									<th scope="col" className="py-3 pr-3">Tỷ lệ FPR đã xác minh %</th>
									<th scope="col" className="py-3 text-right">Thao tác</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-dark-800">
								{allFeedback.map((row) => {
									const isNoisy =
										row.verified_false_positive_ratio != null &&
										row.verified_false_positive_ratio > 0.8;
									return (
										<tr
											key={row.rule_version_id}
											className={isNoisy ? 'bg-rose-950/15' : 'hover:bg-dark-850/40'}
										>
											<td className="py-3 pr-3 font-mono font-semibold text-slate-100">
												{row.rule_code} / v{row.version_number}
												{isNoisy && (
													<span className="ml-2 inline-flex items-center gap-1 rounded border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-sans uppercase text-rose-300">
														<AlertTriangle size={11} />
														<span>Nhiều nhiễu</span>
													</span>
												)}
											</td>
											<td className="py-3 pr-3 font-mono tabular-nums">
												{row.cases_triggered}
											</td>
											<td className="py-3 pr-3 font-mono font-semibold tabular-nums text-emerald-400">
												{row.tp}
											</td>
											<td className="py-3 pr-3 font-mono font-semibold tabular-nums text-rose-400">
												{row.fp}
											</td>
											<td className="py-3 pr-3 font-mono tabular-nums text-amber-300">
												{row.pending}
											</td>
											<td className="w-44 py-3 pr-3">
												<ScoreBar score={row.verified_false_positive_ratio} />
											</td>
											<td className="py-3 text-right">
												<Link
													className={BUTTON_SECONDARY_CLASS}
													to={`/rules/${row.rule_id}/step-builder`}
												>
													<span>Điều chỉnh luật</span>
													<ArrowRight size={14} />
												</Link>
											</td>
										</tr>
									);
								})}
							</tbody>
						</table>
						{feedbackQuery.isPending ? (
							<p role="status" className="py-6 text-center text-sm text-slate-400">
								Đang tải phản hồi xác minh luật...
							</p>
						) : (
							!allFeedback.length &&
							!feedbackQuery.error && (
								<p className="py-6 text-center text-sm text-slate-400">
									Chưa có phản hồi xác minh luật.
								</p>
							)
						)}
					</div>
				</SectionCard>
			)}
		</div>
	);
}

