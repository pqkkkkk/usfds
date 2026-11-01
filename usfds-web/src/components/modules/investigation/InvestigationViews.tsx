import { useDeferredValue, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, ClipboardCheck, FilePlus2, Plus, RefreshCw, Save, ShieldAlert, Unlock, UserCheck } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import { investigationApi } from '../../../api/investigationApi';
import type { Case, CaseAction, CaseStatus, EntityType } from '../../../types/investigation';

const INPUT = 'w-full min-w-0 rounded border border-dark-700 bg-dark-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500';
const BUTTON = 'inline-flex min-h-9 items-center justify-center gap-2 rounded border border-dark-600 px-3 py-2 text-sm text-slate-100 hover:bg-dark-800 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400';
const STATUSES: CaseStatus[] = ['OPEN', 'IN_PROGRESS', 'PENDING_CUSTOMER', 'RESOLVED_FRAUD', 'RESOLVED_LEGITIMATE'];
const ENTITY_TYPES: EntityType[] = ['USER_ID', 'CARD_ID', 'DEVICE_ID', 'IP_ADDRESS', 'MERCHANT_ID'];
const FRAUD_REASONS = ['CARD_TESTING', 'VELOCITY_ATTACK', 'ACCOUNT_TAKEOVER', 'DEVICE_SHARING_RING', 'COLLUSIVE_MERCHANT', 'OTHER_FRAUD'];
const LEGITIMATE_REASONS = ['LEGITIMATE_UNUSUAL_SPENDING', 'CUSTOMER_CONFIRMED', 'OVERLY_STRICT_RULE', 'MODEL_FALSE_ALARM', 'OTHER_LEGITIMATE'];
const number = (value: number | null | undefined) => value == null ? '--' : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
const percent = (value: number | null | undefined) => value == null ? '--' : `${(value * 100).toFixed(1)}%`;
const label = (value: string) => value.replaceAll('_', ' ');
const date = (value: string) => new Date(value).toLocaleString();

function Field({ name, children }: { name: string; children: ReactNode }) {
	return <label className="flex min-w-0 flex-col gap-1 text-xs text-slate-300">{name}{children}</label>;
}

function Status({ value }: { value: string }) {
	const danger = ['CRITICAL', 'HIGH', 'REJECT', 'BLOCKED', 'RESOLVED_FRAUD'].includes(value);
	const success = value === 'RESOLVED_LEGITIMATE' || value === 'REMOVED';
	const Icon = danger ? ShieldAlert : success ? CheckCircle2 : ClipboardCheck;
	return <span className={`inline-flex items-center gap-1 text-xs ${danger ? 'text-red-400' : success ? 'text-emerald-400' : 'text-amber-300'}`}><Icon size={14} aria-hidden="true" />{label(value)}</span>;
}

function ErrorNotice({ error }: { error: Error | null }) {
	return error ? <div role="alert" className="flex items-start gap-2 border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200"><AlertTriangle size={18} className="shrink-0" />{error.message}</div> : null;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
	return <section className="min-w-0 space-y-3 border-b border-dark-700 py-5"><h2 className="text-sm font-semibold text-slate-100">{title}</h2>{children}</section>;
}

