import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
	ArrowLeft,
	ArrowRight,
	Play,
	Database,
	FileSpreadsheet,
	UploadCloud,
	Cpu,
	ShieldCheck,
	Sliders,
	CheckCircle2,
	AlertTriangle,
	Loader2,
	Trash2,
	Lock,
	Sparkles,
} from 'lucide-react';
import { PageHeader } from '../../layout/PageHeader';
import { WorkspaceStepper } from '../../layout/WorkspaceStepper';
import type { PipelineStep } from '../../layout/WorkspaceStepper';
import { datasetApi, trainingApi, ruleApi, detectionApi } from '@/api';
import { useProject } from '@/hooks';
import type {
	DatasetArtifactResponse,
	DatasetResponse,
	ModelResponse,
	ModelVersionResponse,
	RuleResponse,
} from '@/types';

type InputSourceOption = 'RAW_ARTIFACT' | 'FILE_PATH';

interface RawArtifactOptionItem {
	dataset: DatasetResponse;
	artifact: DatasetArtifactResponse;
}

interface ApprovedModelOptionItem {
	model: ModelResponse;
	version: ModelVersionResponse;
}

export function DetectionJobWizardView() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const { currentProject } = useProject();
	const projectId = currentProject?.project_id || '';

	const [activeStep, setActiveStep] = useState<'source' | 'engine' | 'policy'>('source');
	const [sourceOption, setSourceOption] = useState<InputSourceOption>('RAW_ARTIFACT');
	const [selectedRawArtifactId, setSelectedRawArtifactId] = useState<string>('');

	// Option 2: Direct file path state
	const [inputFilePath, setInputFilePath] = useState<string>('');
	const [selectedFileInfo, setSelectedFileInfo] = useState<{
		name: string;
		size: string;
		path: string;
	} | null>(null);
	const fileInputRef = useRef<HTMLInputElement>(null);

	// Step 2: Engine state
	const [selectedModelVersionId, setSelectedModelVersionId] = useState<string>('RULE_ONLY');
	const [useRules, setUseRules] = useState<boolean>(true);

	// Step 3: Threshold & Job Name
	const [scoreThreshold, setScoreThreshold] = useState<number>(0.5);
	const [jobName, setJobName] = useState<string>('');
	const [errorMsg, setErrorMsg] = useState<string | null>(null);

	// 1. Fetch Project Datasets & their RAW Artifacts
	const { data: rawArtifactsList = [], isLoading: isLoadingArtifacts } = useQuery({
		queryKey: ['project-raw-artifacts', projectId],
		queryFn: async (): Promise<RawArtifactOptionItem[]> => {
			if (!projectId) {
				return [];
			}
			const dsRes = await datasetApi.listDatasets(projectId);
			const datasets = dsRes.data || [];
			const details = await Promise.all(
				datasets.map((d) => datasetApi.getDatasetDetail(d.dataset_id))
			);
			const items: RawArtifactOptionItem[] = [];
			for (const detailRes of details) {
				if (!detailRes.success || !detailRes.data) {
					continue;
				}
				const { dataset, artifacts } = detailRes.data;
				const rawArts = (artifacts || []).filter(
					(a) => a.pipeline_stage === 'RAW'
				);
				for (const rawArt of rawArts) {
					items.push({ dataset, artifact: rawArt });
				}
			}
			return items;
		},
		enabled: Boolean(projectId),
	});

	// Auto-select first RAW artifact when loaded
	useEffect(() => {
		if (!selectedRawArtifactId && rawArtifactsList.length > 0) {
			setSelectedRawArtifactId(rawArtifactsList[0].artifact.artifact_id);
		}
	}, [rawArtifactsList, selectedRawArtifactId]);

	// 2. Fetch Approved ModelVersions in Project
	const { data: approvedModelsList = [], isLoading: isLoadingModels } = useQuery({
		queryKey: ['project-approved-model-versions', projectId],
		queryFn: async (): Promise<ApprovedModelOptionItem[]> => {
			if (!projectId) {
				return [];
			}
			const modelsRes = await trainingApi.listModels(projectId);
			const models = modelsRes.data || [];
			const versionLists = await Promise.all(
				models.map(async (m) => {
					const verRes = await trainingApi.listModelVersions(m.model_id);
					return {
						model: m,
						versions: verRes.data || [],
					};
				})
			);
			const approved: ApprovedModelOptionItem[] = [];
			for (const entry of versionLists) {
				for (const v of entry.versions) {
					if (v.status === 'APPROVED') {
						if (!v.project_id || v.project_id === projectId) {
							approved.push({ model: entry.model, version: v });
						}
					}
				}
			}
			return approved;
		},
		enabled: Boolean(projectId),
	});

	// Auto-select first APPROVED ModelVersion when available
	useEffect(() => {
		if (selectedModelVersionId === 'RULE_ONLY' && approvedModelsList.length > 0) {
			const first = approvedModelsList[0];
			setSelectedModelVersionId(first.version.version_id);
			setScoreThreshold(first.version.decision_threshold ?? 0.5);
		}
	}, [approvedModelsList, selectedModelVersionId]);

	// 3. Fetch Active Project Rules
	const { data: activeRulesRes, isLoading: isLoadingRules } = useQuery({
		queryKey: ['project-active-rules', projectId],
		queryFn: () => ruleApi.listRules(projectId, 'ACTIVE'),
		enabled: Boolean(projectId),
	});

	const activeRules: RuleResponse[] = useMemo(() => {
		return activeRulesRes?.data || [];
	}, [activeRulesRes]);

	const selectedApprovedModel = useMemo(() => {
		if (selectedModelVersionId === 'RULE_ONLY') {
			return null;
		}
		return (
			approvedModelsList.find(
				(item) => item.version.version_id === selectedModelVersionId
			) || null
		);
	}, [approvedModelsList, selectedModelVersionId]);

	const selectedRawArtifactItem = useMemo(() => {
		return (
			rawArtifactsList.find(
				(item) => item.artifact.artifact_id === selectedRawArtifactId
			) || null
		);
	}, [rawArtifactsList, selectedRawArtifactId]);

	// Auto-generate suggested job name
	useEffect(() => {
		if (!jobName) {
			const dateTag = new Date().toISOString().slice(0, 10);
			setJobName(`batch-scan-${dateTag}`);
		}
	}, [jobName]);

	// File selection handlers for Option 2
	const handleFileSelected = useCallback(
		(selected: File) => {
			const sizeMb = (selected.size / (1024 * 1024)).toFixed(2);
			let desktopNativePath = '';
			if (window.electronAPI?.getPathForFile) {
				try {
					desktopNativePath = window.electronAPI.getPathForFile(selected) || '';
				} catch {
					// Ignore fallback
				}
			}
			if (!desktopNativePath) {
				desktopNativePath = (selected as unknown as { path?: string }).path || '';
			}
			const resolvedPath =
				desktopNativePath && desktopNativePath.length > 0
					? desktopNativePath
					: inputFilePath && inputFilePath.endsWith(selected.name)
						? inputFilePath
						: `../datasets/${selected.name}`;

			setSelectedFileInfo({
				name: selected.name,
				size: `${sizeMb} MB`,
				path: resolvedPath,
			});
			setInputFilePath(resolvedPath);
			setErrorMsg(null);
		},
		[inputFilePath]
	);

	const handleBrowseNativeFile = useCallback(async () => {
		if (window.electronAPI?.openFileDialog) {
			try {
				const selectedPath = await window.electronAPI.openFileDialog({
					title: 'Select Transaction Batch File for Detection',
					filters: [
						{
							name: 'Transaction Files (*.csv, *.parquet, *.pq, *.json)',
							extensions: ['csv', 'parquet', 'pq', 'json'],
						},
						{ name: 'All Files (*.*)', extensions: ['*'] },
					],
				});
				if (selectedPath) {
					const fileName = selectedPath.split(/[/\\]/).pop() || 'batch.csv';
					setSelectedFileInfo({
						name: fileName,
						size: 'Local Disk File',
						path: selectedPath,
					});
					setInputFilePath(selectedPath);
					setErrorMsg(null);
					return;
				}
			} catch {
				// Fallback to fileInputRef
			}
		}
		fileInputRef.current?.click();
	}, []);

	const startJobMutation = useMutation({
		mutationFn: async () => {
			const isArtifact = sourceOption === 'RAW_ARTIFACT';
			const res = await detectionApi.startJob({
				project_id: projectId,
				target_artifact_id: isArtifact ? selectedRawArtifactId : null,
				input_file_path: !isArtifact ? inputFilePath.trim() : null,
				model_version_id:
					selectedModelVersionId !== 'RULE_ONLY' ? selectedModelVersionId : null,
				use_rules: useRules,
				score_threshold: scoreThreshold,
				job_name: jobName.trim() || undefined,
				created_by: 'analyst',
			});
			if (!res.success || !res.data) {
				throw new Error(res.error || 'Failed to start detection job.');
			}
			return res.data;
		},
		onSuccess: (createdJob) => {
			queryClient.invalidateQueries({ queryKey: ['detection-jobs', projectId] });
			navigate(`/detection/jobs/${createdJob.job_id}`);
		},
		onError: (err: Error) => {
			setErrorMsg(err.message || 'Error starting detection job.');
		},
	});

	const canProceedFromSource =
		sourceOption === 'RAW_ARTIFACT'
			? Boolean(selectedRawArtifactId)
			: Boolean(inputFilePath.trim());

	const canProceedFromEngine =
		selectedModelVersionId !== 'RULE_ONLY' ||
		(useRules && activeRules.length > 0);

	const wizardSteps: PipelineStep[] = [
		{
			id: 'source',
			stepNumber: 1,
			label: 'Input Data Source',
			description: 'RAW Artifact or File Upload',
			state:
				activeStep === 'source'
					? 'active'
					: canProceedFromSource
						? 'completed'
						: 'locked',
		},
		{
			id: 'engine',
			stepNumber: 2,
			label: 'Hybrid Detection Engine',
			description: 'AI Model & Active Rules',
			state:
				activeStep === 'engine'
					? 'active'
					: activeStep === 'policy'
						? 'completed'
						: canProceedFromSource
							? 'completed'
							: 'locked',
		},
		{
			id: 'policy',
			stepNumber: 3,
			label: 'Decision Policy & Launch',
			description: 'Score Threshold & Execution',
			state:
				activeStep === 'policy'
					? 'active'
					: canProceedFromSource && canProceedFromEngine
						? 'completed'
						: 'locked',
		},
	];

	return (
		<div className="flex-1 flex flex-col overflow-hidden bg-dark-950">
			<WorkspaceStepper
				steps={wizardSteps}
				currentStepId={activeStep}
				onSelectStep={(stepId) => {
					if (stepId === 'source') {
						setActiveStep('source');
					} else if (stepId === 'engine' && canProceedFromSource) {
						setActiveStep('engine');
					} else if (
						stepId === 'policy' &&
						canProceedFromSource &&
						canProceedFromEngine
					) {
						setActiveStep('policy');
					}
				}}
			/>

			<PageHeader
				title="Start Fraud Detection Job"
				badgeColor="blue"
				breadcrumbs={[
					{ label: 'Detection Jobs', onClick: () => navigate('/detection') },
					{ label: 'New Detection Job' },
				]}
				actions={
					<button
						type="button"
						onClick={() => navigate('/detection')}
						className="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs font-medium text-slate-300 flex items-center gap-1.5 transition"
					>
						<ArrowLeft className="w-3.5 h-3.5" />
						Back to Jobs Hub
					</button>
				}
			/>

			<div className="flex-1 overflow-y-auto p-6">
				<div className="max-w-4xl mx-auto space-y-6">
					{errorMsg && (
						<div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2.5">
							<AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
							<span>{errorMsg}</span>
						</div>
					)}

					{/* STEP 1: INPUT DATA SOURCE */}
					{activeStep === 'source' && (
						<div className="space-y-5">
							{/* Dual-Option Selector Cards */}
							<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
								<button
									type="button"
									onClick={() => {
										setSourceOption('RAW_ARTIFACT');
										setErrorMsg(null);
									}}
									className={`p-4 rounded-xl border text-left transition flex items-start gap-3.5 ${sourceOption === 'RAW_ARTIFACT'
										? 'bg-brand-500/10 border-brand-500/60 shadow-lg shadow-brand-500/5'
										: 'bg-dark-900 border-dark-800 hover:border-dark-700'
										}`}
								>
									<div
										className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${sourceOption === 'RAW_ARTIFACT'
											? 'bg-brand-500/20 text-brand-400 border border-brand-500/40'
											: 'bg-dark-850 text-slate-400 border border-dark-700'
											}`}
									>
										<Database className="w-5 h-5" />
									</div>
									<div>
										<div className="flex items-center gap-2">
											<span className="text-xs font-bold text-slate-100">
												Option 1: Existing Dataset
											</span>
										</div>
									</div>
								</button>

								<button
									type="button"
									onClick={() => {
										setSourceOption('FILE_PATH');
										setErrorMsg(null);
									}}
									className={`p-4 rounded-xl border text-left transition flex items-start gap-3.5 ${sourceOption === 'FILE_PATH'
										? 'bg-brand-500/10 border-brand-500/60 shadow-lg shadow-brand-500/5'
										: 'bg-dark-900 border-dark-800 hover:border-dark-700'
										}`}
								>
									<div
										className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${sourceOption === 'FILE_PATH'
											? 'bg-brand-500/20 text-brand-400 border border-brand-500/40'
											: 'bg-dark-850 text-slate-400 border border-dark-700'
											}`}
									>
										<UploadCloud className="w-5 h-5" />
									</div>
									<div>
										<div className="flex items-center gap-2">
											<span className="text-xs font-bold text-slate-100">
												Option 2: Upload Dataset
											</span>
										</div>
									</div>
								</button>
							</div>

							{/* Option 1 Content: RAW DatasetArtifact Picker */}
							{sourceOption === 'RAW_ARTIFACT' && (
								<div className="p-5 rounded-xl bg-dark-900 border border-dark-800 space-y-4">
									<div className="flex items-center justify-between">
										<div>
											<h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
												Select Project RAW Dataset Artifact
											</h3>
											<p className="text-[11px] text-slate-400 mt-0.5">
												Only dataset artifacts at stage{' '}
												<code className="text-sky-400 font-mono">RAW</code> are eligible for end-to-end batch detection.
											</p>
										</div>
										<span className="text-[11px] font-mono text-slate-400">
											{rawArtifactsList.length} RAW artifact(s) available
										</span>
									</div>

									{isLoadingArtifacts ? (
										<div className="p-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
											<Loader2 className="w-4 h-4 animate-spin text-brand-400" />
											<span>Loading RAW dataset artifacts...</span>
										</div>
									) : rawArtifactsList.length === 0 ? (
										<div className="p-6 rounded-xl bg-dark-950 border border-dark-800 text-center space-y-2">
											<p className="text-xs font-medium text-slate-300">
												Dự án hiện chưa có DatasetArtifact nào ở bước RAW.
											</p>
											<p className="text-[11px] text-slate-500">
												Bạn có thể chuyển sang{' '}
												<button
													type="button"
													onClick={() => setSourceOption('FILE_PATH')}
													className="text-brand-400 underline font-medium"
												>
													Option 2: Direct File Upload / File Path
												</button>{' '}
												để chọn tệp trực tiếp ngay tại đây.
											</p>
										</div>
									) : (
										<div className="grid grid-cols-1 gap-2.5 max-h-72 overflow-y-auto pr-1">
											{rawArtifactsList.map(({ dataset, artifact }) => {
												const isSelected =
													selectedRawArtifactId === artifact.artifact_id;
												return (
													<div
														key={artifact.artifact_id}
														onClick={() =>
															setSelectedRawArtifactId(artifact.artifact_id)
														}
														className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${isSelected
															? 'bg-brand-500/10 border-brand-500/50'
															: 'bg-dark-950/70 border-dark-800 hover:border-dark-700'
															}`}
													>
														<div className="flex items-center gap-3">
															<div
																className={`w-8 h-8 rounded-lg flex items-center justify-center ${isSelected
																	? 'bg-brand-500/20 text-brand-400'
																	: 'bg-dark-850 text-slate-400'
																	}`}
															>
																<Database className="w-4 h-4" />
															</div>
															<div>
																<div className="flex items-center gap-2">
																	<span className="text-xs font-semibold text-slate-100">
																		{dataset.display_name || dataset.dataset_name}
																	</span>
																	<span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-sky-500/15 text-sky-300 border border-sky-500/30">
																		RAW
																	</span>
																</div>
																<div className="text-[11px] text-slate-500 font-mono mt-0.5">
																	Artifact ID: {artifact.artifact_id.slice(0, 12)}... •Path:{' '}
																	{artifact.storage_path.split(/[/\\]/).pop()}
																</div>
															</div>
														</div>

														<div className="text-right font-mono text-xs">
															<div className="text-slate-200 font-semibold">
																{(artifact.row_count || 0).toLocaleString()} rows
															</div>
															<div className="text-[10px] text-slate-500">
																{artifact.column_count || 0} cols
															</div>
														</div>
													</div>
												);
											})}
										</div>
									)}
								</div>
							)}

							{/* Option 2 Content: File Upload / File Path */}
							{sourceOption === 'FILE_PATH' && (
								<div className="p-5 rounded-xl bg-dark-900 border border-dark-800 space-y-4">
									<div className="flex items-center justify-between">
										<div>
											<h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
												Direct Transaction File Upload
											</h3>
											<p className="text-[11px] text-slate-400 mt-0.5">
												Chọn tệp từ máy tính hoặc nhập đường dẫn tệp (`.csv`, `.parquet`, `.pq`, `.json`).
											</p>
										</div>
										{currentProject?.is_schema_locked && (
											<span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-[10px] font-mono text-emerald-300">
												<Lock className="w-3 h-3" />
												Validated against Project RAW Schema
											</span>
										)}
									</div>

									{/* Drag & Drop Picker */}
									<div
										onClick={() => handleBrowseNativeFile()}
										onDragOver={(e) => {
											e.preventDefault();
											e.stopPropagation();
										}}
										onDrop={(e) => {
											e.preventDefault();
											e.stopPropagation();
											if (e.dataTransfer.files && e.dataTransfer.files[0]) {
												handleFileSelected(e.dataTransfer.files[0]);
											}
										}}
										className="border-2 border-dashed border-dark-700 hover:border-brand-500/60 bg-dark-950/60 hover:bg-brand-500/5 rounded-xl p-6 text-center cursor-pointer transition group"
									>
										<input
											type="file"
											ref={fileInputRef}
											onChange={(e) => {
												if (e.target.files && e.target.files[0]) {
													handleFileSelected(e.target.files[0]);
												}
											}}
											accept=".csv,.parquet,.pq,.json"
											className="hidden"
										/>
										<div className="w-10 h-10 rounded-xl bg-dark-850 group-hover:bg-brand-500/20 text-slate-400 group-hover:text-brand-400 mx-auto flex items-center justify-center transition mb-2">
											<FileSpreadsheet className="w-5 h-5" />
										</div>
										<p className="text-xs font-semibold text-slate-200 group-hover:text-brand-300 transition">
											Click to Browse or Drag & Drop Transaction Batch File
										</p>
										<p className="text-[11px] text-slate-500 mt-1">
											Supported formats: <code className="font-mono text-slate-300">.csv</code>,{' '}
											<code className="font-mono text-slate-300">.parquet</code>,{' '}
											<code className="font-mono text-slate-300">.json</code>
										</p>
									</div>

									{selectedFileInfo && (
										<div className="p-3 rounded-xl bg-dark-950 border border-emerald-500/30 flex items-center justify-between">
											<div className="flex items-center gap-2.5">
												<CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
												<div>
													<div className="text-xs font-semibold text-slate-200">
														{selectedFileInfo.name}
													</div>
													<div className="text-[10px] font-mono text-slate-400">
														{selectedFileInfo.size} • {selectedFileInfo.path}
													</div>
												</div>
											</div>
											<button
												type="button"
												onClick={() => {
													setSelectedFileInfo(null);
													setInputFilePath('');
												}}
												className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-dark-850 transition"
											>
												<Trash2 className="w-4 h-4" />
											</button>
										</div>
									)}
								</div>
							)}

							<div className="flex justify-end">
								<button
									type="button"
									disabled={!canProceedFromSource}
									onClick={() => setActiveStep('engine')}
									className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-xs font-semibold text-white flex items-center gap-2 transition"
								>
									Next: Select Detection Engine
									<ArrowRight className="w-4 h-4" />
								</button>
							</div>
						</div>
					)}

					{/* STEP 2: HYBRID DETECTION ENGINE */}
					{activeStep === 'engine' && (
						<div className="space-y-5">
							{/* Part A: AI ModelVersion Selection */}
							<div className="p-5 rounded-xl bg-dark-900 border border-dark-800 space-y-4">
								<div className="flex items-center justify-between">
									<div className="flex items-center gap-2.5">
										<Cpu className="w-4 h-4 text-brand-400" />
										<div>
											<h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
												AI Model Version (APPROVED)
											</h3>
											<p className="text-[11px] text-slate-400">
												Select an activated ModelVersion for ML probability scoring, or run in Rule-Only mode.
											</p>
										</div>
									</div>
									<span className="text-[11px] font-mono text-slate-400">
										{approvedModelsList.length} APPROVED version(s)
									</span>
								</div>

								{isLoadingModels ? (
									<div className="p-6 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
										<Loader2 className="w-4 h-4 animate-spin text-brand-400" />
										<span>Loading APPROVED model versions...</span>
									</div>
								) : (
									<div className="grid grid-cols-1 gap-2.5">
										{approvedModelsList.map(({ model, version }) => {
											const isSelected =
												selectedModelVersionId === version.version_id;
											return (
												<div
													key={version.version_id}
													onClick={() => {
														setSelectedModelVersionId(version.version_id);
														setScoreThreshold(
															version.decision_threshold ?? 0.5
														);
													}}
													className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${isSelected
														? 'bg-brand-500/10 border-brand-500/50'
														: 'bg-dark-950/70 border-dark-800 hover:border-dark-700'
														}`}
												>
													<div className="flex items-center gap-3">
														<div
															className={`w-8 h-8 rounded-lg flex items-center justify-center ${isSelected
																? 'bg-brand-500/20 text-brand-400'
																: 'bg-dark-850 text-slate-400'
																}`}
														>
															<Sparkles className="w-4 h-4" />
														</div>
														<div>
															<div className="flex items-center gap-2">
																<span className="text-xs font-semibold text-slate-100">
																	{model.display_name || model.model_name}
																</span>
																<span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
																	v{version.semver} • APPROVED
																</span>
																<span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-dark-850 text-slate-400 border border-dark-700">
																	{model.execution_type}
																</span>
															</div>
															<div className="text-[11px] text-slate-400 mt-0.5">
																{version.description ||
																	'Auto-traces Schema Mapping, Feature Engineering & Preprocessing artifacts'}
															</div>
														</div>
													</div>

													<div className="text-right font-mono text-xs">
														<div className="text-brand-300 font-semibold">
															θ = {(version.decision_threshold ?? 0.5).toFixed(2)}
														</div>
														<div className="text-[10px] text-slate-500">
															Default Threshold
														</div>
													</div>
												</div>
											);
										})}

										{/* Rule-Only Option */}
										<div
											onClick={() => setSelectedModelVersionId('RULE_ONLY')}
											className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${selectedModelVersionId === 'RULE_ONLY'
												? 'bg-amber-500/10 border-amber-500/50'
												: 'bg-dark-950/70 border-dark-800 hover:border-dark-700'
												}`}
										>
											<div className="flex items-center gap-3">
												<div
													className={`w-8 h-8 rounded-lg flex items-center justify-center ${selectedModelVersionId === 'RULE_ONLY'
														? 'bg-amber-500/20 text-amber-400'
														: 'bg-dark-850 text-slate-400'
														}`}
												>
													<ShieldCheck className="w-4 h-4" />
												</div>
												<div>
													<div className="text-xs font-semibold text-slate-100">
														Rule-Only Mode (No AI Model Scoring)
													</div>
													<div className="text-[11px] text-slate-400 mt-0.5">
														Evaluate transactions strictly using the project's ACTIVE deterministic business rules.
													</div>
												</div>
											</div>
											<span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30">
												DETERMINISTIC
											</span>
										</div>
									</div>
								)}
							</div>

							{/* Part B: Active Business Ruleset */}
							<div className="p-5 rounded-xl bg-dark-900 border border-dark-800 space-y-4">
								<div className="flex items-center justify-between">
									<div className="flex items-center gap-2.5">
										<ShieldCheck className="w-4 h-4 text-amber-400" />
										<div>
											<h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
												Include Active Business Rules ({activeRules.length} ACTIVE)
											</h3>
											<p className="text-[11px] text-slate-400">
												Evaluate all ACTIVE JsonLogic rules in parallel with AI model scoring.
											</p>
										</div>
									</div>
									<label className="inline-flex items-center gap-2 cursor-pointer">
										<input
											type="checkbox"
											checked={useRules}
											onChange={(e) => setUseRules(e.target.checked)}
											className="rounded border-dark-700 bg-dark-950 text-brand-500 focus:ring-brand-500"
										/>
										<span className="text-xs font-semibold text-slate-200">
											{useRules ? 'Enabled' : 'Disabled'}
										</span>
									</label>
								</div>

								{useRules && (
									<div className="space-y-2">
										{isLoadingRules ? (
											<div className="text-xs text-slate-400 py-3">
												Loading active rules...
											</div>
										) : activeRules.length === 0 ? (
											<div className="p-3.5 rounded-lg bg-dark-950 border border-dark-800 text-xs text-slate-400">
												No ACTIVE rules found in this project. Detection will rely on AI Model scoring.
											</div>
										) : (
											<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
												{activeRules.map((rule) => {
													const action =
														rule.current_version?.action || 'REVIEW';
													const badgeClass =
														action === 'REJECT'
															? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
															: action === 'REVIEW'
																? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
																: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
													return (
														<div
															key={rule.rule_id}
															className="p-2.5 rounded-lg bg-dark-950 border border-dark-800 flex items-center justify-between gap-2"
														>
															<div className="min-w-0">
																<div className="text-xs font-mono font-semibold text-slate-200 truncate">
																	{rule.rule_code}
																</div>
																<div className="text-[11px] text-slate-400 truncate">
																	{rule.name}
																</div>
															</div>
															<span
																className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold border shrink-0 ${badgeClass}`}
															>
																{action}
															</span>
														</div>
													);
												})}
											</div>
										)}
									</div>
								)}
							</div>

							{!canProceedFromEngine && (
								<div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300">
									Rule-Only mode requires at least 1 ACTIVE rule in the project, or select an APPROVED AI Model Version above.
								</div>
							)}

							<div className="flex items-center justify-between">
								<button
									type="button"
									onClick={() => setActiveStep('source')}
									className="px-4 py-2 rounded-xl bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs font-medium text-slate-300 flex items-center gap-1.5 transition"
								>
									<ArrowLeft className="w-4 h-4" />
									Back
								</button>
								<button
									type="button"
									disabled={!canProceedFromEngine}
									onClick={() => setActiveStep('policy')}
									className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-xs font-semibold text-white flex items-center gap-2 transition"
								>
									Next: Decision Policy & Launch
									<ArrowRight className="w-4 h-4" />
								</button>
							</div>
						</div>
					)}

					{/* STEP 3: DECISION POLICY & LAUNCH */}
					{activeStep === 'policy' && (
						<div className="space-y-5">
							<div className="p-5 rounded-xl bg-dark-900 border border-dark-800 space-y-5">
								<div className="flex items-center gap-2.5">
									<Sliders className="w-4 h-4 text-brand-400" />
									<div>
										<h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
											Decision Threshold & Job Identification
										</h3>
										<p className="text-[11px] text-slate-400">
											Configure the AI probability cutoff and review the hybrid decision policy before execution.
										</p>
									</div>
								</div>

								{/* Job Name */}
								<div className="space-y-1.5">
									<label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
										Detection Job Name
									</label>
									<input
										type="text"
										value={jobName}
										onChange={(e) => setJobName(e.target.value)}
										placeholder="e.g. q4-checkout-fraud-scan"
										className="w-full px-3.5 py-2 rounded-lg bg-dark-950 border border-dark-700 text-xs font-mono text-slate-100 focus:outline-none focus:border-brand-500"
									/>
								</div>

								{/* Threshold Slider (when AI Model is selected) */}
								{selectedModelVersionId !== 'RULE_ONLY' && (
									<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-3">
										<div className="flex items-center justify-between">
											<div>
												<span className="text-xs font-semibold text-slate-200">
													AI Risk Score Threshold (θ)
												</span>
												<p className="text-[11px] text-slate-400">
													Transactions with{' '}
													<code className="font-mono text-amber-300">
														model_score &gt;= {scoreThreshold.toFixed(2)}
													</code>{' '}
													are automatically flagged for{' '}
													<code className="font-mono text-amber-300">REVIEW</code>.
												</p>
											</div>
											<input
												type="number"
												step={0.01}
												min={0.01}
												max={0.99}
												value={scoreThreshold}
												onChange={(e) => {
													const val = parseFloat(e.target.value);
													if (!Number.isNaN(val) && val > 0 && val < 1) {
														setScoreThreshold(val);
													}
												}}
												className="w-24 px-2.5 py-1.5 rounded-lg bg-dark-900 border border-dark-700 text-right font-mono text-sm font-bold text-brand-300"
											/>
										</div>
										<input
											type="range"
											min={0.05}
											max={0.95}
											step={0.01}
											value={scoreThreshold}
											onChange={(e) =>
												setScoreThreshold(parseFloat(e.target.value))
											}
											className="w-full accent-brand-500 cursor-pointer"
										/>
									</div>
								)}

								{/* Hybrid Decision Aggregation Policy Card */}
								<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 space-y-2.5">
									<div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
										Hybrid Decision Aggregation Policy
									</div>
									<div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 text-xs">
										<div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/25">
											<div className="font-mono font-bold text-rose-300">
												1. REJECT (Immediate Block)
											</div>
											<p className="text-[11px] text-slate-300 mt-1">
												Triggered when any ACTIVE rule with action{' '}
												<code className="font-mono text-rose-300">REJECT</code> matches the transaction.
											</p>
										</div>
										<div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/25">
											<div className="font-mono font-bold text-amber-300">
												2. REVIEW (Analyst Queue)
											</div>
											<p className="text-[11px] text-slate-300 mt-1">
												Triggered when a{' '}
												<code className="font-mono text-amber-300">REVIEW</code> rule matches OR{' '}
												<code className="font-mono text-amber-300">
													model_score &gt;= {scoreThreshold.toFixed(2)}
												</code>.
											</p>
										</div>
										<div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/25">
											<div className="font-mono font-bold text-emerald-300">
												3. ALLOW (Clean Pass)
											</div>
											<p className="text-[11px] text-slate-300 mt-1">
												No blocking/review rules triggered and AI risk score is below threshold.
											</p>
										</div>
									</div>
								</div>

								{/* Pre-Flight Summary */}
								<div className="p-4 rounded-xl bg-dark-950 border border-dark-800 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
									<div>
										<span className="text-[10px] uppercase tracking-wider text-slate-500 block">
											Input Data Source
										</span>
										<span className="font-semibold text-slate-200 mt-0.5 block truncate">
											{sourceOption === 'RAW_ARTIFACT'
												? `${selectedRawArtifactItem?.dataset.display_name || selectedRawArtifactItem?.dataset.dataset_name || 'RAW Artifact'} (RAW)`
												: inputFilePath.split(/[/\\]/).pop() || inputFilePath}
										</span>
									</div>
									<div>
										<span className="text-[10px] uppercase tracking-wider text-slate-500 block">
											AI Model Engine
										</span>
										<span className="font-semibold text-slate-200 mt-0.5 block">
											{selectedApprovedModel
												? `${selectedApprovedModel.model.display_name || selectedApprovedModel.model.model_name} (v${selectedApprovedModel.version.semver})`
												: 'Rule-Only Mode'}
										</span>
									</div>
									<div>
										<span className="text-[10px] uppercase tracking-wider text-slate-500 block">
											Active Ruleset
										</span>
										<span className="font-semibold text-slate-200 mt-0.5 block">
											{useRules
												? `${activeRules.length} ACTIVE Rule(s) Enabled`
												: 'Rules Disabled'}
										</span>
									</div>
								</div>
							</div>

							<div className="flex items-center justify-between">
								<button
									type="button"
									onClick={() => setActiveStep('engine')}
									className="px-4 py-2 rounded-xl bg-dark-850 hover:bg-dark-800 border border-dark-700 text-xs font-medium text-slate-300 flex items-center gap-1.5 transition"
								>
									<ArrowLeft className="w-4 h-4" />
									Back
								</button>

								<button
									type="button"
									disabled={startJobMutation.isPending}
									onClick={() => startJobMutation.mutate()}
									className="px-6 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-xs font-semibold text-white flex items-center gap-2 shadow-lg shadow-brand-600/25 transition"
								>
									{startJobMutation.isPending ? (
										<>
											<Loader2 className="w-4 h-4 animate-spin" />
											Running Hybrid Detection Scan...
										</>
									) : (
										<>
											<Play className="w-4 h-4 fill-current" />
											Start Detection Job
										</>
									)}
								</button>
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
