import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle2 } from 'lucide-react';
import { investigationApi } from '../../../api/investigationApi';
import type { CaseAction } from '../../../types/investigation';
import {
	BUTTON_SECONDARY_CLASS,
	ErrorNotice,
	StatusBadge,
} from './investigationShared';
import {
	EvidenceAndTimelineColumn,
	SubjectAndBaselineColumn,
} from './WorkbenchPanels';
import { DecisionAndAuditColumn } from './WorkbenchResolutionColumn';

export function CaseWorkbenchView({
	projectId,
	readOnly,
}: {
	projectId: string;
	readOnly: boolean;
}) {
	const { caseId = '' } = useParams();
	return (
		<CaseWorkbench
			key={`${projectId}:${caseId}`}
			projectId={projectId}
			caseId={caseId}
			readOnly={readOnly}
		/>
	);
}

function CaseWorkbench({
	projectId,
	caseId,
	readOnly,
}: {
	projectId: string;
	caseId: string;
	readOnly: boolean;
}) {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [days, setDays] = useState<30 | 90>(30);
	const [autoAdvance, setAutoAdvance] = useState<boolean>(false);
	const [notice, setNotice] = useState<string>('');

	const workbenchQuery = useQuery({
		queryKey: ['investigation', projectId, 'workbench', caseId, days],
		queryFn: () => investigationApi.workbench(projectId, caseId, days),
	});

	const mutation = useMutation({
		mutationFn: async ({
			action,
			payload,
			noteText,
		}: {
			action: string;
			payload: CaseAction;
			noteText?: string;
		}) => {
			if (action === 'note') {
				return investigationApi.note(projectId, caseId, noteText || '');
			}
			return investigationApi.action(projectId, caseId, action, payload);
		},
		onSuccess: async (res, variables) => {
			await queryClient.invalidateQueries({
				queryKey: ['investigation', projectId],
			});
			const relatedWarning =
				typeof res === 'object' &&
				res !== null &&
				'related_assignees' in res &&
				res.related_assignees.length > 0
					? ` (Other open cases for this user assigned to: ${res.related_assignees.join(', ')})`
					: '';
			setNotice(`Case updated successfully.${relatedWarning}`);

			if (variables.action === 'resolve' && autoAdvance) {
				try {
					const nextQueue = await investigationApi.list(projectId, {
						status: 'OPEN',
						sort: 'priority',
						page: 1,
						size: 5,
					});
					const nextCase = nextQueue.items.find((c) => c.case_id !== caseId);
					if (nextCase) {
						navigate(`/investigation/cases/${nextCase.case_id}`);
					}
				} catch {
					// Stay on current case if next lookup fails
				}
			}
		},
		onError: () => {
			void workbenchQuery.refetch();
		},
	});

	const draftMutation = useMutation({
		mutationFn: () => investigationApi.draft(projectId, caseId),
		onSuccess: (data) =>
			navigate('/rules/new', {
				state: { investigationDraft: { ...data, project_id: projectId } },
			}),
	});

	if (workbenchQuery.isPending) {
		return (
			<div
				role="status"
				className="rounded-xl border border-dark-700/80 bg-dark-900 p-8 text-center text-sm text-slate-300"
			>
				Loading case investigation workbench...
			</div>
		);
	}

	if (!workbenchQuery.data) {
		return (
			<div className="space-y-4">
				<Link to="/investigation" className={BUTTON_SECONDARY_CLASS}>
					<ArrowLeft size={15} />
					<span>Back to Case Queue</span>
				</Link>
				<ErrorNotice error={workbenchQuery.error} />
			</div>
		);
	}

	const { case: item } = workbenchQuery.data;
	const disabled = mutation.isPending || readOnly || workbenchQuery.isFetching;

	return (
		<div className="space-y-4">
			<div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-dark-700/80 bg-dark-900 px-4 py-3 shadow-sm">
				<div className="flex flex-wrap items-center gap-3">
					<Link to="/investigation" className={BUTTON_SECONDARY_CLASS}>
						<ArrowLeft size={15} />
						<span>Case Queue</span>
					</Link>
					<div>
						<h1 className="break-all font-mono text-base font-bold text-slate-100">
							{item.case_code}
						</h1>
						<p className="font-mono text-[11px] text-slate-400">
							Event {item.event_id} &bull; User {item.user_id}
						</p>
					</div>
				</div>

				<div className="flex flex-wrap items-center gap-3">
					<label className="inline-flex items-center gap-2 rounded-lg border border-dark-700 bg-dark-950 px-3 py-1.5 text-xs text-slate-300 cursor-pointer">
						<input
							type="checkbox"
							checked={autoAdvance}
							onChange={(event) => setAutoAdvance(event.target.checked)}
						/>
						<span>Auto-advance queue</span>
					</label>
					<StatusBadge value={item.priority} />
					<StatusBadge value={item.status} />
					<span className="rounded border border-dark-700 bg-dark-950 px-2 py-1 font-mono text-[11px] text-slate-400">
						v{item.version}
					</span>
				</div>
			</div>

			<ErrorNotice
				error={workbenchQuery.error || mutation.error || draftMutation.error}
			/>

			{notice && (
				<div
					role="status"
					className="flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-950/30 px-4 py-2.5 text-xs text-emerald-200"
				>
					<CheckCircle2 size={15} className="shrink-0 text-emerald-400" />
					<span>{notice}</span>
				</div>
			)}

			<div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1fr)]">
				<SubjectAndBaselineColumn
					data={workbenchQuery.data}
					days={days}
					onChangeDays={setDays}
				/>
				<EvidenceAndTimelineColumn data={workbenchQuery.data} />
				<DecisionAndAuditColumn
					data={workbenchQuery.data}
					disabled={disabled}
					draftPending={draftMutation.isPending}
					onMutate={(action, payload, noteText) =>
						mutation.mutate({ action, payload, noteText })
					}
					onCreateRuleDraft={() => draftMutation.mutate()}
				/>
			</div>
		</div>
	);
}