export function CaseQueueView({ projectId, readOnly }: { projectId: string; readOnly: boolean }) {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [searchParams] = useSearchParams();
	const [filters, setFilters] = useState<Record<string, string>>({ status: '', priority: '', assigned_to: '', rule_code: '', min_score: '', max_score: '', min_amount: '', max_amount: '', q: '', sort: 'priority' });
	const [page, setPage] = useState(1);
	const deferredFilters = useDeferredValue(filters);
	const queryFilters: Record<string, unknown> = { page, size: 50 };
	if (searchParams.get('user')) queryFilters.user_id = searchParams.get('user');
	for (const [key, value] of Object.entries(deferredFilters)) {
		if (value) queryFilters[key] = key.startsWith('min_') || key.startsWith('max_') ? Number(value) : value;
	}
	if (queryFilters.assigned_to === 'unassigned') { delete queryFilters.assigned_to; queryFilters.unassigned = true; }
	const cases = useQuery({ queryKey: ['investigation', projectId, 'queue', queryFilters], queryFn: () => investigationApi.list(projectId, queryFilters) });
	const kpis = useQuery({ queryKey: ['investigation', projectId, 'kpis'], queryFn: () => investigationApi.kpis(projectId) });
	const claim = useMutation({ mutationFn: (item: Case) => investigationApi.action(projectId, item.case_id, 'claim', { expected_version: item.version }),
		onSuccess: (result) => { void queryClient.invalidateQueries({ queryKey: ['investigation', projectId] }); navigate(`/investigation/cases/${result.case.case_id}`); },
		onError: () => { void cases.refetch(); } });
	const change = (key: string, value: string) => { setFilters({ ...filters, [key]: value }); setPage(1); };
	return <div className="space-y-5">
		<div className="grid grid-cols-2 gap-4 border-b border-dark-700 pb-5 lg:grid-cols-4" aria-label="Case statistics">
			{[['Open cases', kpis.data?.open], ['Critical unresolved', kpis.data?.critical], ['In progress', kpis.data?.in_progress], ['Confirmed fraud ratio', percent(kpis.data?.confirmed_fraud_ratio)]].map(([name, value]) => <div key={name} className="min-w-0"><p className="text-xs text-slate-300">{name}</p><p className="mt-2 text-xl font-semibold tabular-nums text-slate-100">{value ?? '--'}</p></div>)}
		</div>
		<ErrorNotice error={cases.error || kpis.error || claim.error} />
		<div className="grid grid-cols-2 items-end gap-3 xl:grid-cols-5">
			<Field name="Case, event or user"><input className={INPUT} value={filters.q} onChange={(event) => change('q', event.target.value)} /></Field>
			<Field name="Status"><select className={INPUT} value={filters.status} onChange={(event) => change('status', event.target.value)}><option value="">All</option>{STATUSES.map((status) => <option key={status}>{status}</option>)}</select></Field>
			<Field name="Priority"><select className={INPUT} value={filters.priority} onChange={(event) => change('priority', event.target.value)}><option value="">All</option>{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((priority) => <option key={priority}>{priority}</option>)}</select></Field>
			<Field name="Assignment"><select className={INPUT} value={filters.assigned_to} onChange={(event) => change('assigned_to', event.target.value)}><option value="">All</option><option value="local-analyst">Local analyst</option><option value="unassigned">Unassigned</option></select></Field>
			<Field name="Rule code"><input className={INPUT} value={filters.rule_code} onChange={(event) => change('rule_code', event.target.value)} /></Field>
			{(['min_score', 'max_score', 'min_amount', 'max_amount'] as const).map((key) => <Field key={key} name={label(key)}><input type="number" min="0" max={key.includes('score') ? 1 : undefined} step={key.includes('score') ? '0.01' : 'any'} className={INPUT} value={filters[key]} onChange={(event) => change(key, event.target.value)} /></Field>)}
			<Field name="Sort"><select className={INPUT} value={filters.sort} onChange={(event) => change('sort', event.target.value)}><option value="priority">Priority descending</option><option value="amount">Amount descending</option><option value="created">Newest first</option></select></Field>
		</div>
		<div className="flex items-center justify-between text-xs text-slate-300"><span>{number(cases.data?.total)} cases</span><button className={BUTTON} disabled={cases.isFetching} onClick={() => { void queryClient.invalidateQueries({ queryKey: ['investigation', projectId] }); }}><RefreshCw size={16} />Refresh</button></div>
		<div className="overflow-x-auto border-y border-dark-700" aria-busy={cases.isFetching}>
			<table className="w-full min-w-[900px] text-left text-xs"><caption className="sr-only">Investigation cases</caption><thead className="bg-dark-900 text-slate-300"><tr>{['Case / Event', 'User', 'Amount', 'Model score', 'Action / Rules', 'Priority', 'Status', ''].map((heading, index) => <th scope="col" key={index} className="px-3 py-3">{heading}</th>)}</tr></thead><tbody>
				{cases.data?.items.map((item) => <tr key={item.case_id} className="border-t border-dark-800 hover:bg-dark-900"><td className="max-w-56 px-3 py-3"><Link className="block break-all font-mono text-blue-300 hover:underline" to={`/investigation/cases/${item.case_id}`}>{item.case_code}</Link><span className="text-slate-300">{item.event_id}</span></td><td className="max-w-36 break-all px-3 py-3">{item.user_id}</td><td className="px-3 py-3 tabular-nums">{number(item.amount)}</td><td className="px-3 py-3 tabular-nums">{percent(item.model_score)}</td><td className="max-w-52 break-words px-3 py-3"><Status value={item.final_action} /><p className="mt-1 text-slate-300">{item.triggered_rule_codes.join(', ') || '--'}</p></td><td className="px-3 py-3"><Status value={item.priority} /></td><td className="px-3 py-3"><Status value={item.status} /></td><td className="px-3 py-3">{item.status === 'OPEN' && <button className={BUTTON} disabled={claim.isPending || readOnly} onClick={() => claim.mutate(item)}><UserCheck size={16} />Claim</button>}</td></tr>)}
			</tbody></table>
			{cases.isPending ? <p role="status" className="p-6 text-sm text-slate-300">Loading cases...</p> : !cases.error && !cases.data?.items.length ? <p className="p-6 text-sm text-slate-300">No cases found.</p> : null}
		</div>
		<div className="flex items-center justify-end gap-3 text-xs text-slate-300"><button className={BUTTON} disabled={page === 1 || cases.isFetching} onClick={() => setPage(page - 1)} aria-label="Previous page"><ArrowLeft size={16} /></button><span>Page {page}</span><button className={BUTTON} disabled={cases.isFetching || !cases.data || page * 50 >= cases.data.total} onClick={() => setPage(page + 1)} aria-label="Next page"><ArrowRight size={16} /></button></div>
	</div>;
}

