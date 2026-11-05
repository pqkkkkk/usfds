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
						<p className="text-xs text-slate-400">Active Blocked Entities</p>
						<p className="mt-1 font-mono text-2xl font-bold text-slate-100">
							{formatNumber(activeBlacklistCount, 0)}
						</p>
						<p className="mt-0.5 text-[11px] text-slate-400">
							Enforced in project blacklist
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
							Retained in audit history
						</p>
					</div>
					<span className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-2.5 text-emerald-400">
						<CheckCircle2 size={18} aria-hidden="true" />
					</span>
				</div>
				<div className="flex items-start justify-between rounded-xl border border-dark-700/80 bg-dark-900 p-4">
					<div>
						<p className="text-xs text-slate-400">Rules in Feedback Loop</p>
						<p className="mt-1 font-mono text-2xl font-bold text-slate-100">
							{formatNumber(allFeedback.length, 0)}
						</p>
						<p className="mt-0.5 text-[11px] text-slate-400">
							Triggered across investigation cases
						</p>
					</div>
					<span className="rounded-lg border border-sky-500/20 bg-sky-500/10 p-2.5 text-sky-400">
						<Sliders size={18} aria-hidden="true" />
					</span>
				</div>
				<div className="flex items-start justify-between rounded-xl border border-dark-700/80 bg-dark-900 p-4">
					<div>
						<p className="text-xs text-slate-400">Noisy Rules (FPR &gt; 80%)</p>
						<p className="mt-1 font-mono text-2xl font-bold text-slate-100">
							{formatNumber(noisyRuleCount, 0)}
						</p>
						<p className="mt-0.5 text-[11px] text-slate-400">
							Recommended for threshold tuning
						</p>
					</div>
					<span className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-2.5 text-amber-400">
						<AlertTriangle size={18} aria-hidden="true" />
					</span>
				</div>
			</div>

			<div
				role="tablist"
				aria-label="Investigation policies"
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
					Entity Blacklist ({activeBlacklistCount} Active)
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
					Rule Investigation Feedback ({allFeedback.length})
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
						title="Add Entity to Blacklist"
						subtitle="Block compromised users, cards, devices, IP addresses, or collusive merchants (BUC-07)"
					>
						<form
							className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
							onSubmit={(event) => {
								event.preventDefault();
								addMutation.mutate();
							}}
						>
							<FormField name="Entity Type">
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
							<FormField name="Entity Identifier Value">
								<input
									className={INPUT_CLASS}
									value={value}
									maxLength={255}
									required
									placeholder="e.g. usr_1092, dev_88a..."
									onChange={(event) => setValue(event.target.value)}
								/>
							</FormField>
							<FormField name="Blocking Reason" hint="Min 10 chars">
								<input
									className={INPUT_CLASS}
									value={reason}
									minLength={10}
									maxLength={10000}
									required
									placeholder="Justification for blocking entity..."
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
								<span>Add to Blacklist</span>
							</button>
						</form>
					</SectionCard>

					{removingId && (
						<SectionCard
							title="Confirm Blacklist Removal"
							subtitle="Removing an entity preserves the record with status REMOVED in the audit trail"
						>
							<form
								className="flex flex-col gap-3 sm:flex-row sm:items-end"
								onSubmit={(event) => {
									event.preventDefault();
									removeMutation.mutate();
								}}
							>
								<div className="flex-1">
									<FormField name="Removal Reason" hint="Min 10 chars required">
										<input
											className={INPUT_CLASS}
											required
											minLength={10}
											placeholder="Explain why this entity is being unblocked..."
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
									<span>Confirm Removal</span>
								</button>
								<button
									type="button"
									className={BUTTON_SECONDARY_CLASS}
									onClick={() => setRemovingId(null)}
								>
									Cancel
								</button>
							</form>
						</SectionCard>
					)}

					<SectionCard
						title="Entity Blacklist Registry"
						subtitle={`Showing ${filteredEntries.length} matching entries`}
					>
						<div className="grid gap-3 sm:grid-cols-3">
							<FormField name="Search Blacklist">
								<input
									className={INPUT_CLASS}
									placeholder="Search value or reason..."
									value={search}
									onChange={(event) => setSearch(event.target.value)}
								/>
							</FormField>
							<FormField name="Filter Entity Type">
								<select
									className={INPUT_CLASS}
									value={typeFilter}
									onChange={(event) => setTypeFilter(event.target.value)}
								>
									<option value="">All entity types</option>
									{ENTITY_TYPES.map((kind) => (
										<option key={kind} value={kind}>
											{kind}
										</option>
									))}
								</select>
							</FormField>
							<FormField name="Entry Status">
								<select
									className={INPUT_CLASS}
									value={statusFilter}
									onChange={(event) => setStatusFilter(event.target.value)}
								>
									<option value="">All statuses</option>
									<option value="ACTIVE">ACTIVE</option>
									<option value="REMOVED">REMOVED</option>
								</select>
							</FormField>
						</div>

						<div className="overflow-x-auto pt-2">
							<table className="w-full min-w-[720px] text-left text-xs">
								<caption className="sr-only">Entity blacklist</caption>
								<thead className="border-b border-dark-700/80 text-[11px] uppercase text-slate-400">
									<tr>
										<th scope="col" className="py-3 pr-3">Entity Type &amp; Value</th>
										<th scope="col" className="py-3 pr-3">Status</th>
										<th scope="col" className="py-3 pr-3">Reason &amp; Source Case</th>
										<th scope="col" className="py-3 pr-3">Audit Metadata</th>
										<th scope="col" className="py-3 text-right">Action</th>
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
														View Source Case &rarr;
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
														Removed by {entry.removed_by} ({formatDateTime(entry.removed_at)})
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
														<span>Remove</span>
													</button>
												)}
											</td>
										</tr>
									))}
								</tbody>
							</table>
							{entriesQuery.isPending ? (
								<p role="status" className="py-6 text-center text-sm text-slate-400">
									Loading entity blacklist...
								</p>
							) : (
								!filteredEntries.length &&
								!entriesQuery.error && (
									<p className="py-6 text-center text-sm text-slate-400">
										No blacklist entries match the current filters.
									</p>
								)
							)}
						</div>
					</SectionCard>
				</div>
			) : (
				<SectionCard
					title="Rule Verification Feedback Table"
					subtitle="Evaluate real-world rule precision from analyst-verified ground truth (SUC-18 -> SUC-20)"
				>
					<div className="overflow-x-auto">
						<table className="w-full min-w-[740px] text-left text-xs">
							<caption className="sr-only">Verified rule feedback by version</caption>
							<thead className="border-b border-dark-700/80 text-[11px] uppercase text-slate-400">
								<tr>
									<th scope="col" className="py-3 pr-3">Rule Version</th>
									<th scope="col" className="py-3 pr-3">Cases Triggered</th>
									<th scope="col" className="py-3 pr-3">Confirmed Fraud (TP)</th>
									<th scope="col" className="py-3 pr-3">False Positive (FP)</th>
									<th scope="col" className="py-3 pr-3">Pending Review</th>
									<th scope="col" className="py-3 pr-3">Verified FPR %</th>
									<th scope="col" className="py-3 text-right">Action</th>
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
														<span>Noisy</span>
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
													<span>Tune Rule</span>
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
								Loading verified rule feedback...
							</p>
						) : (
							!allFeedback.length &&
							!feedbackQuery.error && (
								<p className="py-6 text-center text-sm text-slate-400">
									No verified rule feedback available yet.
								</p>
							)
						)}
					</div>
				</SectionCard>
			)}
		</div>
	);
}

