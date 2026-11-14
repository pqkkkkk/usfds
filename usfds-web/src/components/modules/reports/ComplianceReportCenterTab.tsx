import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
	ClipboardCheck,
	Download,
	FileCode2,
	FileSpreadsheet,
	FileText,
	Printer,
	ShieldAlert,
	Sparkles,
} from 'lucide-react';
import { insightReportApi } from '@/api';
import { investigationApi } from '@/api/investigationApi';
import type { ReportScopeFilter } from '@/types';

interface ComplianceReportCenterTabProps {
	projectId: string;
	scope: ReportScopeFilter;
	initialCaseId?: string;
}

function formatCurrency(val: number | undefined | null): string {
	return `$${Number(val ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export const ComplianceReportCenterTab: React.FC<ComplianceReportCenterTabProps> = ({
	projectId,
	scope,
	initialCaseId,
}) => {
	const [template, setTemplate] = useState<'SAR_DOSSIER' | 'EXECUTIVE_AUDIT_REPORT'>(
		initialCaseId ? 'SAR_DOSSIER' : 'EXECUTIVE_AUDIT_REPORT'
	);
	const [selectedCaseId, setSelectedCaseId] = useState<string>(initialCaseId || '');
	const [preparedBy, setPreparedBy] = useState<string>('local-analyst');
	const [reviewerNotes, setReviewerNotes] = useState<string>('');

	// Load project cases for SAR Dossier selection
	const { data: casesPage } = useQuery({
		queryKey: ['cases-for-sar', projectId],
		queryFn: () => investigationApi.list(projectId, { page: 1, page_size: 100 }),
		enabled: Boolean(projectId),
	});

	const availableCases = casesPage?.items || [];

	useEffect(() => {
		if (initialCaseId) {
			setTemplate('SAR_DOSSIER');
			setSelectedCaseId(initialCaseId);
		} else if (!selectedCaseId && availableCases.length > 0) {
			const resolvedFraud = availableCases.find((c) => c.status === 'RESOLVED_FRAUD');
			setSelectedCaseId((resolvedFraud || availableCases[0]).case_id);
		}
	}, [initialCaseId, availableCases, selectedCaseId]);

	// Fetch SAR Dossier preview
	const { data: sarData, isLoading: isLoadingSar } = useQuery({
		queryKey: ['report-sar', projectId, selectedCaseId, preparedBy, reviewerNotes],
		queryFn: () => insightReportApi.getSarDossier(projectId, selectedCaseId, preparedBy, reviewerNotes),
		enabled: Boolean(projectId && template === 'SAR_DOSSIER' && selectedCaseId),
	});

	// Fetch Executive Audit Report preview
	const { data: execData, isLoading: isLoadingExec } = useQuery({
		queryKey: ['report-exec', projectId, scope, preparedBy, reviewerNotes],
		queryFn: () => insightReportApi.getExecutiveSummary(projectId, scope, preparedBy, reviewerNotes),
		enabled: Boolean(projectId && template === 'EXECUTIVE_AUDIT_REPORT'),
	});

	const triggerDownload = (format: 'md' | 'json' | 'csv' | 'html') => {
		if (template === 'SAR_DOSSIER' && !selectedCaseId) {
			return;
		}
		void insightReportApi.exportReport({
			projectId,
			template,
			format,
			caseId: template === 'SAR_DOSSIER' ? selectedCaseId : undefined,
			scope,
			preparedBy,
			reviewerNotes,
		});
	};

	const handlePrintPdf = () => {
		triggerDownload('html');
	};

	const s1 = sarData?.section_1_identification;
	const s2 = sarData?.section_2_financial_summary;
	const s3 = sarData?.section_3_detection_evidence;
	const s4 = sarData?.section_4_narrative_and_typology;
	const s5 = sarData?.section_5_mitigation_and_audit;
	const execKpis = execData?.section_1_financial_kpis;

	return (
		<div className="space-y-6">
			{/* Configuration & Export Control Bar */}
			<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-5 space-y-4">
				<div className="flex flex-wrap items-center justify-between gap-4">
					{/* Template Switcher */}
					<div className="flex items-center gap-2 bg-dark-950 p-1 rounded-xl border border-dark-800">
						<button
							type="button"
							onClick={() => setTemplate('EXECUTIVE_AUDIT_REPORT')}
							className={`px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-2 ${
								template === 'EXECUTIVE_AUDIT_REPORT'
									? 'bg-brand-600 text-white'
									: 'text-slate-400 hover:text-slate-200'
							}`}
						>
							<ClipboardCheck size={14} />
							<span>Executive Fraud & Policy Audit Report</span>
						</button>
						<button
							type="button"
							onClick={() => setTemplate('SAR_DOSSIER')}
							className={`px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-2 ${
								template === 'SAR_DOSSIER'
									? 'bg-brand-600 text-white'
									: 'text-slate-400 hover:text-slate-200'
							}`}
						>
							<ShieldAlert size={14} />
							<span>Suspicious Activity Report (SAR) Dossier</span>
						</button>
					</div>

					{/* Export Buttons */}
					<div className="flex flex-wrap items-center gap-2">
						<button
							type="button"
							onClick={handlePrintPdf}
							disabled={template === 'SAR_DOSSIER' && !selectedCaseId}
							className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-white text-xs font-semibold transition-colors cursor-pointer"
						>
							<Printer size={14} />
							<span>Print / Save PDF</span>
						</button>
						<button
							type="button"
							onClick={() => triggerDownload('md')}
							disabled={template === 'SAR_DOSSIER' && !selectedCaseId}
							className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 disabled:opacity-40 text-slate-200 border border-dark-700 text-xs font-medium transition-colors cursor-pointer"
						>
							<FileText size={14} className="text-cyan-400" />
							<span>.MD</span>
						</button>
						<button
							type="button"
							onClick={() => triggerDownload('json')}
							disabled={template === 'SAR_DOSSIER' && !selectedCaseId}
							className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 disabled:opacity-40 text-slate-200 border border-dark-700 text-xs font-medium transition-colors cursor-pointer"
						>
							<FileCode2 size={14} className="text-amber-400" />
							<span>.JSON</span>
						</button>
						<button
							type="button"
							onClick={() => triggerDownload('csv')}
							disabled={template === 'SAR_DOSSIER' && !selectedCaseId}
							className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 disabled:opacity-40 text-slate-200 border border-dark-700 text-xs font-medium transition-colors cursor-pointer"
						>
							<FileSpreadsheet size={14} className="text-emerald-400" />
							<span>.CSV</span>
						</button>
					</div>
				</div>

				{/* Metadata & Case Parameters */}
				<div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 border-t border-dark-800">
					{template === 'SAR_DOSSIER' && (
						<div>
							<label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
								Target Investigation Case
							</label>
							<select
								value={selectedCaseId}
								onChange={(e) => setSelectedCaseId(e.target.value)}
								className="w-full bg-dark-950 border border-dark-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-brand-500"
							>
								{availableCases.length === 0 ? (
									<option value="">No Investigation Cases Found</option>
								) : (
									availableCases.map((c) => (
										<option key={c.case_id} value={c.case_id}>
											[{c.status}] Event {c.event_id} • User {c.user_id} • {formatCurrency(c.amount)}
										</option>
									))
								)}
							</select>
						</div>
					)}

					<div>
						<label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
							Prepared By (Analyst / Compliance Officer)
						</label>
						<input
							type="text"
							value={preparedBy}
							onChange={(e) => setPreparedBy(e.target.value)}
							placeholder="local-analyst"
							className="w-full bg-dark-950 border border-dark-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-brand-500"
						/>
					</div>

					<div className={template === 'EXECUTIVE_AUDIT_REPORT' ? 'md:col-span-2' : ''}>
						<label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
							Reviewer Sign-Off Notes (Embedded in Export)
						</label>
						<input
							type="text"
							value={reviewerNotes}
							onChange={(e) => setReviewerNotes(e.target.value)}
							placeholder="Optional regulatory or audit sign-off remarks..."
							className="w-full bg-dark-950 border border-dark-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
						/>
					</div>
				</div>
			</div>

			{/* Interactive Document Preview */}
			{template === 'SAR_DOSSIER' ? (
				isLoadingSar ? (
					<div className="h-96 bg-dark-900 border border-dark-700/80 rounded-xl animate-pulse" />
				) : !sarData || !s1 || !s2 || !s3 || !s4 || !s5 ? (
					<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-10 text-center text-xs text-slate-400">
						Select a dispatched case above to preview its 5-section Suspicious Activity Report (SAR) Dossier.
					</div>
				) : (
					<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-6 space-y-6">
						{/* Document Header */}
						<div className="border-b border-dark-700 pb-4 flex flex-wrap items-start justify-between gap-4">
							<div>
								<div className="text-[11px] font-mono uppercase tracking-widest text-brand-400">
									REGULATORY COMPLIANCE DOSSIER • {sarData.report_id}
								</div>
								<h2 className="text-lg font-bold text-slate-100 mt-1">
									Suspicious Activity Report (SAR) — Case {s1.case_code} (Event {s2.primary_event_id})
								</h2>
								<p className="text-xs text-slate-400 font-mono mt-1">
									Project: {sarData.project_name} • Prepared By: {sarData.prepared_by} • Generated:{' '}
									{sarData.generated_at}
								</p>
							</div>
							<span className="px-3 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 font-mono text-xs font-bold text-emerald-300">
								{s1.verdict || s1.status}
							</span>
						</div>

						{/* Part I & Part II */}
						<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
							<div className="bg-dark-950 border border-dark-800 rounded-xl p-4 space-y-2">
								<h3 className="text-xs font-bold uppercase tracking-wider text-brand-300">
									Part I — Subject & Case Identification
								</h3>
								<div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
									<div className="text-slate-400">Case ID / Code:</div>
									<div className="text-slate-200 truncate">
										{s1.case_code} ({s1.case_id.slice(0, 8)})
									</div>
									<div className="text-slate-400">Subject (`user_id`):</div>
									<div className="text-slate-100 font-bold">{s1.subject_user_id}</div>
									<div className="text-slate-400">Priority / Score:</div>
									<div className="text-amber-300">
										{s1.priority} ({s1.priority_score})
									</div>
									<div className="text-slate-400">Assigned / Resolved By:</div>
									<div className="text-slate-200">
										{s1.assigned_to} / {s1.resolved_by}
									</div>
									<div className="text-slate-400">Watchlist Status:</div>
									<div className="text-rose-400 font-bold">
										{s5.is_subject_blacklisted ? 'ACTIVE ON BLACKLIST' : 'Not Listed'}
									</div>
								</div>
							</div>

							<div className="bg-dark-950 border border-dark-800 rounded-xl p-4 space-y-2">
								<h3 className="text-xs font-bold uppercase tracking-wider text-emerald-300">
									Part II — Financial Impact Summary
								</h3>
								<div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
									<div className="text-slate-400">Primary Event ID:</div>
									<div className="text-slate-100 font-bold">{s2.primary_event_id}</div>
									<div className="text-slate-400">Primary Amount:</div>
									<div className="text-emerald-400 font-bold text-sm">
										{formatCurrency(s2.primary_amount)} ({s2.final_action})
									</div>
									<div className="text-slate-400">Subject Exposure:</div>
									<div className="text-amber-300">
										{formatCurrency(s2.total_subject_exposure)} ({s2.subject_flagged_tx_count} txs)
									</div>
									<div className="text-slate-400">Event Timestamp:</div>
									<div className="text-slate-200">{s2.primary_tx_timestamp}</div>
								</div>
							</div>
						</div>

						{/* Part III: Hybrid Detection Evidence */}
						<div className="bg-dark-950 border border-dark-800 rounded-xl p-4 space-y-4">
							<div className="flex items-center justify-between">
								<h3 className="text-xs font-bold uppercase tracking-wider text-cyan-300">
									Part III — Hybrid Detection Evidence (XGBoost + SHAP + Rules)
								</h3>
								<span className="text-xs font-mono px-2.5 py-0.5 rounded bg-cyan-500/15 border border-cyan-500/30 text-cyan-300">
									XGBoost Score: {s3.model_score != null ? s3.model_score.toFixed(4) : 'N/A'}
								</span>
							</div>

							<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
								{/* Top SHAP */}
								<div>
									<div className="text-[11px] font-semibold uppercase text-slate-400 mb-2">
										Top SHAP Feature Contributions
									</div>
									{(s3.top_feature_contributions || []).length === 0 ? (
										<div className="text-xs text-slate-500">No SHAP telemetry recorded</div>
									) : (
										<div className="space-y-1.5">
											{s3.top_feature_contributions.map((sc) => (
												<div
													key={sc.feature_name}
													className="flex items-center justify-between text-xs font-mono bg-dark-900 px-3 py-1.5 rounded border border-dark-800"
												>
													<span className="text-slate-200">
														{sc.feature_name} ={' '}
														<span className="text-slate-400">{String(sc.feature_value)}</span>
													</span>
													<span
														className={
															sc.shap_value >= 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'
														}
													>
														{sc.shap_value >= 0 ? '+' : ''}
														{sc.shap_value.toFixed(4)}
													</span>
												</div>
											))}
										</div>
									)}
								</div>

								{/* Triggered Rules */}
								<div>
									<div className="text-[11px] font-semibold uppercase text-slate-400 mb-2">
										Triggered Policy Rules
									</div>
									{(s3.violated_rules || []).length === 0 ? (
										<div className="text-xs text-slate-500">No deterministic rules triggered</div>
									) : (
										<div className="space-y-1.5">
											{s3.violated_rules.map((tr) => (
												<div
													key={`${tr.rule_code}-${tr.version_number}`}
													className="flex items-center justify-between text-xs font-mono bg-dark-900 px-3 py-1.5 rounded border border-dark-800"
												>
													<div>
														<span className="text-amber-300 font-bold">{tr.rule_code}</span>{' '}
														<span className="text-slate-300">({tr.rule_name})</span>
														<div className="text-[11px] text-slate-400">{tr.trigger_reason}</div>
													</div>
													<span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 text-[10px]">
														{tr.action}
													</span>
												</div>
											))}
										</div>
									)}
								</div>
							</div>
						</div>

						{/* Part IV: Investigation Narrative */}
						<div className="bg-dark-950 border border-dark-800 rounded-xl p-4 space-y-2">
							<h3 className="text-xs font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
								<Sparkles size={13} />
								<span>
									Part IV — Investigation Narrative & Typology ({s4.fraud_typology_label})
								</span>
							</h3>
							<p className="text-xs text-slate-200 leading-relaxed">
								{s4.automated_technical_narrative}
							</p>
							{s4.analyst_resolution_summary && (
								<div className="text-xs font-mono text-emerald-300 pt-1">
									Analyst Resolution Summary: {s4.analyst_resolution_summary}
								</div>
							)}
						</div>

						{/* Part V: Immutable Chain-of-Custody Audit Trail */}
						<div className="bg-dark-950 border border-dark-800 rounded-xl p-4 space-y-2">
							<h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
								Part V — Mitigation & Immutable Chain-of-Custody Audit Trail (
								{(s5.audit_trail || []).length} events)
							</h3>
							<div className="overflow-x-auto">
								<table className="w-full text-left border-collapse text-xs font-mono">
									<thead>
										<tr className="border-b border-dark-800 text-[11px] text-slate-400">
											<th className="py-1.5 px-2">Timestamp (UTC)</th>
											<th className="py-1.5 px-2">Actor</th>
											<th className="py-1.5 px-2">Action</th>
											<th className="py-1.5 px-2">Note / Details</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-dark-800/60">
										{(s5.audit_trail || []).map((log) => (
											<tr key={log.log_id}>
												<td className="py-1.5 px-2 text-slate-400">{log.created_at}</td>
												<td className="py-1.5 px-2 text-brand-300">{log.actor}</td>
												<td className="py-1.5 px-2 text-slate-100 font-semibold">{log.action}</td>
												<td className="py-1.5 px-2 text-slate-400 truncate max-w-md">
													{log.note || JSON.stringify(log.details)}
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						</div>
					</div>
				)
			) : isLoadingExec ? (
				<div className="h-96 bg-dark-900 border border-dark-700/80 rounded-xl animate-pulse" />
			) : !execData || !execKpis ? null : (
				<div className="bg-dark-900 border border-dark-700/80 rounded-xl p-6 space-y-6">
					<div className="border-b border-dark-700 pb-4 flex flex-wrap items-start justify-between gap-4">
						<div>
							<div className="text-[11px] font-mono uppercase tracking-widest text-brand-400">
								EXECUTIVE AUDIT REPORT • {execData.report_id}
							</div>
							<h2 className="text-lg font-bold text-slate-100 mt-1">
								Executive Fraud & Policy Audit Report — {execData.project_name}
							</h2>
							<p className="text-xs text-slate-400 font-mono mt-1">
								Prepared By: {execData.prepared_by} • Generated: {execData.generated_at} • Ground Truth:{' '}
								{execKpis.label_source}
							</p>
						</div>
						<button
							type="button"
							onClick={() => triggerDownload('md')}
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 text-xs text-slate-200 border border-dark-700 cursor-pointer"
						>
							<Download size={13} />
							<span>Export Full Report</span>
						</button>
					</div>

					{/* Executive Summary Preview Grid */}
					<div className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono">
						<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
							<div className="text-[11px] text-slate-400">Gross Scanned</div>
							<div className="text-base font-bold text-slate-100 mt-1">
								{formatCurrency(execKpis.gross_scanned_volume)}
							</div>
						</div>
						<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
							<div className="text-[11px] text-emerald-400">Confirmed Fraud Prevented</div>
							<div className="text-base font-bold text-emerald-400 mt-1">
								{formatCurrency(execKpis.confirmed_fraud_loss_prevented)}
							</div>
						</div>
						<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
							<div className="text-[11px] text-rose-400">FP Friction (Insult Rate)</div>
							<div className="text-base font-bold text-rose-400 mt-1">
								{formatCurrency(execKpis.false_positive_friction_volume)} (
								{((execKpis.insult_rate ?? 0) * 100).toFixed(2)}%)
							</div>
						</div>
						<div className="bg-dark-950 border border-dark-800 rounded-lg p-3">
							<div className="text-[11px] text-cyan-400">Verified Precision</div>
							<div className="text-base font-bold text-cyan-400 mt-1">
								{execKpis.verified_precision != null
									? `${(execKpis.verified_precision * 100).toFixed(1)}%`
									: '—'}
							</div>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};
