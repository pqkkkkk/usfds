import { useState } from 'react';
import { WorkspaceStepper } from '../layout/WorkspaceStepper';
import type { PipelineStep } from '../layout/WorkspaceStepper';
import { DatasetHubView } from '../DatasetHubView';
import { DatasetLineageExplorer } from './DatasetLineageExplorer';
import { PageHeader } from '../layout/PageHeader';
import type { DatasetEntity, LineageRawNode } from '../../types/navigation';
import {
  FileSpreadsheet,
  Sliders,
  BarChart3,
  ArrowLeft,
  ArrowRight,
  CheckCircle2
} from 'lucide-react';

interface DataManagementModuleProps {
  onOpenInspector: (item: any) => void;
}

const DATA_MANAGEMENT_STEPS: PipelineStep[] = [
  {
    id: 'step-profiling',
    stepNumber: 1,
    label: 'RAW Data & Profiling',
    description: 'Inspect distributions & quality',
    state: 'completed'
  },
  {
    id: 'step-mapping',
    stepNumber: 2,
    label: 'Schema Mapping & Validation',
    description: '5 canonical core fields',
    state: 'active'
  },
  {
    id: 'step-feature-eng',
    stepNumber: 3,
    label: 'Feature Eng. & Auto-Normalize',
    description: 'Velocity sliders & transforms',
    state: 'locked'
  }
];

