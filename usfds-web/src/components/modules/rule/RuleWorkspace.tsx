import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
	Save,
	ShieldCheck,
	FileCode2,
	ArrowLeft,
	ArrowRight,
	Loader2,
} from 'lucide-react';
import { PageHeader } from '../../layout/PageHeader';
import { WorkspaceStepper, type PipelineStep } from '../../layout/WorkspaceStepper';
import { RuleStudioWorkspace } from './RuleStudioWorkspace';
import { RuleDryRunWorkspace } from './RuleDryRunWorkspace';
import { RuleVersionHistoryModal } from './RuleVersionHistoryModal';
import type {
	RuleResponse,
	RuleGroup,
	RuleAction,
	RuleStatus,
	RuleVersionResponse,
} from '../../../types/rule';
import {
	buildAvailableFieldsFromRawSchema,
	createDefaultRuleGroupForSchema,
	groupToJsonLogic,
	jsonLogicToGroup,
} from '../../../utils/jsonLogicParser';
import { ruleApi } from '../../../api/ruleApi';
import { useProject } from '../../../hooks/useProjects';

const FALLBACK_PROJECT_ID = '11111111-1111-1111-1111-111111111111';

export const RuleWorkspace: React.FC = () => {
	const { ruleId, stepId = 'step-builder' } = useParams<{
		ruleId?: string;
		stepId?: string;
	}>();
	const navigate = useNavigate();
	const { currentProject, currentProjectId, refetchProjects } = useProject();
	const effectiveProjectId = currentProjectId || FALLBACK_PROJECT_ID;

	const isNew = !ruleId || ruleId === 'new';
	const isSchemaLocked = Boolean(currentProject?.is_schema_locked);
	const availableFields = useMemo(
		() => buildAvailableFieldsFromRawSchema(currentProject?.raw_schema),
		[currentProject?.raw_schema]
	);

	const [currentRule, setCurrentRule] = useState<RuleResponse | null>(null);
	const [ruleCode, setRuleCode] = useState<string>('R-001');
	const [ruleName, setRuleName] = useState<string>('Quy tắc nghiệp vụ mới');
	const [status, setStatus] = useState<RuleStatus>('DRAFT');
	const [action, setAction] = useState<RuleAction>('REVIEW');
	const [description, setDescription] = useState<string>('');
	const [changeSummary, setChangeSummary] = useState<string>('Khởi tạo quy tắc');
	const [conditionGroup, setConditionGroup] = useState<RuleGroup>(() =>
		createDefaultRuleGroupForSchema(currentProject?.raw_schema)
	);

	const [loading, setLoading] = useState<boolean>(false);
	const [isSaving, setIsSaving] = useState<boolean>(false);
	const [saveSuccessNotice, setSaveSuccessNotice] = useState<boolean>(false);
	const [errorMessage, setErrorMessage] = useState<string | null>(null);

	// Modal version history
	const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);

	useEffect(() => {
		setErrorMessage(null);
		if (!isNew && ruleId) {
			setLoading(true);
			ruleApi.getRule(ruleId).then((res) => {
				if (res.success && res.data) {
					const rule = res.data;
					setCurrentRule(rule);
					setRuleCode(rule.rule_code);
					setRuleName(rule.name);
					setStatus(rule.status);
					setDescription(rule.description || '');
					if (rule.current_version) {
						setAction(rule.current_version.action);
						setConditionGroup(jsonLogicToGroup(rule.current_version.condition));
						setChangeSummary(
							`Cập nhật từ v${rule.current_version.version_number}`
						);
					}
				} else {
					setErrorMessage(res.error || 'Không tìm thấy quy tắc nghiệp vụ.');
				}
				setLoading(false);
			});
		} else {
			// New rule template tailored to currentProject.raw_schema
			const randomSuffix = Math.floor(100 + Math.random() * 900);
			setCurrentRule(null);
			setRuleCode(`R-${randomSuffix}`);
			setRuleName('Quy tắc phát hiện gian lận mới');
			setStatus('DRAFT');
			setAction('REVIEW');
			setDescription('Mô tả điều kiện phát hiện gian lận.');
			setChangeSummary('Khởi tạo phiên bản v1');
			setConditionGroup(createDefaultRuleGroupForSchema(currentProject?.raw_schema));
		}
	}, [ruleId, isNew, currentProject?.raw_schema]);

	const handleSave = async (targetStatus?: RuleStatus): Promise<RuleResponse | null> => {
		setIsSaving(true);
		setErrorMessage(null);
		try {
			const compiledJsonLogic = groupToJsonLogic(conditionGroup);
			const chosenStatus = targetStatus || status;

			if (!isNew && ruleId) {
				// 1. Update rule metadata & condition
				const res = await ruleApi.updateRule(ruleId, {
					name: ruleName,
					description,
					condition: compiledJsonLogic,
					action,
					change_summary: changeSummary,
				});
				if (!res.success || !res.data) {
					setErrorMessage(res.error || 'Không thể cập nhật quy tắc.');
					return null;
				}
				let updatedRule = res.data;

				// 2. Update status if changed
				if (chosenStatus !== updatedRule.status) {
					const statusRes = await ruleApi.setRuleStatus(ruleId, chosenStatus);
					if (!statusRes.success || !statusRes.data) {
						setErrorMessage(statusRes.error || 'Đã lưu điều kiện nhưng không thể đổi trạng thái.');
						setCurrentRule(updatedRule);
						return null;
					}
					updatedRule = statusRes.data;
				}

				setCurrentRule(updatedRule);
				setStatus(updatedRule.status);
				setSaveSuccessNotice(true);
				refetchProjects();
				setTimeout(() => setSaveSuccessNotice(false), 3000);
				return updatedRule;
			} else {
				// Create new rule
				const res = await ruleApi.createRule({
					project_id: effectiveProjectId,
					rule_code: ruleCode.trim(),
					name: ruleName.trim(),
					description,
					condition: compiledJsonLogic,
					action,
					status: chosenStatus,
					change_summary: changeSummary,
				});
				if (!res.success || !res.data) {
					setErrorMessage(res.error || 'Không thể khởi tạo quy tắc mới.');
					return null;
				}
				setCurrentRule(res.data);
				setStatus(res.data.status);
				setSaveSuccessNotice(true);
				refetchProjects();
				setTimeout(() => {
					navigate(`/rules/${res.data.rule_id}/${stepId}`, { replace: true });
				}, 400);
				return res.data;
			}
		} finally {
			setIsSaving(false);
		}
	};

	const handleStepSelect = (nextStepId: string) => {
		const targetRuleId = currentRule?.rule_id || (isNew ? 'new' : ruleId);
		navigate(`/rules/${targetRuleId}/${nextStepId}`);
	};

	const handleProceedToDryRun = async () => {
		if (isNew && !currentRule) {
			const saved = await handleSave('DRAFT');
			if (saved) {
				navigate(`/rules/${saved.rule_id}/step-dryrun`);
			}
			return;
		}
		const targetRuleId = currentRule?.rule_id || ruleId || 'new';
		navigate(`/rules/${targetRuleId}/step-dryrun`);
	};

	const handleRestoreVersion = (version: RuleVersionResponse) => {
		setAction(version.action);
		setConditionGroup(jsonLogicToGroup(version.condition));
		setChangeSummary(`Khôi phục từ version v${version.version_number}`);
	};

	const pipelineSteps: PipelineStep[] = [
		{
			id: 'step-builder',
			stepNumber: 1,
			label: 'Rule Studio Builder',
			description: 'Logic DSL & Condition Tree',
			state: stepId === 'step-builder' ? 'active' : 'completed',
		},
		{
			id: 'step-dryrun',
			stepNumber: 2,
			label: 'Dry Run Simulation',
			description: 'Historical Backtest & Telemetry',
			state: stepId === 'step-dryrun' ? 'active' : 'completed',
		},
	];

	const currentStep = pipelineSteps.find((s) => s.id === stepId) || pipelineSteps[0];

	return (
		<div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
			{/* 1. Common PageHeader */}
			<PageHeader
				title={
					stepId === 'step-builder'
						? `${ruleCode} - ${ruleName}`
						: `Dry Run: ${ruleCode}`
				}
				badgeColor={stepId === 'step-builder' ? 'blue' : 'purple'}
				breadcrumbs={[
					{ label: 'Rule Management', tab: 'catalog' },
					{ label: ruleCode || 'Rule Studio', tab: 'builder' },
					{ label: currentStep.label },
				]}
				onNavigate={(tab) => {
					if (tab === 'catalog') navigate('/rules');
					if (tab === 'builder') {
						const targetRuleId = currentRule?.rule_id || ruleId || 'new';
						navigate(`/rules/${targetRuleId}/step-builder`);
					}
				}}
				actions={
					<div className="flex items-center gap-2.5">
						{/* Back Button */}
						{stepId === 'step-builder' ? (
							<button
								type="button"
								onClick={() => navigate('/rules')}
								className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-slate-800 text-slate-300 text-xs font-medium transition flex items-center gap-1.5 cursor-pointer"
							>
								<ArrowLeft className="w-3.5 h-3.5 text-slate-400" />
								<span>Danh mục Rules</span>
							</button>
						) : (
							<button
								type="button"
								onClick={() => handleStepSelect('step-builder')}
								className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-slate-800 text-slate-300 text-xs font-medium transition flex items-center gap-1.5 cursor-pointer"
							>
								<ArrowLeft className="w-3.5 h-3.5 text-slate-400" />
								<span>Về Studio Builder</span>
							</button>
						)}

						{/* Version History Modal Trigger */}
						{!isNew && (
							<button
								type="button"
								onClick={() => setIsVersionModalOpen(true)}
								className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-slate-800 text-slate-300 text-xs font-medium transition flex items-center gap-1.5 cursor-pointer"
								title="Lịch sử phiên bản"
							>
								<FileCode2 className="w-3.5 h-3.5 text-slate-400" />
								<span>Versions</span>
							</button>
						)}

						{/* Step 1 Actions */}
						{stepId === 'step-builder' && (
							<>
								<button
									type="button"
									disabled={isSaving}
									onClick={() => handleSave()}
									className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-slate-800 text-slate-200 text-xs font-medium transition flex items-center gap-1.5 cursor-pointer"
								>
									{isSaving ? (
										<Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400" />
									) : (
										<Save className="w-3.5 h-3.5 text-brand-400" />
									)}
									<span>{isNew ? 'Save Rule' : 'Save Changes'}</span>
								</button>

								<button
									type="button"
									onClick={handleProceedToDryRun}
									disabled={isSaving}
									className="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-1.5 cursor-pointer"
								>
									<span>Chuyển sang Dry Run</span>
									<ArrowRight className="w-3.5 h-3.5" />
								</button>
							</>
						)}

						{/* Step 2 Actions */}
						{stepId === 'step-dryrun' && (
							<button
								type="button"
								disabled={isSaving || !isSchemaLocked}
								onClick={() => handleSave('ACTIVE')}
								title={
									!isSchemaLocked
										? 'Cần tải lên Dataset đầu tiên để khóa RAW Schema trước khi kích hoạt ACTIVE (BR-PM-04)'
										: 'Lưu và kích hoạt quy tắc sang trạng thái ACTIVE'
								}
								className="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2 cursor-pointer"
							>
								{isSaving ? (
									<Loader2 className="w-3.5 h-3.5 animate-spin" />
								) : (
									<ShieldCheck className="w-3.5 h-3.5" />
								)}
								<span>{isSaving ? 'Đang lưu...' : 'Triển khai & Kích hoạt'}</span>
							</button>
						)}
					</div>
				}
			/>

			{/* 2. Workspace Stepper */}
			<WorkspaceStepper
				steps={pipelineSteps}
				currentStepId={stepId}
				onSelectStep={handleStepSelect}
			/>

			{/* 3. Workspace Body */}
			<div className="flex-1 flex flex-col overflow-hidden">
				{loading ? (
					<div className="flex-1 flex items-center justify-center text-slate-400 text-xs gap-2 font-mono">
						<Loader2 className="w-4 h-4 animate-spin text-brand-400" />
						<span>Loading rule workspace...</span>
					</div>
				) : (
					<>
						{stepId === 'step-builder' && (
							<RuleStudioWorkspace
								ruleCode={ruleCode}
								setRuleCode={setRuleCode}
								ruleName={ruleName}
								setRuleName={setRuleName}
								status={status}
								setStatus={setStatus}
								action={action}
								setAction={setAction}
								description={description}
								setDescription={setDescription}
								changeSummary={changeSummary}
								setChangeSummary={setChangeSummary}
								conditionGroup={conditionGroup}
								setConditionGroup={setConditionGroup}
								saveSuccessNotice={saveSuccessNotice}
								availableFields={availableFields}
								isSchemaLocked={isSchemaLocked}
								isNew={isNew && !currentRule}
								errorMessage={errorMessage}
							/>
						)}

						{stepId === 'step-dryrun' && (
							<RuleDryRunWorkspace
								ruleCode={ruleCode}
								ruleName={ruleName}
								ruleAction={action}
								conditionGroup={conditionGroup}
								currentRule={currentRule}
								errorMessage={errorMessage}
							/>
						)}
					</>
				)}
			</div>

			{/* Version History Modal */}
			<RuleVersionHistoryModal
				rule={currentRule}
				isOpen={isVersionModalOpen}
				onClose={() => setIsVersionModalOpen(false)}
				onRestoreVersion={handleRestoreVersion}
			/>
		</div>
	);
};