export function CaseWorkbenchView({ projectId, readOnly }: { projectId: string; readOnly: boolean }) {
	const { caseId = '' } = useParams();
	return <CaseWorkbench key={`${projectId}:${caseId}`} projectId={projectId} caseId={caseId} readOnly={readOnly} />;
}

function CaseWorkbench({ projectId, caseId, readOnly }: { projectId: string; caseId: string; readOnly: boolean }) {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [days, setDays] = useState<30 | 90>(30);
	const [verdict, setVerdict] = useState<'FRAUD' | 'LEGITIMATE'>('FRAUD');
	const [reason, setReason] = useState('');
	const [summary, setSummary] = useState('');
	const [note, setNote] = useState('');
	const [assignee, setAssignee] = useState('');
	const [blocked, setBlocked] = useState<EntityType[]>([]);
	const [notice, setNotice] = useState('');
	const result = useQuery({ queryKey: ['investigation', projectId, 'workbench', caseId, days], queryFn: () => investigationApi.workbench(projectId, caseId, days) });
	const mutate = useMutation({ mutationFn: async ({ action, payload }: { action: string; payload: CaseAction }) => action === 'note' ? investigationApi.note(projectId, caseId, note) : investigationApi.action(projectId, caseId, action, payload),
		onSuccess: () => { setNotice('Saved'); setNote(''); setSummary(''); void queryClient.invalidateQueries({ queryKey: ['investigation', projectId] }); },
		onError: () => { void result.refetch(); } });
	const draft = useMutation({ mutationFn: () => investigationApi.draft(projectId, caseId), onSuccess: (data) => navigate('/rules/new', { state: { investigationDraft: { ...data, project_id: projectId } } }) });
	if (result.isPending) return <p role="status" className="p-6 text-slate-300">Loading case...</p>;
	if (!result.data) return <div className="space-y-4"><Link to="/investigation" className={BUTTON}><ArrowLeft size={16} />Case queue</Link><ErrorNotice error={result.error} /></div>;
	const { case: item, profile, related_cases: related, audit_logs: logs } = result.data;
	const resolved = item.status.startsWith('RESOLVED');
	const disabled = mutate.isPending || readOnly || result.isFetching;
	const act = (action: string) => mutate.mutate({ action, payload: { expected_version: item.version, summary, ...(action === 'escalate' ? { assignee } : {}) } });
	const entities = ENTITY_TYPES.map((entity_type) => ({ entity_type, entity_value: entity_type === 'USER_ID' ? item.user_id : String(item.attributes[entity_type.toLowerCase()] ?? '') })).filter((entity) => entity.entity_value);
	const contributions = item.feature_contributions.map((feature) => ({ ...feature, display_name: feature.feature_name.length > 24 ? feature.feature_name.slice(0, 21) + '...' : feature.feature_name }));
	const points = profile.timeline.map((point) => ({ ...point, time: new Date(point.timestamp).getTime() }));
	return <div className="space-y-3">
		<div className="flex flex-wrap items-center justify-between gap-3"><Link to="/investigation" className={BUTTON}><ArrowLeft size={16} />Case queue</Link><div className="flex flex-wrap items-center gap-3"><Status value={item.status} /><Status value={item.priority} /><span className="text-xs text-slate-300">Version {item.version}</span></div></div>
		<h1 className="break-all font-mono text-base text-slate-100">{item.case_code}</h1>
		<ErrorNotice error={result.error || mutate.error || draft.error} />{notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
		<div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1fr)]">
			<div className="min-w-0">
				<Section title="Subject"><p className="break-all font-mono text-sm">{item.user_id}</p><Status value={result.data.subject_status} /><dl className="space-y-2 text-xs text-slate-300"><dt>Event</dt><dd className="break-all text-slate-100">{item.event_id}</dd><dt>Amount</dt><dd className="text-slate-100 tabular-nums">{number(item.amount)}</dd><dt>Transaction time</dt><dd>{date(item.tx_timestamp)}</dd><dt>Assigned to</dt><dd>{item.assigned_to || 'Unassigned'}</dd></dl></Section>
				<Section title="Historical baseline"><Field name="Window"><select className={INPUT} value={days} onChange={(event) => setDays(Number(event.target.value) as 30 | 90)}><option value={30}>30 days</option><option value={90}>90 days</option></select></Field>{profile.cold_start && <p className="text-xs text-amber-300">Cold-start account / Population baseline</p>}{!profile.available ? <p className="text-xs text-slate-300">{profile.message || 'No historical baseline available.'}</p> : <dl className="grid grid-cols-2 gap-2 text-xs"><dt className="text-slate-300">Average amount</dt><dd>{number(profile.avg_amount)}</dd><dt className="text-slate-300">Maximum</dt><dd>{number(profile.max_amount)}</dd><dt className="text-slate-300">History count</dt><dd>{number(profile.history_count)}</dd><dt className="text-slate-300">Transactions/day</dt><dd>{number(profile.transactions_per_day)}</dd></dl>}</Section>
				<Section title={`Related cases (${result.data.related_total})`}><div className="space-y-3">{related.map((entry) => <div key={entry.case_id} className="text-xs"><Link className="break-all text-blue-300 hover:underline" to={`/investigation/cases/${entry.case_id}`}>{entry.event_id}</Link><p className="mt-1"><Status value={entry.status} /></p><p className="text-slate-300">{entry.assigned_to || 'Unassigned'} / {number(entry.amount)}</p></div>)}{!related.length && <p className="text-xs text-slate-300">No other cases for this user.</p>}{result.data.related_total > related.length && <Link to={`/investigation?user=${encodeURIComponent(item.user_id)}`} className="text-xs text-blue-300">View all related cases</Link>}</div></Section>
			</div>
			<div className="min-w-0">
				<Section title="Detection evidence"><div className="flex items-center justify-between"><Status value={item.final_action} /><span className="text-sm tabular-nums">Model score {percent(item.model_score)}</span></div>{contributions.length ? <div className="h-60 min-w-0" role="img" aria-label="Local feature contributions"><ResponsiveContainer width="100%" height="100%"><BarChart data={contributions} layout="vertical" margin={{ left: 0, right: 20 }}><CartesianGrid stroke="#334155" horizontal={false} /><XAxis type="number" tick={{ fill: '#cbd5e1', fontSize: 11 }} /><YAxis type="category" dataKey="display_name" width={140} tick={{ fill: '#cbd5e1', fontSize: 11 }} /><Tooltip contentStyle={{ background: '#0f172a', borderColor: '#475569', color: '#f1f5f9' }} /><Bar dataKey="contribution" isAnimationActive={false}>{contributions.map((feature, index) => <Cell key={index} fill={feature.contribution > 0 ? '#f87171' : '#34d399'} />)}</Bar></BarChart></ResponsiveContainer></div> : <p className="text-xs text-slate-300">No model explanation available.</p>}{item.triggered_rules.map((rule) => <div key={rule.rule_version_id} className="border-t border-dark-700 pt-3 text-xs"><div className="flex flex-wrap justify-between gap-2"><span className="break-all font-mono">{rule.rule_code} / v{rule.version_number}</span><Status value={rule.action} /></div><p className="mt-2 break-words text-slate-300">{rule.trigger_reason}</p>{rule.matched_clauses?.map((clause, index) => <p key={index} className="mt-1 break-all font-mono text-slate-200">{clause}</p>)}</div>)}{!item.triggered_rules.length && <p className="text-xs text-slate-300">No triggered rules in snapshot.</p>}</Section>
				<Section title="Transaction timeline"><div className="h-60 min-w-0" role="img" aria-label="Historical transactions and current flagged transaction">{points.length ? <ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ right: 15, left: 0, bottom: 10 }}><CartesianGrid stroke="#334155" /><XAxis type="number" dataKey="time" domain={['dataMin', 'dataMax']} tickFormatter={(value) => new Date(value).toLocaleDateString()} tick={{ fill: '#cbd5e1', fontSize: 10 }} /><YAxis type="number" dataKey="amount" width={70} tick={{ fill: '#cbd5e1', fontSize: 10 }} /><Tooltip cursor={{ strokeDasharray: '3 3' }} labelFormatter={(value) => new Date(Number(value)).toLocaleString()} contentStyle={{ background: '#0f172a', color: '#f1f5f9' }} /><Scatter data={points.filter((point) => !point.is_current)} fill="#94a3b8" name="Historical" isAnimationActive={false} /><Scatter data={points.filter((point) => point.is_current)} fill="#f87171" name="Current case" isAnimationActive={false} /></ScatterChart></ResponsiveContainer> : <p className="text-xs text-slate-300">No transaction history available.</p>}</div>{profile.timeline_truncated && <p className="text-xs text-amber-300">Showing the latest 500 transactions.</p>}</Section>
				<Section title="Current vs. baseline"><div className="overflow-x-auto"><table className="w-full text-left text-xs"><caption className="sr-only">Behavioral comparison</caption><thead><tr>{['Field', 'Current', 'Baseline'].map((heading) => <th scope="col" className="py-2 pr-3 text-slate-300" key={heading}>{heading}</th>)}</tr></thead><tbody>{profile.comparison.map((row) => <tr className="border-t border-dark-800" key={row.field}><td className="py-2 pr-3">{label(row.field)}</td><td className={`max-w-40 break-all py-2 pr-3 ${row.is_anomalous ? 'text-red-300' : ''}`}>{row.is_anomalous && <AlertTriangle size={14} className="mr-1 inline" aria-label="Anomalous" />}{row.current == null ? '--' : String(row.current)}</td><td className="max-w-40 break-words py-2 text-slate-300">{Array.isArray(row.baseline) ? row.baseline.join(', ') || '--' : row.baseline == null ? '--' : String(row.baseline)}</td></tr>)}</tbody></table></div></Section>
				<Section title="Transaction snapshot"><pre className="max-h-64 overflow-auto text-xs text-slate-300">{JSON.stringify(item.attributes, null, 2)}</pre></Section>
			</div>
			<div className="min-w-0">
				<Section title="Decision">
					{resolved ? <div className="space-y-3 text-xs"><p>{label(item.resolution_reason || '')}</p><p className="break-words text-slate-300">{item.resolution_summary}</p><p>Ground truth: {item.verified_label}</p><p className="text-slate-300">{item.resolved_by} / {item.resolved_at && date(item.resolved_at)}</p><Field name="Reopen reason"><textarea className={INPUT} rows={3} value={summary} onChange={(event) => setSummary(event.target.value)} /></Field><button className={BUTTON} disabled={disabled || summary.trim().length < 10} onClick={() => act('reopen')}><Unlock size={16} />Reopen case</button>{item.status === 'RESOLVED_FRAUD' && <button className={BUTTON} disabled={draft.isPending || readOnly} onClick={() => draft.mutate()}><FilePlus2 size={16} />Create rule</button>}</div> : <>
						<button className={BUTTON} disabled={disabled} onClick={() => act('claim')}><UserCheck size={16} />Claim case</button>
						<form className="space-y-3" onSubmit={(event) => { event.preventDefault(); mutate.mutate({ action: 'resolve', payload: { expected_version: item.version, verdict, reason, summary, block_entities: verdict === 'FRAUD' ? entities.filter((entity) => blocked.includes(entity.entity_type)) : [] } }); }}>
							<Field name="Verdict"><select className={INPUT} value={verdict} onChange={(event) => { setVerdict(event.target.value as 'FRAUD' | 'LEGITIMATE'); setReason(''); }}><option value="FRAUD">Confirmed fraud</option><option value="LEGITIMATE">Legitimate</option></select></Field>
							<Field name="Resolution reason"><select className={INPUT} value={reason} required onChange={(event) => setReason(event.target.value)}><option value="">Select reason</option>{(verdict === 'FRAUD' ? FRAUD_REASONS : LEGITIMATE_REASONS).map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></Field>
							<Field name="Evidence summary"><textarea className={INPUT} rows={4} value={summary} required minLength={10} maxLength={10000} onChange={(event) => setSummary(event.target.value)} /></Field>
							{verdict === 'FRAUD' && <fieldset className="space-y-2 text-xs"><legend className="mb-2 text-slate-300">Blacklist entities</legend>{entities.map((entity) => <label key={entity.entity_type} className="flex items-start gap-2 break-all"><input type="checkbox" checked={blocked.includes(entity.entity_type)} onChange={(event) => setBlocked(event.target.checked ? [...blocked, entity.entity_type] : blocked.filter((value) => value !== entity.entity_type))} />{label(entity.entity_type)}: {entity.entity_value}</label>)}</fieldset>}
							<button className={BUTTON} type="submit" disabled={disabled || !reason || summary.trim().length < 10}><CheckCircle2 size={16} />Submit decision</button>
						</form>
						<button className={BUTTON} disabled={disabled || summary.trim().length < 10} onClick={() => act('pending-customer')}><ClipboardCheck size={16} />Pending customer</button>
						<Field name="Escalation assignee"><input className={INPUT} maxLength={100} value={assignee} onChange={(event) => setAssignee(event.target.value)} /></Field><button className={BUTTON} disabled={disabled || !assignee.trim() || summary.trim().length < 10} onClick={() => act('escalate')}><ShieldAlert size={16} />Escalate</button>
					</>}
				</Section>
				<Section title="Investigation notes"><form className="space-y-3" onSubmit={(event) => { event.preventDefault(); act('note'); }}><Field name="Note"><textarea className={INPUT} rows={3} maxLength={10000} required value={note} onChange={(event) => setNote(event.target.value)} /></Field><button className={BUTTON} disabled={disabled || !note.trim()}><Save size={16} />Add note</button></form></Section>
				<Section title="Audit history"><ol className="space-y-4">{logs.map((log) => <li key={log.log_id} className="space-y-1 text-xs"><p>{label(log.action)}</p><p className="text-slate-300">{log.actor} / {date(log.created_at)}</p>{log.note && <p className="break-words">{log.note}</p>}<details><summary className="cursor-pointer text-blue-300">Changes</summary><pre className="max-h-40 overflow-auto text-xs">{JSON.stringify(log.details, null, 2)}</pre></details></li>)}</ol></Section>
			</div>
		</div>
	</div>;
}