export const DataManagementModule = ({
  onOpenInspector,
}: DataManagementModuleProps) => {
  const [viewMode, setViewMode] = useState<'hub' | 'lineage' | 'pipeline'>('hub');
  const [selectedDataset, setSelectedDataset] = useState<DatasetEntity | null>(null);
  const [activeArtifact, setActiveArtifact] = useState<LineageRawNode | null>(null);
  const [currentStep, setCurrentStep] = useState<string>('step-mapping');

  // Khi click vào một Dataset ở Hub -> Mở Lineage Explorer của Dataset đó
  const handleSelectDataset = (dataset: DatasetEntity) => {
    setSelectedDataset(dataset);
    setViewMode('lineage');
  };

  // Từ Lineage Explorer -> Mở Stepper cho một artifact cụ thể
  const handleSelectArtifactForPipeline = (artifact: LineageRawNode, stepHint: string) => {
    setActiveArtifact(artifact);
    setCurrentStep(stepHint);
    setViewMode('pipeline');
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      {/* 1. View: Dataset Hub (Liệt kê Datasets) */}
      {viewMode === 'hub' && (
        <DatasetHubView
          onSelectDataset={handleSelectDataset}
          onOpenInspector={onOpenInspector}
        />
      )}

      {/* 2. View: Dataset Lineage Explorer (Cả Tree View và Canvas View từ sample_lineage.json) */}
      {viewMode === 'lineage' && (
        <DatasetLineageExplorer
          datasetId={selectedDataset?.id}
          datasetName={selectedDataset?.name}
          onBackToDatasets={() => setViewMode('hub')}
          onSelectArtifactForPipeline={handleSelectArtifactForPipeline}
        />
      )}

      {/* 3. View: Pipeline Stepper (Xử lý từng bước trong vòng đời chuẩn hóa dữ liệu) */}
      {viewMode === 'pipeline' && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <WorkspaceStepper
            steps={DATA_MANAGEMENT_STEPS}
            currentStepId={currentStep}
            onSelectStep={setCurrentStep}
            branchName="main"
            forkedFromArtifactId={activeArtifact?.id}
          />

          {/* Module Step Sub-Viewport */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Step 1: Profiling */}
            {currentStep === 'step-profiling' && (
              <div className="flex-1 flex flex-col overflow-hidden">
                <PageHeader
                  title="Raw Data & Profiling"
                  subtitle="Xem phân phối dữ liệu thô, tỷ lệ khuyết thiếu và thông số thống kê cơ bản"
                  badge="Step 1 / 3"
                  badgeColor="blue"
                  breadcrumbs={[
                    { label: 'Data Management' },
                    { label: selectedDataset?.name || 'Dataset' },
                    { label: 'RAW Profiling' }
                  ]}
                  actions={
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setViewMode('lineage')}
                        className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs text-slate-300 transition flex items-center gap-1.5"
                      >
                        <ArrowLeft className="w-3.5 h-3.5" />
                        <span>Back to Lineage</span>
                      </button>
                      <button
                        onClick={() => setCurrentStep('step-mapping')}
                        className="px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-1.5"
                      >
                        <span>Next: Schema Mapping</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  }
                />
                <div className="flex-1 p-6 overflow-y-auto">
                  <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
                    <BarChart3 className="w-8 h-8 text-brand-400 mx-auto" />
                    <h3 className="text-sm font-semibold text-slate-100">Dataset Profiling Matrix</h3>
                    <p className="text-xs text-slate-400">
                      Tập dữ liệu thô đã được ingest thành công và tính toán thống kê nulls/cardinality.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Schema Mapping & Validation */}
            {currentStep === 'step-mapping' && (
              <div className="flex-1 flex flex-col overflow-hidden">
                <PageHeader
                  title="Schema Mapping & Validation"
                  subtitle="Ánh xạ các cột dữ liệu gốc sang 5 trường chuẩn bắt buộc (event_id, event_timestamp, user_id, amount, label)"
                  badge="Step 2 / 3"
                  badgeColor="blue"
                  breadcrumbs={[
                    { label: 'Data Management' },
                    { label: selectedDataset?.name || 'Dataset' },
                    { label: 'Schema Mapping' }
                  ]}
                  actions={
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setViewMode('lineage')}
                        className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs text-slate-300 transition flex items-center gap-1.5"
                      >
                        <ArrowLeft className="w-3.5 h-3.5" />
                        <span>Back to Lineage</span>
                      </button>
                      <button
                        onClick={() => setCurrentStep('step-feature-eng')}
                        className="px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-1.5"
                      >
                        <span>Next: Feature Engineering</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  }
                />
                <div className="flex-1 p-6 overflow-y-auto">
                  <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
                    <FileSpreadsheet className="w-8 h-8 text-emerald-400 mx-auto" />
                    <h3 className="text-sm font-semibold text-slate-100">Canonical Schema Mapping</h3>
                    <p className="text-xs text-slate-400">
                      Các trường canonical chuẩn hóa đã sẵn sàng để đối chiếu với tập dữ liệu giao dịch.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Feature Engineering & Auto Normalization */}
            {currentStep === 'step-feature-eng' && (
              <div className="flex-1 flex flex-col overflow-hidden">
                <PageHeader
                  title="Feature Engineering & Auto-Normalization"
                  subtitle="Cấu hình cửa sổ thời gian trượt (Sliding Velocity Windows) và bộ chuẩn hóa tự động"
                  badge="Step 3 / 3"
                  badgeColor="purple"
                  breadcrumbs={[
                    { label: 'Data Management' },
                    { label: selectedDataset?.name || 'Dataset' },
                    { label: 'Feature Engineering' }
                  ]}
                  actions={
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCurrentStep('step-mapping')}
                        className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs text-slate-300 transition flex items-center gap-1.5"
                      >
                        <ArrowLeft className="w-3.5 h-3.5" />
                        <span>Previous Step</span>
                      </button>
                      <button
                        onClick={() => setViewMode('lineage')}
                        className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold shadow-glow-green transition flex items-center gap-1.5"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Save & View Lineage</span>
                      </button>
                    </div>
                  }
                />
                <div className="flex-1 p-6 overflow-y-auto">
                  <div className="p-8 rounded-xl bg-dark-900 border border-dark-700/80 text-center space-y-3 max-w-xl mx-auto mt-8">
                    <Sliders className="w-8 h-8 text-purple-400 mx-auto" />
                    <h3 className="text-sm font-semibold text-slate-100">Velocity Feature Sliders</h3>
                    <p className="text-xs text-slate-400">
                      Thiết lập các đặc trưng vận tốc giao dịch (1h, 24h, 7d) và chuẩn hóa tự động.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
