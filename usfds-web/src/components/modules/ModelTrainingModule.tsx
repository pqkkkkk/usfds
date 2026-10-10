import { useState } from 'react';
import { WorkspaceStepper } from '../layout/WorkspaceStepper';
import type { PipelineStep } from '../layout/WorkspaceStepper';
import { PageHeader } from '../layout/PageHeader';
import { BrainCircuit } from 'lucide-react';

const MODEL_TRAINING_STEPS: PipelineStep[] = [
  { id: 'train-wizard', stepNumber: 1, label: 'Model Training Wizard', description: 'Algorithm & Hyperparams', state: 'active' },
  { id: 'train-eval', stepNumber: 2, label: 'Evaluation & Metrics', description: 'PR-AUC & Confusion Matrix', state: 'locked' },
  { id: 'model-deploy', stepNumber: 3, label: 'Deploy & Model Ledger', description: 'Shadow vs Active', state: 'locked' }
];

export const ModelTrainingModule = () => {
  const [currentStep, setCurrentStep] = useState('train-wizard');

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      <WorkspaceStepper
        steps={MODEL_TRAINING_STEPS}
        currentStepId={currentStep}
        onSelectStep={setCurrentStep}
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <PageHeader
          title="Model Training & Evaluation"
          subtitle="Huấn luyện mô hình học máy (LightGBM, XGBoost, CatBoost), tinh chỉnh ngưỡng và đánh giá ma trận"
          badge="Module"
          badgeColor="blue"
          breadcrumbs={[
            { label: 'Model Training' },
            { label: currentStep === 'train-wizard' ? 'Wizard' : 'Evaluation' }
          ]}
        />
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
            <BrainCircuit className="w-8 h-8 text-brand-400 mx-auto" />
            <h3 className="text-sm font-semibold text-slate-100">Model Training Pipeline</h3>
            <p className="text-xs text-slate-400">
              Quy trình đào tạo mô hình được cấu trúc thành các bước tuần tự (Wizard ➔ Đánh giá PR/ROC ➔ Triển khai).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
