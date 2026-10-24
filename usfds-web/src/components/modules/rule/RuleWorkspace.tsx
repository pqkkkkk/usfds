import React, { useState, useEffect } from 'react';
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
  createStitchSampleRuleGroup,
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
  const { currentProjectId, refetchProjects } = useProject();
  const effectiveProjectId = currentProjectId || FALLBACK_PROJECT_ID;

  const isNew = !ruleId || ruleId === 'new';

  const [currentRule, setCurrentRule] = useState<RuleResponse | null>(null);
  const [ruleCode, setRuleCode] = useState<string>('R-022');
  const [ruleName, setRuleName] = useState<string>(
    'High amount on new device with sudden velocity'
  );
  const [status, setStatus] = useState<RuleStatus>('ACTIVE');
  const [action, setAction] = useState<RuleAction>('REVIEW');
  const [description, setDescription] = useState<string>(
    'Flags purchases exceeding $2,000 on newly recognized client hardware or sudden frequency bursts.'
  );
  const [changeSummary, setChangeSummary] = useState<string>(
    'Cập nhật tham số điều kiện logic'
  );
  const [conditionGroup, setConditionGroup] = useState<RuleGroup>(
    createStitchSampleRuleGroup()
  );

  const [loading, setLoading] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccessNotice, setSaveSuccessNotice] = useState<boolean>(false);

  // Modal version history
  const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);

  useEffect(() => {
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
          }
        }
        setLoading(false);
      });
    } else {
      // New rule template
      setRuleCode('R-NEW');
      setRuleName('Quy tắc nghiệp vụ mới');
      setStatus('DRAFT');
      setAction('REVIEW');
      setDescription('Mô tả điều kiện phát hiện gian lận mới.');
      setConditionGroup(createStitchSampleRuleGroup());
    }
  }, [ruleId, isNew]);

  const handleSave = async (targetStatus?: RuleStatus) => {
    setIsSaving(true);
    try {
      const compiledJsonLogic = groupToJsonLogic(conditionGroup);
      const chosenStatus = targetStatus || status;

      if (!isNew && ruleId) {
        // Update existing rule
        const res = await ruleApi.updateRule(ruleId, {
          name: ruleName,
          description,
          condition: compiledJsonLogic,
          action,
          change_summary: changeSummary,
        });
        if (res.success && res.data) {
          setCurrentRule(res.data);
          setStatus(chosenStatus);
          setSaveSuccessNotice(true);
          setTimeout(() => setSaveSuccessNotice(false), 3000);
          return res.data;
        }
      } else {
        // Create new rule
        const res = await ruleApi.createRule({
          project_id: effectiveProjectId,
          rule_code: ruleCode,
          name: ruleName,
          description,
          condition: compiledJsonLogic,
          action,
          status: chosenStatus,
          change_summary: changeSummary,
        });
        if (res.success && res.data) {
          setCurrentRule(res.data);
          setSaveSuccessNotice(true);
          refetchProjects();
          setTimeout(() => {
            navigate(`/rules/${res.data.rule_id}/${stepId}`);
          }, 600);
          return res.data;
        }
      }
    } finally {
      setIsSaving(false);
    }
    return null;
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
        return;
      }
    }
    const targetRuleId = currentRule?.rule_id || ruleId || 'new';
    navigate(`/rules/${targetRuleId}/step-dryrun`);
  };

  const handleRestoreVersion = (version: RuleVersionResponse) => {
    setAction(version.action);
    setConditionGroup(jsonLogicToGroup(version.condition));
    if (version.change_summary) {
      setChangeSummary(`Khôi phục từ version v${version.version_number}`);
    }
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
      state: stepId === 'step-dryrun' ? 'active' : 'locked',
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
                  onClick={() => handleSave('DRAFT')}
                  className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-slate-800 text-slate-300 text-xs font-medium transition flex items-center gap-1.5 cursor-pointer"
                >
                  <Save className="w-3.5 h-3.5 text-slate-400" />
                  <span>Save Draft</span>
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
                disabled={isSaving}
                onClick={() => handleSave('ACTIVE')}
                className="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2 cursor-pointer"
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
              />
            )}

            {stepId === 'step-dryrun' && (
              <RuleDryRunWorkspace
                ruleCode={ruleCode}
                ruleName={ruleName}
                ruleAction={action}
                conditionGroup={conditionGroup}
                currentRule={currentRule}
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
