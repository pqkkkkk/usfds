import { useState } from 'react';
import { WorkspaceStepper } from '../layout/WorkspaceStepper';
import type { PipelineStep } from '../layout/WorkspaceStepper';
import { PageHeader } from '../layout/PageHeader';
import { ShieldCheck } from 'lucide-react';

const RULE_STEPS: PipelineStep[] = [
  { id: 'rule-studio', stepNumber: 1, label: 'Rule Studio Builder', description: 'DSL & Visual Rules', state: 'active' },
  { id: 'rule-backtest', stepNumber: 2, label: 'Rule Backtest Matrix', description: 'Historical Evaluation', state: 'locked' },
  { id: 'ai-recommend', stepNumber: 3, label: 'AI Rule Mining', description: 'Decision Tree extraction', state: 'locked' }
];

export const RuleEngineModule = () => {
  const [currentStep, setCurrentStep] = useState('rule-studio');

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      <WorkspaceStepper
        steps={RULE_STEPS}
        currentStepId={currentStep}
        onSelectStep={setCurrentStep}
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <PageHeader
          title="Rule Engine & Studio"
          subtitle="Định nghĩa luật nghiệp vụ gian lận, thực hiện backtest trên dữ liệu lịch sử và tiếp nhận gợi ý AI"
          badge="Module"
          badgeColor="green"
          breadcrumbs={[
            { label: 'Rule Engine' },
            { label: currentStep === 'rule-studio' ? 'Studio' : 'Backtest' }
          ]}
        />
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
            <ShieldCheck className="w-8 h-8 text-emerald-400 mx-auto" />
            <h3 className="text-sm font-semibold text-slate-100">Rule Engine Studio Flow</h3>
            <p className="text-xs text-slate-400">
              Quy trình định nghĩa luật, chạy thử nghiệm backtest ma trận và triển khai luật an toàn.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
