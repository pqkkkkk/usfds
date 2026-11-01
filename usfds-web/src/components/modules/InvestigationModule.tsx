import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
	SearchCheck,
	RefreshCw,
	Search,
	ShieldAlert,
	ExternalLink,
	X,
	Cpu,
	ShieldCheck,
} from 'lucide-react';
import { PageHeader } from '../layout/PageHeader';
import { detectionApi } from '@/api';
import { useProject } from '@/hooks';
import type { InvestigationCaseResponse } from '@/types';

export const InvestigationModule = () => {
	const navigate = useNavigate();
	const { currentProject } = useProject();
	const projectId = currentProject?.project_id || '';

	const [searchQuery, setSearchQuery] = useState('');
	const [selectedCase, setSelectedCase] =
		useState<InvestigationCaseResponse | null>(null);

	const {
		data: casesRes,
		isLoading,
		refetch,
		isFetching,
	} = useQuery({
		queryKey: ['investigation-cases', projectId],
		queryFn: () => detectionApi.listCases({ projectId }),
		enabled: Boolean(projectId),
	});

	const cases = useMemo(() => {
		const raw = casesRes?.data || [];
		if (!searchQuery.trim()) {
			return raw;
		}
		const q = searchQuery.trim().toLowerCase();
		return raw.filter((c) => {
			const evId = String(c.metadata?.raw_event_id || c.event_id).toLowerCase();
			const userId = String(c.metadata?.user_id || '').toLowerCase();
			const jobName = String(c.metadata?.job_name || '').toLowerCase();
			return evId.includes(q) || userId.includes(q) || jobName.includes(q);
		});
	}, [casesRes, searchQuery]);

	return (
		<div className="flex-1 flex flex-col overflow-hidden bg-dark-950 relative">
			<PageHeader
				title="Investigation & Case Review Queue"
				subtitle="Hàng đợi rà soát các giao dịch nghi vấn được chuyển từ các phiên quét Detection Jobs"
				badge="Case Queue"
				badgeColor="amber"
				breadcrumbs={[
					{ label: currentProject?.project_name || 'Project' },
					{ label: 'Investigation Queue' },
				]}
				actions={
					<button
						type="button"
						onClick={() => refetch()}
						disabled={isFetching}
						className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs font-medium text-slate-300 flex items-center gap-1.5 transition"
					>
						<RefreshCw
							className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-amber-400' : ''}`}
						/>
						Refresh Cases
					</button>
				}
			/>

			<div className="flex-1 overflow-y-auto p-6 space-y-5">
				<div className="flex items-center justify-between gap-3 p-3.5 rounded-xl bg-dark-900 border border-dark-800">
					<div className="relative flex-1 max-w-md">
						<Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
						<input
							type="text"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							placeholder="Search by event ID, user ID, or source detection job..."
							className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-dark-950 border border-dark-700 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500"
						/>
					</div>
					<span className="text-xs font-mono text-slate-400">
						{cases.length} case(s) in queue
					</span>
				</div>

				<div className="rounded-xl bg-dark-900 border border-dark-800 overflow-hidden">
					{isLoading ? (
						<div className="p-12 text-center text-xs text-slate-400">
							Loading investigation cases...
						</div>
					) : cases.length === 0 ? (
						<div className="p-12 text-center space-y-3 max-w-md mx-auto">
							<SearchCheck className="w-8 h-8 text-amber-400 mx-auto" />
							<h3 className="text-sm font-semibold text-slate-100">
								No Investigation Cases Dispatched Yet
							</h3>
							<p className="text-xs text-slate-400">
								Khi phân tích kết quả của một Detection Job, bạn có thể chọn các giao dịch bị gắn cờ (REJECT / REVIEW) và nhấn "Send to Investigation" để chuyển sang hàng đợi điều tra này.
							</p>
							<button
								type="button"
								onClick={() => navigate('/detection')}
								className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white transition"
							>
								Go to Detection Jobs
							</button>
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-left border-collapse">
								<thead>
									<tr className="border-b border-dark-800 bg-dark-950/60 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
										<th className="py-3 px-4">Case ID</th>
										<th className="py-3 px-4">Transaction Event</th>
										<th className="py-3 px-4">Source Detection Job</th>
										<th className="py-3 px-4">Risk Level</th>
										<th className="py-3 px-4 text-right">Amount</th>
										<th className="py-3 px-4">AI Score & Decision</th>
										<th className="py-3 px-4">Analyst Notes</th>
										<th className="py-3 px-4">Created</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800/70 text-xs">
									{cases.map((c) => {
										const meta = c.metadata || {};
										const rawEvId = meta.raw_event_id || String(c.event_id);
										const amt = meta.amount ?? 0;
										const triggered = meta.triggered_rules || [];

										return (
											<tr
												key={c.case_id}
												onClick={() => setSelectedCase(c)}
												className="hover:bg-dark-850/70 cursor-pointer transition"
											>
												<td className="py-3.5 px-4 font-mono text-amber-300 font-semibold">
													#{c.case_id.slice(0, 8)}
												</td>
												<td className="py-3.5 px-4">
													<div className="font-mono font-semibold text-slate-100">
														Event: {rawEvId}
													</div>
													<div className="text-[11px] font-mono text-slate-400">
														User: {meta.user_id || '—'}
													</div>
												</td>
												<td className="py-3.5 px-4">
													{meta.job_id ? (
														<button
															type="button"
															onClick={(e) => {
																e.stopPropagation();
																navigate(`/detection/jobs/${meta.job_id}`);
															}}
															className="text-brand-400 hover:underline font-medium inline-flex items-center gap-1"
														>
															{meta.job_name || meta.job_id.slice(0, 8)}
															<ExternalLink className="w-3 h-3" />
														</button>
													) : (
														<span className="text-slate-500">—</span>
													)}
												</td>
												<td className="py-3.5 px-4">
													<span
														className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
															c.risk_level === 'CRITICAL'
																? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
																: 'bg-amber-500/15 text-amber-300 border-amber-500/30'
														}`}
													>
														{c.risk_level}
													</span>
												</td>
												<td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-200">
													${Number(amt || 0).toLocaleString(undefined, {
														minimumFractionDigits: 2,
														maximumFractionDigits: 2,
													})}
												</td>
												<td className="py-3.5 px-4">
													<div className="font-mono text-slate-200">
														Score: {(c.fraud_probability ?? 0).toFixed(4)} (
														{c.action_taken || 'REVIEW'})
													</div>
													{triggered.length > 0 && (
														<div className="text-[10px] font-mono text-amber-300 mt-0.5">
															Rules: {triggered.join(', ')}
														</div>
													)}
												</td>
												<td className="py-3.5 px-4 text-slate-300 max-w-xs truncate">
													{c.analyst_notes || '—'}
												</td>
												<td className="py-3.5 px-4 font-mono text-[11px] text-slate-500">
													{new Date(c.created_at).toLocaleString()}
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

			{/* Case Evidence Drawer */}
			{selectedCase && (
				<div className="fixed inset-y-0 right-0 z-40 w-full max-w-lg bg-dark-900 border-l border-dark-700 shadow-2xl flex flex-col">
					<div className="p-5 border-b border-dark-800 bg-dark-950 flex items-center justify-between">
						<div>
							<div className="flex items-center gap-2">
								<ShieldAlert className="w-4 h-4 text-amber-400" />
								<span className="text-sm font-bold font-mono text-slate-100">
									Case #{selectedCase.case_id.slice(0, 8)}
								</span>
								<span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30">
									{selectedCase.status}
								</span>
							</div>
							<p className="text-[11px] text-slate-400 font-mono mt-0.5">
								Event ID: {selectedCase.metadata?.raw_event_id || selectedCase.event_id}
							</p>
						</div>
						<button
							type="button"
							onClick={() => setSelectedCase(null)}
							className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800"
						>
							<X className="w-4 h-4" />
						</button>
					</div>

					<div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
						{selectedCase.analyst_notes && (
							<div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200">
								<div className="text-[10px] font-bold uppercase tracking-wider text-amber-400 mb-1">
									Analyst Triage Notes
								</div>
								{selectedCase.analyst_notes}
							</div>
						)}

						<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2">
							<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
								<Cpu className="w-3.5 h-3.5 text-brand-400" />
								Detection Snapshot
							</div>
							<div className="grid grid-cols-2 gap-2 pt-1 font-mono">
								<div>
									<span className="text-slate-500 block text-[10px]">
										Decision Action
									</span>
									<span className="text-slate-100 font-bold">
										{selectedCase.action_taken || 'REVIEW'}
									</span>
								</div>
								<div>
									<span className="text-slate-500 block text-[10px]">
										AI Model Score
									</span>
									<span className="text-slate-100 font-bold">
										{(selectedCase.fraud_probability ?? 0).toFixed(4)}
									</span>
								</div>
							</div>
						</div>

						{selectedCase.metadata?.triggered_rule_details &&
							selectedCase.metadata.triggered_rule_details.length > 0 && (
								<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2">
									<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
										<ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
										Triggered Rules
									</div>
									{selectedCase.metadata.triggered_rule_details.map((rd) => (
										<div
											key={rd.rule_code}
											className="p-2.5 rounded-lg bg-dark-900 border border-dark-800 font-mono text-[11px]"
										>
											<div className="font-bold text-slate-200">
												{rd.rule_code} ({rd.action}) — {rd.rule_name}
											</div>
											{rd.matched_clauses?.map((c, idx) => (
												<div key={idx} className="text-amber-300 mt-0.5">
													• {c}
												</div>
											))}
										</div>
									))}
								</div>
							)}

						<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2">
							<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
								Transaction Features
							</div>
							<div className="divide-y divide-dark-800/70 max-h-64 overflow-y-auto pr-1">
								{Object.entries(selectedCase.metadata?.features || {}).map(
									([k, v]) => (
										<div
											key={k}
											className="py-1.5 flex items-center justify-between gap-4 font-mono text-[11px]"
										>
											<span className="text-slate-400">{k}</span>
											<span className="text-slate-200 truncate max-w-[220px]">
												{v === null || v === undefined ? 'null' : String(v)}
											</span>
										</div>
									)
								)}
							</div>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};