export function PoliciesView({ projectId, readOnly }: { projectId: string; readOnly: boolean }) {
	const queryClient = useQueryClient();
	const [tab, setTab] = useState<'blacklist' | 'feedback'>('blacklist');
	const [search, setSearch] = useState('');
	const [status, setStatus] = useState('ACTIVE');
	const [entityType, setEntityType] = useState<EntityType>('USER_ID');
	const [value, setValue] = useState('');
	const [reason, setReason] = useState('');
	const [removing, setRemoving] = useState<string | null>(null);
	const [removeReason, setRemoveReason] = useState('');
	const entries = useQuery({ queryKey: ['investigation', projectId, 'blacklist'], queryFn: () => investigationApi.blacklist(projectId) });
	const feedback = useQuery({ queryKey: ['investigation', projectId, 'feedback'], queryFn: () => investigationApi.feedback(projectId), enabled: tab === 'feedback' });
	const add = useMutation({ mutationFn: () => investigationApi.addBlacklist(projectId, entityType, value, reason), onSuccess: () => { setValue(''); setReason(''); void queryClient.invalidateQueries({ queryKey: ['investigation', projectId] }); } });
	const remove = useMutation({ mutationFn: () => investigationApi.removeBlacklist(projectId, removing!, removeReason), onSuccess: () => { setRemoving(null); setRemoveReason(''); void queryClient.invalidateQueries({ queryKey: ['investigation', projectId] }); } });
	const filtered = (entries.data || []).filter((entry) => (!status || entry.status === status) && `${entry.entity_type} ${entry.entity_value} ${entry.reason}`.toLowerCase().includes(search.toLowerCase()));
	return <div className="space-y-5"><div role="tablist" aria-label="Investigation policies" className="flex gap-4 border-b border-dark-700">{(['blacklist', 'feedback'] as const).map((value) => <button role="tab" aria-selected={tab === value} className={`border-b-2 px-2 py-3 text-sm ${tab === value ? 'border-blue-400 text-blue-300' : 'border-transparent text-slate-300'}`} key={value} onClick={() => setTab(value)}>{value === 'blacklist' ? 'Blacklist' : 'Rule feedback'}</button>)}</div><ErrorNotice error={entries.error || feedback.error || add.error || remove.error} />
		{tab === 'blacklist' ? <>
			<form className="grid gap-3 border-b border-dark-700 pb-5 sm:grid-cols-2 xl:grid-cols-4" onSubmit={(event) => { event.preventDefault(); add.mutate(); }}><Field name="Entity type"><select className={INPUT} value={entityType} onChange={(event) => setEntityType(event.target.value as EntityType)}>{ENTITY_TYPES.map((value) => <option key={value}>{value}</option>)}</select></Field><Field name="Entity value"><input className={INPUT} value={value} maxLength={255} required onChange={(event) => setValue(event.target.value)} /></Field><Field name="Reason"><input className={INPUT} value={reason} minLength={10} maxLength={10000} required onChange={(event) => setReason(event.target.value)} /></Field><button className={`${BUTTON} self-end`} disabled={readOnly || add.isPending || !value.trim() || reason.trim().length < 10}><Plus size={16} />Add to blacklist</button></form>
			<div className="grid gap-3 sm:grid-cols-2"><Field name="Search blacklist"><input className={INPUT} value={search} onChange={(event) => setSearch(event.target.value)} /></Field><Field name="Entry status"><select className={INPUT} value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All</option><option>ACTIVE</option><option>REMOVED</option></select></Field></div>
			<div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-xs"><caption className="sr-only">Entity blacklist</caption><thead><tr>{['Entity', 'Status', 'Reason', 'Created', ''].map((heading, index) => <th scope="col" className="py-3 pr-3 text-slate-300" key={index}>{heading}</th>)}</tr></thead><tbody>{filtered.map((entry) => <tr key={entry.blacklist_id} className="border-t border-dark-700"><td className="max-w-52 break-all py-3 pr-3">{entry.entity_type}<p className="font-mono">{entry.entity_value}</p></td><td className="py-3 pr-3"><Status value={entry.status} /></td><td className="max-w-80 break-words py-3 pr-3">{entry.reason}{entry.source_case_id && <Link className="block text-blue-300" to={`/investigation/cases/${entry.source_case_id}`}>Source case</Link>}</td><td className="py-3 pr-3 text-slate-300">{date(entry.created_at)}<p>{entry.created_by}</p></td><td className="py-3">{entry.status === 'ACTIVE' && <button className={BUTTON} disabled={readOnly || remove.isPending} onClick={() => { setRemoving(entry.blacklist_id); setRemoveReason(''); }}><Unlock size={16} />Remove</button>}</td></tr>)}</tbody></table>{entries.isPending ? <p role="status" className="py-6 text-sm text-slate-300">Loading blacklist...</p> : !filtered.length && !entries.error && <p className="py-6 text-sm text-slate-300">No blacklist entries found.</p>}</div>
			{removing && <form className="flex flex-col gap-3 border-t border-dark-700 pt-4 sm:flex-row sm:items-end" onSubmit={(event) => { event.preventDefault(); remove.mutate(); }}><Field name="Removal reason"><input className={INPUT} required minLength={10} value={removeReason} onChange={(event) => setRemoveReason(event.target.value)} /></Field><button className={BUTTON} disabled={remove.isPending || removeReason.trim().length < 10 || readOnly}><Unlock size={16} />Confirm removal</button><button className={BUTTON} type="button" onClick={() => setRemoving(null)}>Cancel</button></form>}
		</> : <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-xs"><caption className="sr-only">Verified rule feedback by version</caption><thead><tr>{['Rule version', 'Cases', 'Fraud', 'False positive', 'Pending', 'Verified false-positive ratio', ''].map((heading, index) => <th className="py-3 pr-3 text-slate-300" scope="col" key={index}>{heading}</th>)}</tr></thead><tbody>{feedback.data?.map((row) => <tr key={row.rule_version_id} className="border-t border-dark-700"><td className="py-3 pr-3 font-mono">{row.rule_code} / v{row.version_number}</td><td>{row.cases_triggered}</td><td>{row.tp}</td><td>{row.fp}</td><td>{row.pending}</td><td className={row.verified_false_positive_ratio != null && row.verified_false_positive_ratio > .8 ? 'text-red-300' : ''}>{row.verified_false_positive_ratio != null && row.verified_false_positive_ratio > .8 && <AlertTriangle size={14} className="mr-1 inline" />}{percent(row.verified_false_positive_ratio)}</td><td><Link className={BUTTON} to={`/rules/${row.rule_id}/step-builder`}>Tune rule<ArrowRight size={14} /></Link></td></tr>)}</tbody></table>{feedback.isPending ? <p role="status" className="py-6 text-sm text-slate-300">Loading rule feedback...</p> : !feedback.data?.length && !feedback.error && <p className="py-6 text-sm text-slate-300">No verified rule feedback available.</p>}</div>}
	</div>;
}