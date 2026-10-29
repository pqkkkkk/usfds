import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { PageHeader } from '../../layout/PageHeader';
import { WorkspaceStepper } from '../../layout/WorkspaceStepper';
import { DataProfilingWorkspace } from './DataProfilingWorkspace';
import { SchemaMappingWorkspace } from './SchemaMappingWorkspace';
import { DataValidationWorkspace } from './DataValidationWorkspace';
import { FeatureEngineeringWorkspace } from './FeatureEngineeringWorkspace';
import { useDatasetPipeline } from '../../../hooks/useDatasetPipeline';
import type { DataMappingConfig, FeatureEngineeringConfig } from '../../../types/dataset';
import {
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  Loader2
} from 'lucide-react';

export const DataPipelineWorkspace = () => {
  const { datasetId, stepId = 'step-profiling' } = useParams<{ datasetId: string; stepId: string }>();
  const navigate = useNavigate();

  const [mappingConfig, setMappingConfig] = useState<DataMappingConfig | null>(null);
  const [isMappingValid, setIsMappingValid] = useState<boolean>(false);
  const [feConfig, setFeConfig] = useState<FeatureEngineeringConfig | null>(null);

  const handleMappingConfigChange = useCallback((cfg: DataMappingConfig, valid: boolean) => {
    setMappingConfig(cfg);
    setIsMappingValid(valid);
  }, []);

  const {
    datasetDetail,
    datasetName,
    isLoading,
    currentStep,
    pipelineSteps,
    sourceRawArtifact,
    activeMappedArtifact,
    activeFeArtifact,
    isNewMappingBranch,
    backButtonText,
    handleStepSelect,
    handleBack,
    saveSchemaMapping,
    isSavingMapping,
    mappingError,
    executeFeatureEngineering,
    isExecutingFE,
    feError,
  } = useDatasetPipeline(datasetId, stepId);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
      {/* Header */}
      <PageHeader
        title={currentStep.label}
        subtitle={currentStep.description}
        badge={`Step ${currentStep.stepNumber} / 4`}
        badgeColor={
          currentStep.stepNumber === 1
            ? 'blue'
            : currentStep.stepNumber === 2
              ? 'green'
              : currentStep.stepNumber === 3
                ? 'blue'
                : 'purple'
        }
        breadcrumbs={[
          { label: 'Data Management', tab: 'data-hub' },
          { label: datasetName, tab: 'lineage' },
          { label: currentStep.label }
        ]}
        onNavigate={(tab) => {
          if (tab === 'data-hub') navigate('/datasets');
          if (tab === 'lineage') navigate(`/datasets/${datasetId}`);
        }}
        actions={
          <div className="flex items-center gap-2.5">
            {/* Back Button */}
            <button
              onClick={handleBack}
              className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs text-slate-300 transition flex items-center gap-1.5"
            >
              <ArrowLeft className="w-3.5 h-3.5 text-slate-400" />
              <span>{backButtonText}</span>
            </button>

            {/* Step 1: Profiling -> Proceed to Mapping */}
            {stepId === 'step-profiling' && (
              <button
                onClick={() => handleStepSelect('step-mapping')}
                className="px-4 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-1.5"
              >
                <span>Proceed to Schema Mapping</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            {/* Step 2: Schema Mapping -> Validate Data action */}
            {stepId === 'step-mapping' && (
              <button
                onClick={async () => {
                  if (!mappingConfig || !isMappingValid || isSavingMapping) return;
                  try {
                    const res = await saveSchemaMapping(mappingConfig);
                    if (res?.artifact_id) {
                      navigate(`/datasets/${datasetId}/pipeline/step-validation?artifactId=${res.artifact_id}`);
                    }
                  } catch (e) {
                    console.error('Validation failed:', e);
                  }
                }}
                disabled={!isMappingValid || isSavingMapping}
                className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-glow-blue ${
                  !isMappingValid || isSavingMapping
                    ? 'bg-dark-700 text-slate-500 cursor-not-allowed border border-dark-600'
                    : 'bg-brand-500 hover:bg-brand-600 text-white'
                }`}
                title={!isMappingValid ? 'Please map all required fields (User ID, Timestamp, Amount, Label)' : 'Validate schema and generate validation report'}
              >
                {isSavingMapping ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Validating Data...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>Validate Data</span>
                  </>
                )}
              </button>
            )}

            {/* Step 3: Validation Report -> Proceed to Feature Engineering */}
            {stepId === 'step-validation' && (
              <button
                onClick={() => handleStepSelect('step-feature-eng')}
                className="px-4 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-1.5"
              >
                <span>Proceed to Feature Engineering</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            {/* Step 4: Feature Engineering -> Execute & Proceed to Training */}
            {stepId === 'step-feature-eng' && (
              <div className="flex items-center gap-2">
                {activeFeArtifact && (
                  <button
                    onClick={async () => {
                      if (!feConfig || isExecutingFE) return;
                      try {
                        await executeFeatureEngineering(feConfig);
                      } catch (e) {
                        console.error('Re-run feature engineering failed:', e);
                      }
                    }}
                    disabled={isExecutingFE}
                    className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs text-brand-300 transition flex items-center gap-1.5"
                  >
                    {isExecutingFE ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="w-3.5 h-3.5 text-brand-400" />
                    )}
                    <span>Re-run Features</span>
                  </button>
                )}

                <button
                  onClick={async () => {
                    if (activeFeArtifact) {
                      navigate('/models');
                    } else {
                      if (!feConfig || isExecutingFE) return;
                      try {
                        await executeFeatureEngineering(feConfig);
                      } catch (e) {
                        console.error('Feature engineering failed:', e);
                      }
                    }
                  }}
                  disabled={!activeFeArtifact && (!feConfig || isExecutingFE)}
                  className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
                    !activeFeArtifact && (!feConfig || isExecutingFE)
                      ? 'bg-dark-700 text-slate-500 cursor-not-allowed border border-dark-600'
                      : 'bg-brand-500 hover:bg-brand-600 text-white shadow-glow-blue'
                  }`}
                >
                  {isExecutingFE ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Running Feature Engineering...</span>
                    </>
                  ) : activeFeArtifact ? (
                    <>
                      <span>Proceed to Model Training</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Run Feature Engineering</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        }
      />

      {/* Stepper Navigation */}
      <WorkspaceStepper
        steps={pipelineSteps}
        currentStepId={stepId}
        onSelectStep={handleStepSelect}
        branchName={isNewMappingBranch ? 'new-schema-branch' : (activeMappedArtifact ? `branch-${activeMappedArtifact.artifact_id.slice(-6)}` : 'main')}
        forkedFromArtifactId={activeMappedArtifact?.artifact_id || sourceRawArtifact?.artifact_id}
      />

      {/* Workspace Body */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {isLoading && !datasetDetail ? (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-xs gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
            <span>Loading workspace data...</span>
          </div>
        ) : (
          <>
            {/* Step 1: RAW Data & Profiling */}
            {stepId === 'step-profiling' && (
              <DataProfilingWorkspace
                datasetName={datasetName}
                artifact={sourceRawArtifact}
              />
            )}

            {/* Step 2: Schema Mapping */}
            {stepId === 'step-mapping' && (
              <SchemaMappingWorkspace
                rawArtifact={sourceRawArtifact}
                mappedArtifact={activeMappedArtifact}
                onConfigChange={handleMappingConfigChange}
                saveError={mappingError}
              />
            )}

            {/* Step 3: Data Validation Report */}
            {stepId === 'step-validation' && (
              <DataValidationWorkspace
                datasetId={datasetId || ''}
                datasetName={datasetName}
                mappedArtifact={activeMappedArtifact}
              />
            )}

            {/* Step 4: Feature Engineering */}
            {stepId === 'step-feature-eng' && (
              <FeatureEngineeringWorkspace
                mappedArtifact={activeMappedArtifact}
                feArtifact={activeFeArtifact}
                onConfigChange={setFeConfig}
                executionError={feError}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default DataPipelineWorkspace;
