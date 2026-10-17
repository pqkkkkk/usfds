import { useState } from 'react';
import { WorkspaceStepper } from '../layout/WorkspaceStepper';
import type { PipelineStep } from '../layout/WorkspaceStepper';
import { PageHeader } from '../layout/PageHeader';
import { Terminal } from 'lucide-react';

const DETECTION_STEPS: PipelineStep[] = [
  { id: 'job-wizard', stepNumber: 1, label: 'Detection Job Wizard', description: 'Batch inference config', state: 'active' },
  { id: 'job-results', stepNumber: 2, label: 'Result Explorer & Case Dispatch', description: 'Score breakdown & Alerts', state: 'locked' }
];

export const DetectionJobModule = () => {
  const [currentStep, setCurrentStep] = useState('job-wizard');

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      <WorkspaceStepper
        steps={DETECTION_STEPS}
        currentStepId={currentStep}
        onSelectStep={setCurrentStep}
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <PageHeader
          title="Detection & Inference"
          subtitle="Chạy tác vụ chấm điểm gian lận theo lô (Batch Scoring), đối chiếu kết hợp ML & Rules"
          badge="Module"
          badgeColor="blue"
          breadcrumbs={[
            { label: 'Detection' },
            { label: currentStep === 'job-wizard' ? 'Job Wizard' : 'Results & Dispatch' }
          ]}
        />
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
            <Terminal className="w-8 h-8 text-brand-400 mx-auto" />
            <h3 className="text-sm font-semibold text-slate-100">Inference Job Pipeline</h3>
            <p className="text-xs text-slate-400">
              Quy trình thiết lập job chấm điểm gian lận và điều hướng xử lý các trường hợp nghi vấn (Case Dispatch).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
