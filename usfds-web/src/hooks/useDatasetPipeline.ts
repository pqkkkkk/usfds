import { useState, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { datasetApi } from '../api/datasetApi';
import { DATASET_DETAIL_QUERY_KEY } from './useDatasetDetail';
import { DATASETS_QUERY_KEY } from './useDatasetList';
import type {
  DatasetDetailResponse,
  DatasetArtifactResponse,
  DataMappingConfig,
  FeatureEngineeringConfig,
  ExportDatasetRequest,
} from '../types/dataset';
import type { PipelineStep } from '../components/layout/WorkspaceStepper';

export type PipelineStepId = 'step-profiling' | 'step-mapping' | 'step-validation' | 'step-feature-eng';

export function useDatasetPipeline(datasetId: string | undefined, currentStepId: string = 'step-profiling') {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const artifactIdParam = searchParams.get('artifactId');

  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  // Fetch dataset detail
  const {
    data: datasetDetail = null,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery<DatasetDetailResponse | null>({
    queryKey: [...DATASET_DETAIL_QUERY_KEY, datasetId],
    queryFn: async () => {
      if (!datasetId) return null;
      const res = await datasetApi.getDatasetDetail(datasetId);
      if (!res.success) {
        throw new Error(res.error || 'Failed to fetch dataset');
      }
      return res.data;
    },
    enabled: Boolean(datasetId),
  });

  // Track the active mapped and FE artifacts created in this pipeline session
  const [sessionMappedArtifact, setSessionMappedArtifact] = useState<DatasetArtifactResponse | null>(null);
  const [sessionFeArtifact, setSessionFeArtifact] = useState<DatasetArtifactResponse | null>(null);

  // 1. Resolve source RAW artifact
  const sourceRawArtifact = useMemo<DatasetArtifactResponse | null>(() => {
    if (!datasetDetail || !datasetDetail.artifacts) return null;

    if (artifactIdParam) {
      const target = datasetDetail.artifacts.find(a => a.artifact_id === artifactIdParam);
      if (target?.pipeline_stage === 'RAW') {
        return target;
      }
      if (target?.pipeline_stage === 'MAPPED' && target.parent_artifact_id) {
        return datasetDetail.artifacts.find(a => a.artifact_id === target.parent_artifact_id) || null;
      }
      if ((target?.pipeline_stage === 'PRE_PROCESSED' || target?.pipeline_stage === 'FEATURE_ENGINEERED') && target.parent_artifact_id) {
        const parentMapped = datasetDetail.artifacts.find(a => a.artifact_id === target.parent_artifact_id);
        if (parentMapped?.parent_artifact_id) {
          return datasetDetail.artifacts.find(a => a.artifact_id === parentMapped.parent_artifact_id) || null;
        }
      }
    }

    // Default to first RAW artifact in dataset
    return datasetDetail.artifacts.find(a => a.pipeline_stage === 'RAW') || null;
  }, [datasetDetail, artifactIdParam]);

  // 2. Resolve active MAPPED artifact
  // CRITICAL LOGIC: If starting from RAW (artifactIdParam is RAW), this is a NEW mapping branch!
  // It must NOT automatically reuse an existing MAPPED artifact unless user created one in this session
  // or explicitly selected a MAPPED artifact in lineage.
  const activeMappedArtifact = useMemo<DatasetArtifactResponse | null>(() => {
    if (sessionMappedArtifact) {
      return sessionMappedArtifact;
    }

    if (!datasetDetail || !datasetDetail.artifacts) return null;

    if (artifactIdParam) {
      const target = datasetDetail.artifacts.find(a => a.artifact_id === artifactIdParam);
      if (target?.pipeline_stage === 'MAPPED') {
        return target;
      }
      if ((target?.pipeline_stage === 'PRE_PROCESSED' || target?.pipeline_stage === 'FEATURE_ENGINEERED') && target.parent_artifact_id) {
        return datasetDetail.artifacts.find(a => a.artifact_id === target.parent_artifact_id) || null;
      }
      if (target?.pipeline_stage === 'RAW') {
        // Explicitly started from RAW -> new branch, no mapped artifact yet!
        return null;
      }
    }

    return null;
  }, [sessionMappedArtifact, datasetDetail, artifactIdParam]);

  // 3. Resolve active FEATURE_ENGINEERED artifact
  const activeFeArtifact = useMemo<DatasetArtifactResponse | null>(() => {
    if (sessionFeArtifact) {
      return sessionFeArtifact;
    }

    if (!datasetDetail || !datasetDetail.artifacts) return null;

    if (artifactIdParam) {
      const target = datasetDetail.artifacts.find(a => a.artifact_id === artifactIdParam);
      if (target?.pipeline_stage === 'PRE_PROCESSED' || target?.pipeline_stage === 'FEATURE_ENGINEERED') {
        return target;
      }
    }

    if (activeMappedArtifact) {
      return datasetDetail.artifacts.find(
        a => a.parent_artifact_id === activeMappedArtifact.artifact_id &&
          (a.pipeline_stage === 'PRE_PROCESSED' || a.pipeline_stage === 'FEATURE_ENGINEERED')
      ) || null;
    }

    return null;
  }, [sessionFeArtifact, datasetDetail, artifactIdParam, activeMappedArtifact]);

  // Is this a brand new mapping branch from RAW?
  const isNewMappingBranch = useMemo(() => {
    if (sessionMappedArtifact) return false;
    if (!artifactIdParam) return true;
    const target = datasetDetail?.artifacts.find(a => a.artifact_id === artifactIdParam);
    return target?.pipeline_stage === 'RAW';
  }, [sessionMappedArtifact, artifactIdParam, datasetDetail]);

  // 4. Stepper Configuration (4 Steps)
  const pipelineSteps: PipelineStep[] = useMemo(() => {
    const isStep1Done = !!sourceRawArtifact;
    const isStep2Done = !!activeMappedArtifact;
    const isStep3Done = !!activeMappedArtifact;
    const isStep4Done = !!activeFeArtifact;

    return [
      {
        id: 'step-profiling',
        stepNumber: 1,
        label: 'Data Profiling',
        description: 'Inspect distributions & quality metrics',
        state: isStep1Done ? 'completed' : 'active',
      },
      {
        id: 'step-mapping',
        stepNumber: 2,
        label: 'Schema Mapping',
        description: 'Map raw fields to canonical schema',
        state: isStep2Done ? 'completed' : 'active',
      },
      {
        id: 'step-validation',
        stepNumber: 3,
        label: 'Validation Report',
        description: 'Quality score & constraint audit',
        state: isStep3Done ? (isStep4Done ? 'completed' : 'active') : 'locked',
      },
      {
        id: 'step-feature-eng',
        stepNumber: 4,
        label: 'Feature Engineering',
        description: 'Enrich features to optimize model performance',
        state: isStep2Done ? (isStep4Done ? 'completed' : 'active') : 'locked',
      },
    ];
  }, [sourceRawArtifact, activeMappedArtifact, activeFeArtifact]);

  const currentStep = useMemo(() => {
    return pipelineSteps.find(s => s.id === currentStepId) || pipelineSteps[0];
  }, [pipelineSteps, currentStepId]);

  // Navigation handlers
  const handleStepSelect = useCallback((targetStepId: string) => {
    // Check if step is locked
    const targetStep = pipelineSteps.find(s => s.id === targetStepId);
    if (targetStep?.state === 'locked') {
      alert('Bước này chưa sẵn sàng. Vui lòng hoàn thành bước Ánh xạ lược đồ (Schema Mapping) trước.');
      return;
    }

    // Determine which artifactId to keep in URL
    let nextArtifactId = artifactIdParam;
    if (targetStepId === 'step-profiling' && sourceRawArtifact) {
      nextArtifactId = sourceRawArtifact.artifact_id;
    } else if ((targetStepId === 'step-validation' || targetStepId === 'step-feature-eng') && activeMappedArtifact) {
      nextArtifactId = activeMappedArtifact.artifact_id;
    } else if (targetStepId === 'step-feature-eng' && activeFeArtifact) {
      nextArtifactId = activeFeArtifact.artifact_id;
    }

    const query = nextArtifactId ? `?artifactId=${nextArtifactId}` : '';
    navigate(`/datasets/${datasetId}/workspace/${targetStepId}${query}`);
  }, [pipelineSteps, artifactIdParam, sourceRawArtifact, activeMappedArtifact, activeFeArtifact, datasetId, navigate]);

  // Proceed logic
  const canProceed = useMemo(() => {
    if (currentStepId === 'step-profiling') return true;
    if (currentStepId === 'step-mapping') return !!activeMappedArtifact;
    if (currentStepId === 'step-validation') return true;
    if (currentStepId === 'step-feature-eng') return true;
    return true;
  }, [currentStepId, activeMappedArtifact]);

  const proceedButtonText = useMemo(() => {
    switch (currentStepId) {
      case 'step-profiling':
        return 'Proceed to Schema Mapping';
      case 'step-mapping':
        return activeMappedArtifact ? 'Proceed to Validation Report' : 'Save Mapping to Proceed';
      case 'step-validation':
        return 'Proceed to Feature Engineering';
      case 'step-feature-eng':
        return 'Proceed to Model Training';
      default:
        return 'Proceed';
    }
  }, [currentStepId, activeMappedArtifact]);

  const backButtonText = useMemo(() => {
    switch (currentStepId) {
      case 'step-profiling':
        return 'Back to Lineage';
      case 'step-mapping':
        return 'Back to Profiling';
      case 'step-validation':
        return 'Back to Schema Mapping';
      case 'step-feature-eng':
        return 'Back to Validation Report';
      default:
        return 'Back';
    }
  }, [currentStepId]);

  const handleProceed = useCallback(() => {
    if (currentStepId === 'step-profiling') {
      handleStepSelect('step-mapping');
    } else if (currentStepId === 'step-mapping') {
      if (!activeMappedArtifact) {
        alert('Vui lòng cấu hình và nhấn "Lưu ánh xạ lược đồ" để tạo Mapped Artifact trước khi xem Validation Report.');
        return;
      }
      handleStepSelect('step-validation');
    } else if (currentStepId === 'step-validation') {
      handleStepSelect('step-feature-eng');
    } else if (currentStepId === 'step-feature-eng') {
      navigate('/models');
    }
  }, [currentStepId, activeMappedArtifact, handleStepSelect, navigate]);

  const handleBack = useCallback(() => {
    if (currentStepId === 'step-profiling') {
      navigate(`/datasets/${datasetId}`);
    } else if (currentStepId === 'step-mapping') {
      handleStepSelect('step-profiling');
    } else if (currentStepId === 'step-validation') {
      handleStepSelect('step-mapping');
    } else if (currentStepId === 'step-feature-eng') {
      handleStepSelect('step-validation');
    }
  }, [currentStepId, datasetId, navigate, handleStepSelect]);

  // Callback when a new Schema Mapping artifact is created
  const handleMappingSuccess = useCallback((newMappedArtifact: DatasetArtifactResponse) => {
    setSessionMappedArtifact(newMappedArtifact);
    setSessionFeArtifact(null); // Reset downstream FE if mapping changed

    // Update React Query cache
    if (datasetId) {
      queryClient.setQueryData<DatasetDetailResponse | null>(
        [...DATASET_DETAIL_QUERY_KEY, datasetId],
        (old) => {
          if (!old) return old;
          return {
            ...old,
            artifacts: [
              ...old.artifacts.filter(a => a.artifact_id !== newMappedArtifact.artifact_id),
              newMappedArtifact,
            ],
          };
        }
      );
      queryClient.invalidateQueries({ queryKey: DATASETS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: [...DATASET_DETAIL_QUERY_KEY, datasetId] });
    }

    // Update URL to point to newly created artifact branch
    setSearchParams({ artifactId: newMappedArtifact.artifact_id });
  }, [datasetId, queryClient, setSearchParams]);

  // Callback when a Feature Engineering artifact is created
  const handleFESuccess = useCallback((newFeArtifact: DatasetArtifactResponse) => {
    setSessionFeArtifact(newFeArtifact);

    if (datasetId) {
      queryClient.setQueryData<DatasetDetailResponse | null>(
        [...DATASET_DETAIL_QUERY_KEY, datasetId],
        (old) => {
          if (!old) return old;
          return {
            ...old,
            artifacts: [
              ...old.artifacts.filter(a => a.artifact_id !== newFeArtifact.artifact_id),
              newFeArtifact,
            ],
          };
        }
      );
      queryClient.invalidateQueries({ queryKey: DATASETS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: [...DATASET_DETAIL_QUERY_KEY, datasetId] });
    }

    setSearchParams({ artifactId: newFeArtifact.artifact_id });
  }, [datasetId, queryClient, setSearchParams]);

  // 5. Schema Mapping handler
  const mapSchemaMutation = useMutation({
    mutationFn: async (payload: DataMappingConfig) => {
      if (!datasetId) throw new Error('Dataset ID is missing');
      const res = await datasetApi.mapSchema(datasetId, payload);
      if (!res.success || !res.data) {
        throw new Error(res.error || 'Lưu ánh xạ lược đồ thất bại');
      }
      return res.data;
    },
    onSuccess: (newMappedArtifact) => {
      handleMappingSuccess(newMappedArtifact);
    },
  });

  // 6. Feature Engineering handler
  const feMutation = useMutation({
    mutationFn: async (payload: FeatureEngineeringConfig) => {
      if (!datasetId) throw new Error('Dataset ID is missing');
      const res = await datasetApi.executeFeatureEngineering(datasetId, payload);
      if (!res.success || !res.data) {
        throw new Error(res.error || 'Thực thi Feature Engineering thất bại');
      }
      return res.data;
    },
    onSuccess: (newFeArtifact) => {
      handleFESuccess(newFeArtifact);
    },
  });

  // 7. Export Dataset handler
  const exportMutation = useMutation({
    mutationFn: async ({
      artifactId,
      payload,
      fallbackFilename,
    }: {
      artifactId: string;
      payload: ExportDatasetRequest;
      fallbackFilename?: string;
    }) => {
      if (!datasetId) throw new Error('Dataset ID is missing');
      const res = await datasetApi.exportDataset(datasetId, artifactId, payload, fallbackFilename);
      if (!res.success) {
        throw new Error(res.error || 'Xuất dữ liệu thất bại');
      }
      return res;
    },
  });

  const datasetName = datasetDetail?.dataset.dataset_name || 'Dataset';
  const exportTargetArtifact = activeFeArtifact || activeMappedArtifact || sourceRawArtifact;

  return {
    datasetDetail,
    datasetName,
    isLoading: isLoading || isFetching,
    error: error ? (error as Error).message : null,
    currentStep,
    currentStepId,
    pipelineSteps,
    artifactIdParam,
    sourceRawArtifact,
    activeMappedArtifact,
    activeFeArtifact,
    isNewMappingBranch,
    canProceed,
    proceedButtonText,
    backButtonText,
    handleStepSelect,
    handleProceed,
    handleBack,
    handleMappingSuccess,
    handleFESuccess,
    isExportModalOpen,
    setIsExportModalOpen,
    exportTargetArtifact,
    refetch,

    // Schema Mapping Action & Status
    saveSchemaMapping: mapSchemaMutation.mutateAsync,
    isSavingMapping: mapSchemaMutation.isPending,
    mappingError: mapSchemaMutation.error ? (mapSchemaMutation.error as Error).message : null,

    // Feature Engineering Action & Status
    executeFeatureEngineering: feMutation.mutateAsync,
    isExecutingFE: feMutation.isPending,
    feError: feMutation.error ? (feMutation.error as Error).message : null,

    // Export Dataset Action & Status
    exportDataset: exportMutation.mutateAsync,
    isExporting: exportMutation.isPending,
    exportError: exportMutation.error ? (exportMutation.error as Error).message : null,
  };
}

export default useDatasetPipeline;
