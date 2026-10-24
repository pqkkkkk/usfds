import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
	ArrowLeft,
	ArrowRight,
	BrainCircuit,
	CheckCircle2,
	Code2,
	Database,
	Loader2,
	Play,
	RotateCcw,
	ShieldAlert,
	Sliders,
} from 'lucide-react';
import { datasetApi } from '../../../api/datasetApi';
import { trainingApi } from '../../../api/trainingApi';
import { useProject } from '../../../hooks/useProjects';
import { WorkspaceStepper } from '../../layout/WorkspaceStepper';
import type { PipelineStep } from '../../layout/WorkspaceStepper';
import type { DatasetArtifactResponse, DatasetResponse } from '../../../types/dataset';
import type {
	HyperparameterPropertySchema,
	ModelResponse,
} from '../../../types/model';
import { ImportCustomModelModal } from './ImportCustomModelModal';

export const TrainingWizardView: React.FC = () => {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();
	const { currentProject } = useProject();
	const projectId = currentProject?.project_id;

	const initialModelId = searchParams.get('modelId') || '';
	const initialDatasetId = searchParams.get('datasetId') || '';
	const initialArtifactId = searchParams.get('artifactId') || '';

	const [currentStep, setCurrentStep] = useState<'step-data' | 'step-model' | 'step-review'>('step-data');

	// Data state
	const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
	const [artifactsByDataset, setArtifactsByDataset] = useState<Record<string, DatasetArtifactResponse[]>>({});
	const [models, setModels] = useState<ModelResponse[]>([]);
	const [isLoadingInit, setIsLoadingInit] = useState<boolean>(true);

	// Form selection state
	const [selectedDatasetId, setSelectedDatasetId] = useState<string>(initialDatasetId);
	const [selectedArtifactId, setSelectedArtifactId] = useState<string>(initialArtifactId);
	const [selectedModelId, setSelectedModelId] = useState<string>(initialModelId);
	const [hyperparams, setHyperparams] = useState<Record<string, any>>({});
	const [jsonEditMode, setJsonEditMode] = useState<boolean>(false);
	const [rawHyperparamsJson, setRawHyperparamsJson] = useState<string>('{}');
	const [runName, setRunName] = useState<string>('');

	// Submission state
	const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);
	const [isImportModalOpen, setIsImportModalOpen] = useState<boolean>(false);

	const loadInitialCatalog = useCallback(async () => {
		setIsLoadingInit(true);
		try {
			const [dsRes, modelsRes] = await Promise.all([
				datasetApi.listDatasets(projectId),
				trainingApi.listModels(projectId),
			]);
			const dsList = dsRes.success && dsRes.data ? dsRes.data : [];
			const modelList = modelsRes.success && modelsRes.data ? modelsRes.data : [];
			setDatasets(dsList);
			setModels(modelList);

			// Fetch artifacts for each dataset
			const details = await Promise.all(
				dsList.map(async (ds) => {
					const detailRes = await datasetApi.getDatasetDetail(ds.dataset_id);
					return [
						ds.dataset_id,
						detailRes.success && detailRes.data ? detailRes.data.artifacts : [],
					] as const;
				})
			);
			const artMap: Record<string, DatasetArtifactResponse[]> = {};
			for (const [dId, arts] of details) {
				artMap[dId] = arts;
			}
			setArtifactsByDataset(artMap);

			// Auto-select dataset & eligible artifact if not pre-filled
			let targetDsId = selectedDatasetId;
			let targetArtId = selectedArtifactId;

			if (targetArtId && !targetDsId) {
				for (const [dId, arts] of Object.entries(artMap)) {
					if (arts.some((a) => a.artifact_id === targetArtId)) {
						targetDsId = dId;
						break;
					}
				}
			}

			if (!targetDsId && dsList.length > 0) {
				// Prefer a dataset that has at least one FEATURE_ENGINEERED or PRE_PROCESSED artifact
				const dsWithEligible = dsList.find((d) =>
					(artMap[d.dataset_id] || []).some(
						(a) =>
							(a.pipeline_stage === 'FEATURE_ENGINEERED' ||
								a.pipeline_stage === 'PRE_PROCESSED') &&
							a.validation_status !== 'FAILED'
					)
				);
				targetDsId = (dsWithEligible || dsList[0]).dataset_id;
			}

			if (targetDsId && !targetArtId) {
				const eligible = (artMap[targetDsId] || []).filter(
					(a) =>
						(a.pipeline_stage === 'FEATURE_ENGINEERED' ||
							a.pipeline_stage === 'PRE_PROCESSED') &&
						a.validation_status !== 'FAILED'
				);
				if (eligible.length > 0) {
					targetArtId = eligible[eligible.length - 1].artifact_id;
				}
			}

			setSelectedDatasetId(targetDsId);
			setSelectedArtifactId(targetArtId);

			// Auto-select model
			let targetModId = selectedModelId;
			if (!targetModId && modelList.length > 0) {
				targetModId = modelList[0].model_id;
			}
			if (targetModId) {
				const foundModel = modelList.find((m) => m.model_id === targetModId);
				setSelectedModelId(targetModId);
				if (foundModel) {
					const defaults = { ...(foundModel.default_hyperparameters || {}) };
					setHyperparams(defaults);
					setRawHyperparamsJson(JSON.stringify(defaults, null, 2));
					setRunName(`run-${foundModel.model_name}-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')}`);
				}
			}
		} finally {
			setIsLoadingInit(false);
		}
	}, [projectId]);

	useEffect(() => {
		loadInitialCatalog();
	}, [loadInitialCatalog]);

	const selectedDataset = useMemo(
		() => datasets.find((d) => d.dataset_id === selectedDatasetId) || null,
		[datasets, selectedDatasetId]
	);

	const datasetArtifacts = useMemo(
		() => (selectedDatasetId ? artifactsByDataset[selectedDatasetId] || [] : []),
		[artifactsByDataset, selectedDatasetId]
	);

	const eligibleArtifacts = useMemo(
		() =>
			datasetArtifacts.filter(
				(a) =>
					(a.pipeline_stage === 'FEATURE_ENGINEERED' ||
						a.pipeline_stage === 'PRE_PROCESSED') &&
					a.validation_status !== 'FAILED'
			),
		[datasetArtifacts]
	);

	const selectedArtifact = useMemo(
		() => datasetArtifacts.find((a) => a.artifact_id === selectedArtifactId) || null,
		[datasetArtifacts, selectedArtifactId]
	);

	const selectedModel = useMemo(
		() => models.find((m) => m.model_id === selectedModelId) || null,
		[models, selectedModelId]
	);

	// Normalize hyperparameter schema (supports both JSON Schema `{ properties: {...} }` and flat dict `{ param: { type, min, max } }`)
	const normalizedHyperparamFields = useMemo(() => {
		if (!selectedModel) {
			return [] as Array<{ key: string; spec: HyperparameterPropertySchema }>;
		}
		const rawSchema = selectedModel.hyperparameter_schema || {};
		const props: Record<string, any> =
			rawSchema.type === 'object' && rawSchema.properties
				? rawSchema.properties
				: rawSchema;

		const keys = new Set<string>([
			...Object.keys(props),
			...Object.keys(selectedModel.default_hyperparameters || {}),
		]);

		return Array.from(keys).map((key) => ({
			key,
			spec: (props[key] || {}) as HyperparameterPropertySchema,
		}));
	}, [selectedModel]);

	const handleSelectDataset = (dsId: string) => {
		setSelectedDatasetId(dsId);
		const arts = (artifactsByDataset[dsId] || []).filter(
			(a) =>
				(a.pipeline_stage === 'FEATURE_ENGINEERED' ||
					a.pipeline_stage === 'PRE_PROCESSED') &&
				a.validation_status !== 'FAILED'
		);
		setSelectedArtifactId(arts.length > 0 ? arts[arts.length - 1].artifact_id : '');
		setErrorMsg(null);
	};

	const handleSelectModel = (model: ModelResponse) => {
		setSelectedModelId(model.model_id);
		const defaults = { ...(model.default_hyperparameters || {}) };
		setHyperparams(defaults);
		setRawHyperparamsJson(JSON.stringify(defaults, null, 2));
		setRunName(
			`run-${model.model_name}-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')}`
		);
		setErrorMsg(null);
	};

	const handleResetHyperparams = () => {
		if (!selectedModel) {
			return;
		}
		const defaults = { ...(selectedModel.default_hyperparameters || {}) };
		setHyperparams(defaults);
		setRawHyperparamsJson(JSON.stringify(defaults, null, 2));
		setErrorMsg(null);
	};

	const handleParamValueChange = (key: string, rawVal: string, spec: HyperparameterPropertySchema) => {
		const propType = spec.type || typeof selectedModel?.default_hyperparameters?.[key];
		let parsed: any = rawVal;
		if (propType === 'integer' || propType === 'int') {
			const n = parseInt(rawVal, 10);
			parsed = Number.isNaN(n) ? 0 : n;
		} else if (propType === 'number' || propType === 'float') {
			const n = parseFloat(rawVal);
			parsed = Number.isNaN(n) ? 0 : n;
		} else if (propType === 'boolean') {
			parsed = rawVal === 'true';
		}
		const updated = { ...hyperparams, [key]: parsed };
		setHyperparams(updated);
		setRawHyperparamsJson(JSON.stringify(updated, null, 2));
	};

	const steps: PipelineStep[] = [
		{
			id: 'step-data',
			stepNumber: 1,
			label: '1. Training Data',
			description: 'Select FEATURE_ENGINEERED Artifact',
			state:
				currentStep === 'step-data'
					? 'active'
					: selectedArtifactId
					? 'completed'
					: 'locked',
		},
		{
			id: 'step-model',
			stepNumber: 2,
			label: '2. Algorithm & Hyperparameters',
			description: 'Model & Hyperparameter Config',
			state:
				currentStep === 'step-model'
					? 'active'
					: currentStep === 'step-review'
					? 'completed'
					: selectedArtifactId
					? 'completed'
					: 'locked',
		},
		{
			id: 'step-review',
			stepNumber: 3,
			label: '3. Review & Launch',
			description: 'Confirm & Dispatch Training Run',
			state: currentStep === 'step-review' ? 'active' : 'locked',
		},
	];

	const handleLaunchTraining = async () => {
		if (!selectedArtifactId) {
			setErrorMsg('Vui lòng chọn một DatasetArtifact hợp lệ ở trạng thái FEATURE_ENGINEERED hoặc PRE_PROCESSED.');
			return;
		}
		if (!selectedModelId) {
			setErrorMsg('Vui lòng chọn một mô hình học máy từ Model Registry.');
			return;
		}

		let finalHyperparams = hyperparams;
		if (jsonEditMode) {
			try {
				finalHyperparams = JSON.parse(rawHyperparamsJson);
			} catch {
				setErrorMsg('Cấu hình JSON Hyperparameters không hợp lệ.');
				return;
			}
		}

		setIsSubmitting(true);
		setErrorMsg(null);
		try {
			const res = await trainingApi.startTrainingRun({
				model_id: selectedModelId,
				dataset_artifact_id: selectedArtifactId,
				project_id: projectId,
				hyperparameters: finalHyperparams,
				run_name: runName.trim() || undefined,
			});
			if (!res.success || !res.data) {
				setErrorMsg(res.error || 'Khởi chạy huấn luyện mô hình thất bại.');
				return;
			}
			navigate(`/models/runs/${res.data.run_id}`);
		} catch (err: any) {
			setErrorMsg(err?.message || 'Khởi chạy huấn luyện mô hình thất bại.');
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden bg-dark-950">
			{/* Top Bar */}
			<div className="px-6 py-3.5 border-b border-dark-800 bg-dark-900/60 flex items-center justify-between">
				<div className="flex items-center gap-3">
					<button
						type="button"
						onClick={() => navigate('/models')}
						className="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-slate-300 transition"
						title="Quay lại Model Hub"
					>
						<ArrowLeft className="w-4 h-4" />
					</button>
					<div>
						<div className="flex items-center gap-2">
							<h1 className="text-sm font-bold text-slate-100">
								Start Model Training Wizard
							</h1>
							<span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-brand-500/15 text-brand-400 border border-brand-500/30">
								SUC-08
							</span>
						</div>
						<p className="text-[11px] text-slate-400">
							Chọn tập dữ liệu `FEATURE_ENGINEERED`, cấu hình siêu tham số và thực thi huấn luyện mô hình
						</p>
					</div>
				</div>
			</div>

			{/* Stepper */}
			<WorkspaceStepper
				steps={steps}
				currentStepId={currentStep}
				onSelectStep={(id) => {
					if (id === 'step-data') {
						setCurrentStep('step-data');
					} else if (id === 'step-model' && selectedArtifactId) {
						setCurrentStep('step-model');
					} else if (id === 'step-review' && selectedArtifactId && selectedModelId) {
						setCurrentStep('step-review');
					}
				}}
			/>

			{/* Main Wizard Body */}
			<div className="flex-1 overflow-y-auto p-6">
				<div className="max-w-5xl mx-auto space-y-5">
					{errorMsg && (
						<div
							role="alert"
							className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2.5"
						>
							<ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
							<span>{errorMsg}</span>
						</div>
					)}

					{isLoadingInit ? (
						<div className="p-12 rounded-xl bg-dark-900 border border-dark-800 flex items-center justify-center gap-2.5 text-xs text-slate-400">
							<Loader2 className="w-4 h-4 animate-spin text-brand-400" />
							<span>Đang tải danh mục Dataset Artifacts và Model Registry...</span>
						</div>
					) : currentStep === 'step-data' ? (
						/* STEP 1: TRAINING DATA */
						<div className="bg-dark-900 border border-dark-800 rounded-xl p-6 space-y-5">
							<div className="flex items-center gap-2.5 border-b border-dark-800 pb-3">
								<Database className="w-4 h-4 text-brand-400" />
								<h2 className="text-sm font-bold text-slate-100">
									Bước 1: Chọn Tập dữ liệu Huấn luyện (`FEATURE_ENGINEERED` / `PRE_PROCESSED`)
								</h2>
							</div>

							<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
								<div>
									<label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
										Chọn Dataset trong Dự án
									</label>
									<select
										value={selectedDatasetId}
										onChange={(e) => handleSelectDataset(e.target.value)}
										className="w-full px-3 py-2.5 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
									>
										<option value="">-- Chọn Dataset --</option>
										{datasets.map((ds) => (
											<option key={ds.dataset_id} value={ds.dataset_id}>
												{ds.display_name || ds.dataset_name} ({ds.artifacts_count} artifacts)
											</option>
										))}
									</select>
								</div>

								<div>
									<label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
										Chọn Phiên bản Artifact (`dataset_artifact_id`)
									</label>
									<select
										value={selectedArtifactId}
										onChange={(e) => setSelectedArtifactId(e.target.value)}
										disabled={!selectedDatasetId}
										className="w-full px-3 py-2.5 bg-dark-950 border border-dark-700 rounded-lg text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none disabled:opacity-50"
									>
										<option value="">-- Chọn Artifact FEATURE_ENGINEERED --</option>
										{eligibleArtifacts.map((art) => (
											<option key={art.artifact_id} value={art.artifact_id}>
												[{art.pipeline_stage}] {art.artifact_id.slice(0, 8)}... ({art.row_count ?? '—'} rows · {art.column_count ?? '—'} cols)
											</option>
										))}
									</select>
								</div>
							</div>

							{selectedDatasetId && eligibleArtifacts.length === 0 && (
								<div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 flex items-center justify-between gap-4">
									<span>
										Dataset này chưa có Artifact nào đạt trạng thái <strong className="font-mono">FEATURE_ENGINEERED</strong>. Vui lòng thực hiện Schema Mapping & Feature Engineering trước.
									</span>
									<button
										type="button"
										onClick={() => navigate(`/datasets/${selectedDatasetId}`)}
										className="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 font-semibold shrink-0"
									>
										Mở Data Pipeline →
									</button>
								</div>
							)}

							{selectedArtifact && (
								<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-3">
									<div className="flex items-center justify-between">
										<span className="text-xs font-bold text-slate-200 flex items-center gap-2">
											<CheckCircle2 className="w-4 h-4 text-emerald-400" />
											Thông tin Artifact đã chọn
										</span>
										<span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-500/15 text-purple-400 border border-purple-500/30">
											{selectedArtifact.pipeline_stage}
										</span>
									</div>
									<div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
										<div className="p-2.5 rounded-lg bg-dark-900 border border-dark-800">
											<div className="text-[10px] text-slate-400">Artifact ID</div>
											<div className="font-mono text-slate-100 mt-0.5 truncate" title={selectedArtifact.artifact_id}>
												{selectedArtifact.artifact_id}
											</div>
										</div>
										<div className="p-2.5 rounded-lg bg-dark-900 border border-dark-800">
											<div className="text-[10px] text-slate-400">Row Count</div>
											<div className="font-mono font-bold text-slate-100 mt-0.5">
												{selectedArtifact.row_count?.toLocaleString() ?? '—'}
											</div>
										</div>
										<div className="p-2.5 rounded-lg bg-dark-900 border border-dark-800">
											<div className="text-[10px] text-slate-400">Column Count</div>
											<div className="font-mono font-bold text-slate-100 mt-0.5">
												{selectedArtifact.column_count ?? '—'}
											</div>
										</div>
										<div className="p-2.5 rounded-lg bg-dark-900 border border-dark-800">
											<div className="text-[10px] text-slate-400">Target Column</div>
											<div className="font-mono font-bold text-emerald-400 mt-0.5">
												{selectedArtifact.validation_report?.target_column || 'label'}
											</div>
										</div>
									</div>
								</div>
							)}

							<div className="flex justify-end pt-3 border-t border-dark-800">
								<button
									type="button"
									disabled={!selectedArtifactId}
									onClick={() => setCurrentStep('step-model')}
									className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white text-xs font-semibold transition flex items-center gap-2"
								>
									<span>Next: Algorithm & Hyperparameters</span>
									<ArrowRight className="w-4 h-4" />
								</button>
							</div>
						</div>
					) : currentStep === 'step-model' ? (
						/* STEP 2: ALGORITHM & HYPERPARAMETERS */
						<div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
							{/* Left Column: Algorithm Catalog (5 cols) */}
							<div className="lg:col-span-5 bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-4">
								<div className="flex items-center justify-between border-b border-dark-800 pb-3">
									<div className="flex items-center gap-2">
										<BrainCircuit className="w-4 h-4 text-brand-400" />
										<h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
											Algorithm Catalog ({models.length})
										</h2>
									</div>
									<button
										type="button"
										onClick={() => setIsImportModalOpen(true)}
										className="text-[11px] font-semibold text-brand-400 hover:text-brand-300 flex items-center gap-1"
									>
										<Code2 className="w-3.5 h-3.5" />
										<span>+ Import Plugin</span>
									</button>
								</div>

								<div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1">
									{models.map((m) => {
										const isSelected = m.model_id === selectedModelId;
										return (
											<button
												key={m.model_id}
												type="button"
												onClick={() => handleSelectModel(m)}
												className={`w-full p-3.5 rounded-xl border text-left transition ${
													isSelected
														? 'bg-brand-500/15 border-brand-500/50 shadow-glow-blue'
														: 'bg-dark-950 border-dark-800 hover:border-dark-700'
												}`}
											>
												<div className="flex items-center justify-between gap-2">
													<span className="text-xs font-bold text-slate-100">
														{m.display_name || m.model_name}
													</span>
													<span
														className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
															m.execution_type === 'BUILTIN'
																? 'bg-brand-500/15 text-brand-400 border border-brand-500/30'
																: 'bg-purple-500/15 text-purple-400 border border-purple-500/30'
														}`}
													>
														{m.execution_type}
													</span>
												</div>
												<div className="text-[11px] font-mono text-slate-400 mt-0.5">
													{m.model_name}
												</div>
												{m.description && (
													<p className="text-[11px] text-slate-400 mt-1.5 line-clamp-2">
														{m.description}
													</p>
												)}
											</button>
										);
									})}
								</div>
							</div>

							{/* Right Column: Hyperparameters Form (7 cols) */}
							<div className="lg:col-span-7 bg-dark-900 border border-dark-800 rounded-xl p-5 flex flex-col justify-between space-y-5">
								<div className="space-y-4">
									<div className="flex items-center justify-between border-b border-dark-800 pb-3">
										<div className="flex items-center gap-2">
											<Sliders className="w-4 h-4 text-brand-400" />
											<h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
												Hyperparameters Configuration
											</h2>
										</div>
										<div className="flex items-center gap-2">
											<button
												type="button"
												onClick={() => setJsonEditMode(!jsonEditMode)}
												className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-[11px] font-mono text-slate-300 transition"
											>
												{jsonEditMode ? 'Form View' : '{ } Edit JSON'}
											</button>
											<button
												type="button"
												onClick={handleResetHyperparams}
												className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-[11px] text-slate-300 transition flex items-center gap-1"
											>
												<RotateCcw className="w-3 h-3" />
												<span>Reset Defaults</span>
											</button>
										</div>
									</div>

									{selectedModel && (
										<div className="p-3 rounded-xl bg-dark-950 border border-dark-800 text-[11px] text-slate-400">
											<strong className="text-slate-200">Model-Owned Normalization:</strong> Mô hình{' '}
											<span className="font-mono text-brand-400">{selectedModel.model_name}</span> tự động đóng gói bước chuẩn hóa đặc trưng (<span className="font-mono text-slate-300">preprocessor.joblib</span>) cùng tệp trọng số để đảm bảo đồng bộ tuyệt đối khi suy diễn.
										</div>
									)}

									{jsonEditMode ? (
										<div>
											<label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
												Hyperparameters JSON
											</label>
											<textarea
												rows={10}
												value={rawHyperparamsJson}
												onChange={(e) => setRawHyperparamsJson(e.target.value)}
												className="w-full p-3 bg-dark-950 border border-dark-700 rounded-xl text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none"
											/>
										</div>
									) : normalizedHyperparamFields.length === 0 ? (
										<div className="p-6 text-center text-xs text-slate-400 bg-dark-950 rounded-xl border border-dark-800">
											Mô hình này không khai báo schema siêu tham số cố định. Bạn có thể chuyển sang chế độ{' '}
											<button
												type="button"
												onClick={() => setJsonEditMode(true)}
												className="text-brand-400 underline font-mono"
											>
												{'{ } Edit JSON'}
											</button>{' '}
											để truyền tham số tùy chỉnh.
										</div>
									) : (
										<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
											{normalizedHyperparamFields.map(({ key, spec }) => {
												const currentVal =
													hyperparams[key] ??
													spec.default ??
													selectedModel?.default_hyperparameters?.[key] ??
													'';
												const minVal = spec.minimum ?? spec.min;
												const maxVal = spec.maximum ?? spec.max;
												const isNumeric =
													spec.type === 'integer' ||
													spec.type === 'int' ||
													spec.type === 'number' ||
													spec.type === 'float' ||
													typeof currentVal === 'number';
												const stepVal =
													spec.type === 'number' || spec.type === 'float' ? 'any' : '1';

												return (
													<div
														key={key}
														className="p-3 rounded-xl bg-dark-950 border border-dark-800 space-y-1.5"
													>
														<div className="flex items-center justify-between">
															<label className="text-xs font-mono font-semibold text-slate-200">
																{key}
															</label>
															<span className="text-[10px] font-mono text-slate-500">
																{spec.type || typeof currentVal}
																{minVal !== undefined || maxVal !== undefined
																	? ` [${minVal ?? '—'}..${maxVal ?? '—'}]`
																	: ''}
															</span>
														</div>
														{spec.enum ? (
															<select
																value={String(currentVal)}
																onChange={(e) => handleParamValueChange(key, e.target.value, spec)}
																className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none"
															>
																{spec.enum.map((opt) => (
																	<option key={String(opt)} value={String(opt)}>
																		{String(opt)}
																	</option>
																))}
															</select>
														) : (
															<input
																type={isNumeric ? 'number' : 'text'}
																step={isNumeric ? stepVal : undefined}
																min={minVal}
																max={maxVal}
																value={currentVal}
																onChange={(e) => handleParamValueChange(key, e.target.value, spec)}
																className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none"
															/>
														)}
													</div>
												);
											})}
										</div>
									)}
								</div>

								<div className="flex items-center justify-between pt-4 border-t border-dark-800">
									<button
										type="button"
										onClick={() => setCurrentStep('step-data')}
										className="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-xs font-medium text-slate-300 transition flex items-center gap-2"
									>
										<ArrowLeft className="w-4 h-4" />
										<span>Back</span>
									</button>
									<button
										type="button"
										disabled={!selectedModelId}
										onClick={() => setCurrentStep('step-review')}
										className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white text-xs font-semibold transition flex items-center gap-2"
									>
										<span>Next: Review & Launch</span>
										<ArrowRight className="w-4 h-4" />
									</button>
								</div>
							</div>
						</div>
					) : (
						/* STEP 3: REVIEW & LAUNCH */
						<div className="bg-dark-900 border border-dark-800 rounded-xl p-6 space-y-5">
							<div className="flex items-center gap-2.5 border-b border-dark-800 pb-3">
								<Play className="w-4 h-4 text-emerald-400" />
								<h2 className="text-sm font-bold text-slate-100">
									Bước 3: Kiểm tra Cấu hình & Khởi chạy Huấn luyện (Review & Launch)
								</h2>
							</div>

							<div>
								<label
									htmlFor="training-run-name-input"
									className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
								>
									Tên lần chạy huấn luyện (`run_name`)
								</label>
								<input
									id="training-run-name-input"
									type="text"
									value={runName}
									onChange={(e) => setRunName(e.target.value)}
									placeholder="Ví dụ: rf-fraud-baseline-v1"
									className="w-full max-w-md px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none"
								/>
							</div>

							<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
								<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2.5 text-xs">
									<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
										Tập dữ liệu & Mô hình
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Dataset:</span>
										<span className="font-semibold text-slate-100">
											{selectedDataset?.display_name || selectedDataset?.dataset_name || '—'}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Artifact ID:</span>
										<span className="font-mono text-slate-200">
											{selectedArtifact?.artifact_id.slice(0, 12)}... ({selectedArtifact?.pipeline_stage})
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Target Model:</span>
										<span className="font-semibold text-brand-400">
											{selectedModel?.display_name || selectedModel?.model_name}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Execution Type:</span>
										<span className="font-mono text-slate-200">
											{selectedModel?.execution_type}
										</span>
									</div>
								</div>

								<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2">
									<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
										Hyperparameters (`hyperparameters`)
									</div>
									<pre className="text-[11px] font-mono text-slate-200 overflow-x-auto max-h-36">
										{jsonEditMode
											? rawHyperparamsJson
											: JSON.stringify(hyperparams, null, 2)}
									</pre>
								</div>
							</div>

							<div className="flex items-center justify-between pt-4 border-t border-dark-800">
								<button
									type="button"
									disabled={isSubmitting}
									onClick={() => setCurrentStep('step-model')}
									className="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-xs font-medium text-slate-300 transition flex items-center gap-2"
								>
									<ArrowLeft className="w-4 h-4" />
									<span>Back</span>
								</button>

								<button
									type="button"
									disabled={isSubmitting}
									onClick={handleLaunchTraining}
									className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-glow-green transition flex items-center gap-2"
								>
									{isSubmitting ? (
										<>
											<Loader2 className="w-4 h-4 animate-spin" />
											<span>Đang thực thi huấn luyện mô hình...</span>
										</>
									) : (
										<>
											<Play className="w-4 h-4" />
											<span>Start Training</span>
										</>
									)}
								</button>
							</div>
						</div>
					)}
				</div>
			</div>

			<ImportCustomModelModal
				isOpen={isImportModalOpen}
				projectId={projectId}
				onClose={() => setIsImportModalOpen(false)}
				onSuccess={(newModel) => {
					setModels((prev) => [newModel, ...prev]);
					handleSelectModel(newModel);
				}}
			/>
		</div>
	);
};
