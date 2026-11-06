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
			label: 'Open Cases',
			value: formatNumber(kpisQuery.data?.open, 0),
			subtext: 'Waiting for analyst triage',
			icon: Briefcase,
			accent: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
		},
		{
			label: 'Critical Unresolved',
			value: formatNumber(kpisQuery.data?.critical, 0),
			subtext: 'Immediate investigation required',
			icon: AlertTriangle,
			accent: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
		},
		{
			label: 'In Progress',
			value: formatNumber(kpisQuery.data?.in_progress, 0),
			subtext: `Pending customer: ${formatNumber(kpisQuery.data?.pending_customer, 0)}`,
			icon: ClipboardCheck,
			accent: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
		},
		{
			label: 'Confirmed Fraud Ratio',
			value: formatPercent(kpisQuery.data?.confirmed_fraud_ratio),
			subtext: `Total resolved: ${formatNumber(kpisQuery.data?.resolved, 0)} cases`,
			icon: CheckCircle2,
			accent: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
		},
	];

	return (
		<div className="space-y-5">
			<div
				className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
				aria-label="Case statistics"
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
				title="Multi-dimensional Queue Filters"
				subtitle={
					userFilterParam
						? `Filtering cases for Subject User ID: ${userFilterParam}`
						: 'Narrow down cases by priority, status, rule code, model score, or transaction amount'
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
							<span>Reset</span>
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
							<span>Refresh</span>
						</button>
					</div>
				}
			>
				<div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 lg:grid-cols-5">
					<FormField name="Search (Case / Event / User)">
						<input
							className={INPUT_CLASS}
							placeholder="CASE-2026-..., evt_..., usr_..."
							value={filters.q}
							onChange={(event) => handleFilterChange('q', event.target.value)}
						/>
					</FormField>
					<FormField name="Status">
						<select
							className={INPUT_CLASS}
							value={filters.status}
							onChange={(event) => handleFilterChange('status', event.target.value)}
						>
							<option value="">All statuses</option>
							{CASE_STATUSES.map((status) => (
								<option key={status} value={status}>
									{status}
								</option>
							))}
						</select>
					</FormField>
					<FormField name="Priority">
						<select
							className={INPUT_CLASS}
							value={filters.priority}
							onChange={(event) => handleFilterChange('priority', event.target.value)}
						>
							<option value="">All priorities</option>
							{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((priority) => (
								<option key={priority} value={priority}>
									{priority}
								</option>
							))}
						</select>
					</FormField>
					<FormField name="Assignment">
						<select
							className={INPUT_CLASS}
							value={filters.assigned_to}
							onChange={(event) => handleFilterChange('assigned_to', event.target.value)}
						>
							<option value="">All analysts</option>
							<option value="local-analyst">Assigned to me (local-analyst)</option>
							<option value="unassigned">Unassigned only</option>
						</select>
					</FormField>
					<FormField name="Triggered Rule Code">
						<input
							className={INPUT_CLASS}
							placeholder="e.g. R-001"
							value={filters.rule_code}
							onChange={(event) => handleFilterChange('rule_code', event.target.value)}
						/>
					</FormField>
					<FormField name="Min Model Score" hint="0.00 - 1.00">
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
					<FormField name="Max Model Score" hint="0.00 - 1.00">
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
					<FormField name="Min Amount">
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
					<FormField name="Max Amount">
						<input
							type="number"
							min="0"
							step="any"
							placeholder="Any"
							className={INPUT_CLASS}
							value={filters.max_amount}
							onChange={(event) => handleFilterChange('max_amount', event.target.value)}
						/>
					</FormField>
					<FormField name="Sort Order">
						<select
							className={INPUT_CLASS}
							value={filters.sort}
							onChange={(event) => handleFilterChange('sort', event.target.value)}
						>
							<option value="priority">Priority score descending</option>
							<option value="amount">Transaction amount descending</option>
							<option value="created">Newest created first</option>
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
						Click a Case Code or Investigate to open the 3-Column Workbench
					</span>
				</div>

				<div className="overflow-x-auto" aria-busy={casesQuery.isFetching}>
					<table className="w-full min-w-[1040px] text-left text-xs">
						<caption className="sr-only">Investigation case queue</caption>
						<thead className="border-b border-dark-700/80 bg-dark-950/60 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
							<tr>
								<th scope="col" className="px-4 py-3">Case / Event ID</th>
								<th scope="col" className="px-3 py-3">Subject User</th>
								<th scope="col" className="px-3 py-3">Amount &amp; Tx Time</th>
								<th scope="col" className="px-3 py-3">Model / Priority Score</th>
								<th scope="col" className="px-3 py-3">Action &amp; Triggered Rules</th>
								<th scope="col" className="px-3 py-3">Priority</th>
								<th scope="col" className="px-3 py-3">Status</th>
								<th scope="col" className="px-3 py-3">Assignee</th>
								<th scope="col" className="px-4 py-3 text-right">Actions</th>
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
											Priority score: {formatNumber(item.priority_score, 1)}
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
												<span className="text-[11px] text-slate-500">ML Score Only</span>
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
											{item.assigned_to || 'Unassigned'}
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
													<span>Claim</span>
												</button>
											)}
											<Link
												to={`/investigation/cases/${item.case_id}`}
												className={BUTTON_PRIMARY_CLASS}
											>
												<span>Investigate</span>
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
							Loading investigation cases...
						</p>
					) : !casesQuery.error && !casesQuery.data?.items.length ? (
						<div className="p-8 text-center text-sm text-slate-400">
							No investigation cases match the current filters.
						</div>
					) : null}
				</div>

				<div className="flex items-center justify-between border-t border-dark-700/80 bg-dark-850/30 px-4 py-3 text-xs text-slate-300">
					<span>Page {page}</span>
					<div className="flex items-center gap-2">
						<button
							type="button"
							className={BUTTON_SECONDARY_CLASS}
							disabled={page === 1 || casesQuery.isFetching}
							onClick={() => setPage(page - 1)}
							aria-label="Previous page"
						>
							<ArrowLeft size={14} />
							<span>Previous</span>
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
							aria-label="Next page"
						>
							<span>Next</span>
							<ArrowRight size={14} />
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}

