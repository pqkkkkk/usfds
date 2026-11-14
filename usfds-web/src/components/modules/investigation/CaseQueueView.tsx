import { useDeferredValue, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
	AlertTriangle,
	ArrowLeft,
	ArrowRight,
	ArrowUpRight,
	Briefcase,
	CheckCircle2,
	ClipboardCheck,
	Filter,
	RefreshCw,
	RotateCcw,
	UserCheck,
} from 'lucide-react';
import { investigationApi } from '../../../api/investigationApi';
import type { Case } from '../../../types/investigation';
import {
	BUTTON_PRIMARY_CLASS,
	BUTTON_SECONDARY_CLASS,
	CASE_STATUSES,
	ErrorNotice,
	FormField,
	INPUT_CLASS,
	ScoreBar,
	SectionCard,
	StatusBadge,
	formatCurrencyAmount,
	formatDateTime,
	formatNumber,
	formatPercent,
} from './investigationShared';

const INITIAL_FILTERS: Record<string, string> = {
	status: '',
	priority: '',
	assigned_to: '',
	rule_code: '',
	min_score: '',
	max_score: '',
	min_amount: '',
	max_amount: '',
	q: '',
	sort: 'priority',
};

export function CaseQueueView({
	projectId,
	readOnly,
}: {
	projectId: string;
	readOnly: boolean;
}) {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [searchParams, setSearchParams] = useSearchParams();
	const [filters, setFilters] = useState<Record<string, string>>(INITIAL_FILTERS);
	const [page, setPage] = useState(1);
	const deferredFilters = useDeferredValue(filters);

	const userFilterParam = searchParams.get('user') || '';
	const queryFilters: Record<string, unknown> = { page, size: 50 };
	if (userFilterParam) {
		queryFilters.user_id = userFilterParam;
	}
	for (const [key, value] of Object.entries(deferredFilters)) {
		if (value) {
			queryFilters[key] =
				key.startsWith('min_') || key.startsWith('max_') ? Number(value) : value;
		}
	}
	if (queryFilters.assigned_to === 'unassigned') {
		delete queryFilters.assigned_to;
		queryFilters.unassigned = true;
	}

	const casesQuery = useQuery({
		queryKey: ['investigation', projectId, 'queue', queryFilters],
		queryFn: () => investigationApi.list(projectId, queryFilters),
	});
	const kpisQuery = useQuery({
		queryKey: ['investigation', projectId, 'kpis'],
		queryFn: () => investigationApi.kpis(projectId),
	});
	const claimMutation = useMutation({
		mutationFn: (item: Case) =>
			investigationApi.action(projectId, item.case_id, 'claim', {
				expected_version: item.version,
			}),
		onSuccess: (result) => {
			void queryClient.invalidateQueries({ queryKey: ['investigation', projectId] });
			navigate(`/investigation/cases/${result.case.case_id}`);
		},
		onError: () => {
			void casesQuery.refetch();
		},
	});

	const handleFilterChange = (key: string, value: string) => {
		setFilters((prev) => ({ ...prev, [key]: value }));
		setPage(1);
	};

	const handleResetFilters = () => {
		setFilters(INITIAL_FILTERS);
		setPage(1);
		if (userFilterParam) {
			setSearchParams({});
		}
	};

	const kpiItems = [
		{
			label: 'Hồ sơ đang mở',
			value: formatNumber(kpisQuery.data?.open, 0),
			subtext: 'Đang chờ chuyên viên phân loại',
			icon: Briefcase,
			accent: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
		},
		{
			label: 'Nghiêm trọng chưa xử lý',
			value: formatNumber(kpisQuery.data?.critical, 0),
			subtext: 'Cần điều tra ngay',
			icon: AlertTriangle,
			accent: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
		},
		{
			label: 'Đang xử lý',
			value: formatNumber(kpisQuery.data?.in_progress, 0),
			subtext: `Chờ khách hàng: ${formatNumber(kpisQuery.data?.pending_customer, 0)}`,
			icon: ClipboardCheck,
			accent: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
		},
		{
			label: 'Tỷ lệ gian lận đã xác nhận',
			value: formatPercent(kpisQuery.data?.confirmed_fraud_ratio),
			subtext: `Tổng đã xử lý: ${formatNumber(kpisQuery.data?.resolved, 0)} hồ sơ`,
			icon: CheckCircle2,
			accent: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
		},
	];

	return (
		<div className="space-y-5">
			<div
				className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
				aria-label="Thống kê hồ sơ"
			>
				{kpiItems.map((card) => {
					const Icon = card.icon;
					return (
						<div
							key={card.label}
							className="flex items-start justify-between rounded-xl border border-dark-700/80 bg-dark-900 p-4 shadow-sm"
						>
							<div className="min-w-0 space-y-1">
								<p className="text-xs font-medium text-slate-400">{card.label}</p>
								<p className="font-mono text-2xl font-bold tabular-nums text-slate-100">
									{card.value}
								</p>
								<p className="text-[11px] text-slate-400">{card.subtext}</p>
							</div>
							<span className={`rounded-lg border p-2.5 ${card.accent}`}>
								<Icon size={18} aria-hidden="true" />
							</span>
						</div>
					);
				})}
			</div>

			<ErrorNotice error={casesQuery.error || kpisQuery.error || claimMutation.error} />

			<SectionCard
				title="Bộ lọc hàng đợi đa chiều"
				subtitle={
					userFilterParam
						? `Đang lọc hồ sơ theo ID người dùng liên quan: ${userFilterParam}`
						: 'Thu hẹp hồ sơ theo mức ưu tiên, trạng thái, mã luật, điểm mô hình hoặc số tiền giao dịch'
				}
				badge={<Filter size={14} className="text-slate-400" aria-hidden="true" />}
				actions={
					<div className="flex items-center gap-2">
						<button
							type="button"
							className={BUTTON_SECONDARY_CLASS}
							onClick={handleResetFilters}
						>
							<RotateCcw size={14} />
							<span>Đặt lại</span>
						</button>
						<button
							type="button"
							className={BUTTON_SECONDARY_CLASS}
							disabled={casesQuery.isFetching}
							onClick={() => {
								void queryClient.invalidateQueries({ queryKey: ['investigation', projectId] });
							}}
						>
							<RefreshCw size={14} className={casesQuery.isFetching ? 'animate-spin' : ''} />
							<span>Làm mới</span>
						</button>
					</div>
				}
			>
				<div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 lg:grid-cols-5">
					<FormField name="Tìm kiếm (hồ sơ / sự kiện / người dùng)">
						<input
							className={INPUT_CLASS}
							placeholder="CASE-2026-..., evt_..., usr_..."
							value={filters.q}
							onChange={(event) => handleFilterChange('q', event.target.value)}
						/>
					</FormField>
					<FormField name="Trạng thái">
						<select
							className={INPUT_CLASS}
							value={filters.status}
							onChange={(event) => handleFilterChange('status', event.target.value)}
						>
							<option value="">Tất cả trạng thái</option>
							{CASE_STATUSES.map((status) => (
								<option key={status} value={status}>
									{status}
								</option>
							))}
						</select>
					</FormField>
					<FormField name="Mức ưu tiên">
						<select
							className={INPUT_CLASS}
							value={filters.priority}
							onChange={(event) => handleFilterChange('priority', event.target.value)}
						>
							<option value="">Tất cả mức ưu tiên</option>
							{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((priority) => (
								<option key={priority} value={priority}>
									{priority}
								</option>
							))}
						</select>
					</FormField>
					<FormField name="Phân công">
						<select
							className={INPUT_CLASS}
							value={filters.assigned_to}
							onChange={(event) => handleFilterChange('assigned_to', event.target.value)}
						>
							<option value="">Tất cả chuyên viên</option>
							<option value="local-analyst">Được giao cho tôi (local-analyst)</option>
							<option value="unassigned">Chỉ hồ sơ chưa giao</option>
						</select>
					</FormField>
					<FormField name="Mã luật đã kích hoạt">
						<input
							className={INPUT_CLASS}
							placeholder="e.g. R-001"
							value={filters.rule_code}
							onChange={(event) => handleFilterChange('rule_code', event.target.value)}
						/>
					</FormField>
					<FormField name="Điểm mô hình tối thiểu" hint="0.00 - 1.00">
						<input
							type="number"
							min="0"
							max="1"
							step="0.01"
							placeholder="0.00"
							className={INPUT_CLASS}
							value={filters.min_score}
							onChange={(event) => handleFilterChange('min_score', event.target.value)}
						/>
					</FormField>
					<FormField name="Điểm mô hình tối đa" hint="0.00 - 1.00">
						<input
							type="number"
							min="0"
							max="1"
							step="0.01"
							placeholder="1.00"
							className={INPUT_CLASS}
							value={filters.max_score}
							onChange={(event) => handleFilterChange('max_score', event.target.value)}
						/>
					</FormField>
					<FormField name="Số tiền tối thiểu">
						<input
							type="number"
							min="0"
							step="any"
							placeholder="0.00"
							className={INPUT_CLASS}
							value={filters.min_amount}
							onChange={(event) => handleFilterChange('min_amount', event.target.value)}
						/>
					</FormField>
					<FormField name="Số tiền tối đa">
						<input
							type="number"
							min="0"
							step="any"
							placeholder="Bất kỳ"
							className={INPUT_CLASS}
							value={filters.max_amount}
							onChange={(event) => handleFilterChange('max_amount', event.target.value)}
						/>
					</FormField>
					<FormField name="Thứ tự sắp xếp">
						<select
							className={INPUT_CLASS}
							value={filters.sort}
							onChange={(event) => handleFilterChange('sort', event.target.value)}
						>
							<option value="priority">Điểm ưu tiên giảm dần</option>
							<option value="amount">Số tiền giao dịch giảm dần</option>
							<option value="created">Mới tạo nhất trước</option>
						</select>
					</FormField>
				</div>
			</SectionCard>

			<div className="overflow-hidden rounded-xl border border-dark-700/80 bg-dark-900 shadow-sm">
				<div className="flex flex-wrap items-center justify-between gap-2 border-b border-dark-700/80 bg-dark-850/50 px-4 py-3 text-xs text-slate-300">
					<span className="font-medium">
						Showing <strong className="font-mono text-slate-100">{casesQuery.data?.items.length ?? 0}</strong> of{' '}
						<strong className="font-mono text-slate-100">{formatNumber(casesQuery.data?.total, 0)}</strong> cases
					</span>
					<span className="text-[11px] text-slate-400">
						Nhấp vào mã hồ sơ hoặc Điều tra để mở không gian làm việc 3 cột
					</span>
				</div>

				<div className="overflow-x-auto" aria-busy={casesQuery.isFetching}>
					<table className="w-full min-w-[1040px] text-left text-xs">
						<caption className="sr-only">Hàng đợi hồ sơ điều tra</caption>
						<thead className="border-b border-dark-700/80 bg-dark-950/60 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
							<tr>
								<th scope="col" className="px-4 py-3">Mã hồ sơ / sự kiện</th>
								<th scope="col" className="px-3 py-3">Người dùng liên quan</th>
								<th scope="col" className="px-3 py-3">Số tiền & thời gian giao dịch</th>
								<th scope="col" className="px-3 py-3">Điểm mô hình / ưu tiên</th>
								<th scope="col" className="px-3 py-3">Thao tác & luật đã kích hoạt</th>
								<th scope="col" className="px-3 py-3">Mức ưu tiên</th>
								<th scope="col" className="px-3 py-3">Trạng thái</th>
								<th scope="col" className="px-3 py-3">Assignee</th>
								<th scope="col" className="px-4 py-3 text-right">Thao tác</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-dark-800">
							{casesQuery.data?.items.map((item) => (
								<tr key={item.case_id} className="hover:bg-dark-850/60 transition-colors">
									<td className="max-w-56 px-4 py-3">
										<Link
											className="block break-all font-mono font-semibold text-brand-400 hover:text-brand-300 hover:underline"
											to={`/investigation/cases/${item.case_id}`}
										>
											{item.case_code}
										</Link>
										<span className="mt-0.5 block break-all font-mono text-[11px] text-slate-400">
											Event: {item.event_id}
										</span>
									</td>
									<td className="max-w-40 break-all px-3 py-3 font-mono text-slate-200">
										{item.user_id}
									</td>
									<td className="px-3 py-3">
										<div className="font-mono font-semibold tabular-nums text-slate-100">
											{formatCurrencyAmount(item.amount)}
										</div>
										<div className="mt-0.5 text-[11px] text-slate-400">
											{formatDateTime(item.tx_timestamp)}
										</div>
									</td>
									<td className="px-3 py-3">
										<ScoreBar score={item.model_score} />
										<span className="mt-1 block font-mono text-[11px] tabular-nums text-slate-400">
											Điểm ưu tiên: {formatNumber(item.priority_score, 1)}
										</span>
									</td>
									<td className="max-w-56 px-3 py-3">
										<StatusBadge value={item.final_action} />
										<div className="mt-1.5 flex flex-wrap gap-1">
											{item.triggered_rule_codes.length > 0 ? (
												item.triggered_rule_codes.map((code) => (
													<span
														key={code}
														className="rounded border border-dark-700 bg-dark-950 px-1.5 py-0.5 font-mono text-[10px] text-slate-300"
													>
														{code}
													</span>
												))
											) : (
												<span className="text-[11px] text-slate-500">Chỉ điểm ML</span>
											)}
										</div>
									</td>
									<td className="px-3 py-3">
										<StatusBadge value={item.priority} />
									</td>
									<td className="px-3 py-3">
										<StatusBadge value={item.status} />
									</td>
									<td className="px-3 py-3">
										<span className="font-mono text-[11px] text-slate-300">
											{item.assigned_to || 'Chưa giao'}
										</span>
										<span className="mt-0.5 block text-[10px] text-slate-500">
											Created {formatDateTime(item.created_at)}
										</span>
									</td>
									<td className="px-4 py-3 text-right">
										<div className="inline-flex items-center justify-end gap-2">
											{item.status === 'OPEN' && (
												<button
													type="button"
													className={BUTTON_SECONDARY_CLASS}
													disabled={claimMutation.isPending || readOnly}
													onClick={() => claimMutation.mutate(item)}
												>
													<UserCheck size={14} />
													<span>Nhận xử lý</span>
												</button>
											)}
											<Link
												to={`/investigation/cases/${item.case_id}`}
												className={BUTTON_PRIMARY_CLASS}
											>
												<span>Điều tra</span>
												<ArrowUpRight size={14} />
											</Link>
										</div>
									</td>
								</tr>
							))}
						</tbody>
					</table>

					{casesQuery.isPending ? (
						<p role="status" className="p-8 text-center text-sm text-slate-400">
							Đang tải hồ sơ điều tra...
						</p>
					) : !casesQuery.error && !casesQuery.data?.items.length ? (
						<div className="p-8 text-center text-sm text-slate-400">
							Không có hồ sơ điều tra nào khớp bộ lọc hiện tại.
						</div>
					) : null}
				</div>

				<div className="flex items-center justify-between border-t border-dark-700/80 bg-dark-850/30 px-4 py-3 text-xs text-slate-300">
					<span>Trang {page}</span>
					<div className="flex items-center gap-2">
						<button
							type="button"
							className={BUTTON_SECONDARY_CLASS}
							disabled={page === 1 || casesQuery.isFetching}
							onClick={() => setPage(page - 1)}
							aria-label="Trang trước"
						>
							<ArrowLeft size={14} />
							<span>Trước</span>
						</button>
						<button
							type="button"
							className={BUTTON_SECONDARY_CLASS}
							disabled={
								casesQuery.isFetching ||
								!casesQuery.data ||
								page * 50 >= casesQuery.data.total
							}
							onClick={() => setPage(page + 1)}
							aria-label="Trang sau"
						>
							<span>Sau</span>
							<ArrowRight size={14} />
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}

