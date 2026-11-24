import { useMemo, useState } from 'react';
import { Code2, Database, Layers, Wrench } from 'lucide-react';
import {
	useActorContext,
	useDatasetDetail,
	useDatasetList,
	useFeatureCatalog,
	useFeatureCompatibility,
	useFeatureMutations,
	useFeatureSets,
	useProject,
} from '@/hooks';
import type { FeatureResponse } from '@/types/feature';
import { FeatureBuilderTab } from './FeatureBuilderTab';
import { FeatureCatalogTab } from './FeatureCatalogTab';
import { FeatureSetsTab } from './FeatureSetsTab';

type ActiveTab = 'catalog' | 'builder' | 'sets';

export function FeatureManagementModule() {
	const { currentProjectId } = useProject();
	const { features: actorFeatures, canAccessRecord } = useActorContext(currentProjectId);

	const canCreate = actorFeatures.createFeature?.allowed ?? false;
	const [activeTab, setActiveTab] = useState<ActiveTab>('catalog');
	const [editingFeature, setEditingFeature] = useState<FeatureResponse | null>(null);
	const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
	const [selectedArtifactId, setSelectedArtifactId] = useState<string>('');

	const { datasets } = useDatasetList(currentProjectId || undefined);
	const { datasetDetail } = useDatasetDetail(
		selectedDatasetId || undefined,
		currentProjectId || undefined
	);

	const mappedArtifacts = useMemo(() => {
		const list = datasetDetail?.artifacts || [];
		return list.filter(
			(a) =>
				a.pipeline_stage === 'MAPPED' ||
				a.pipeline_stage === 'FEATURE_ENGINEERED' ||
				a.pipeline_stage === 'PRE_PROCESSED'
		);
	}, [datasetDetail]);

	const effectiveArtifactId =
		selectedArtifactId || (mappedArtifacts.length > 0 ? mappedArtifacts[0].artifact_id : undefined);

	const { data: featureCatalog = [], isLoading: isLoadingFeatures } = useFeatureCatalog(
		currentProjectId,
		{ include_builtin: true }
	);
	const { data: compatibilityReport } = useFeatureCompatibility(
		currentProjectId,
		selectedDatasetId || undefined,
		effectiveArtifactId
	);
	const { data: featureSets = [], isLoading: isLoadingSets } = useFeatureSets(
		currentProjectId,
		true
	);

	const {
		createFeature,
		updateFeature,
		deleteFeature,
		cloneFeature,
		previewFeature,
		createFeatureSet,
		deleteFeatureSet,
	} = useFeatureMutations(currentProjectId);

	const handleClone = async (feature: FeatureResponse) => {
		const cloned = await cloneFeature.mutateAsync({
			featureId: feature.feature_id,
			payload: {
				new_feature_key: `${feature.feature_key}_copy`,
				new_display_name: `${feature.display_name} (Bản sao)`,
			},
		});
		setEditingFeature(cloned);
		setActiveTab('builder');
	};

	const handleEdit = (feature: FeatureResponse) => {
		setEditingFeature(feature);
		setActiveTab('builder');
	};

	return (
		<div className="flex-1 overflow-y-auto bg-dark-950 text-slate-100 p-6 space-y-5">
			<div className="flex flex-wrap items-start justify-between gap-4 border-b border-dark-800 pb-4">
				<div>
					<h1 className="text-lg font-bold text-slate-100 flex items-center gap-2">
						<Wrench className="w-5 h-5 text-brand-400" />
						<span>Quản lý đặc trưng</span>
					</h1>
					<p className="text-xs text-slate-400 mt-1">
						Kho đặc trưng 2-Tier (DuckDB SQL + Python AST động), kiểm tra độ tương thích theo schema và gói đặc trưng theo domain.
					</p>
				</div>

				<div className="flex flex-wrap items-center gap-2">
					<select
						value={selectedDatasetId}
						onChange={(e) => {
							setSelectedDatasetId(e.target.value);
							setSelectedArtifactId('');
						}}
						aria-label="Chọn tập dữ liệu kiểm tra tương thích"
						className="bg-dark-900 border border-dark-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
					>
						<option value="">Schema chuẩn dự án</option>
						{datasets.map((ds) => (
							<option key={ds.dataset_id} value={ds.dataset_id}>
								{ds.display_name || ds.dataset_name}
							</option>
						))}
					</select>

					{mappedArtifacts.length > 0 && (
						<select
							value={effectiveArtifactId || ''}
							onChange={(e) => setSelectedArtifactId(e.target.value)}
							aria-label="Chọn artifact chạy Preview"
							className="bg-dark-900 border border-dark-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
						>
							{mappedArtifacts.map((art) => (
								<option key={art.artifact_id} value={art.artifact_id}>
									{art.pipeline_stage} • {art.artifact_id.slice(0, 8)} ({art.row_count ?? 0} dòng)
								</option>
							))}
						</select>
					)}
				</div>
			</div>

			<div className="flex flex-wrap items-center justify-between gap-3">
				<div className="inline-flex items-center gap-1 bg-dark-900 border border-dark-800 rounded-xl p-1">
					<button
						type="button"
						onClick={() => setActiveTab('catalog')}
						className={`px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition ${
							activeTab === 'catalog'
								? 'bg-brand-600 text-white'
								: 'text-slate-400 hover:text-slate-200'
						}`}
					>
						<Database className="w-3.5 h-3.5" />
						<span>Danh mục đặc trưng</span>
					</button>

					{canCreate && (
						<button
							type="button"
							onClick={() => setActiveTab('builder')}
							className={`px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition ${
								activeTab === 'builder'
									? 'bg-brand-600 text-white'
									: 'text-slate-400 hover:text-slate-200'
							}`}
						>
							<Code2 className="w-3.5 h-3.5" />
							<span>Trình tạo đặc trưng</span>
						</button>
					)}

					<button
						type="button"
						onClick={() => setActiveTab('sets')}
						className={`px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition ${
							activeTab === 'sets'
								? 'bg-brand-600 text-white'
								: 'text-slate-400 hover:text-slate-200'
						}`}
					>
						<Layers className="w-3.5 h-3.5" />
						<span>Gói đặc trưng</span>
					</button>
				</div>

				{compatibilityReport && (
					<div className="text-xs text-slate-400 font-mono">
						Khả dụng: <span className="text-emerald-400">{compatibilityReport.available_count}</span> •{' '}
						Thiếu điều kiện:{' '}
						<span className="text-amber-300">{compatibilityReport.unavailable_count}</span>
					</div>
				)}
			</div>

			{activeTab === 'catalog' && (
				<FeatureCatalogTab
					features={featureCatalog}
					compatibilityItems={compatibilityReport?.items || []}
					isLoading={isLoadingFeatures}
					canCreate={canCreate}
					canUpdateFeature={(f) => canAccessRecord('updateFeature', f.user_id)}
					canDeleteFeature={(f) => canAccessRecord('deleteFeature', f.user_id)}
					previewArtifactId={effectiveArtifactId}
					onClone={handleClone}
					onEdit={handleEdit}
					onDelete={async (f) => {
						await deleteFeature.mutateAsync(f.feature_id);
					}}
					onPreview={async (f) => {
						if (!currentProjectId || !effectiveArtifactId) return null;
						return await previewFeature.mutateAsync({
							project_id: currentProjectId,
							artifact_id: effectiveArtifactId,
							feature_id: f.feature_id,
						});
					}}
				/>
			)}

			{activeTab === 'builder' && canCreate && currentProjectId && (
				<FeatureBuilderTab
					projectId={currentProjectId}
					editingFeature={editingFeature}
					previewArtifactId={effectiveArtifactId}
					isSaving={createFeature.isPending || updateFeature.isPending}
					isPreviewing={previewFeature.isPending}
					onCancelEdit={() => setEditingFeature(null)}
					onCreate={async (payload) => {
						await createFeature.mutateAsync(payload);
					}}
					onUpdate={async (featureId, payload) => {
						await updateFeature.mutateAsync({ featureId, payload });
						setEditingFeature(null);
					}}
					onPreviewSpec={async (spec) => {
						if (!currentProjectId || !effectiveArtifactId) return null;
						return await previewFeature.mutateAsync({
							project_id: currentProjectId,
							artifact_id: effectiveArtifactId,
							feature_spec: spec,
						});
					}}
				/>
			)}

			{activeTab === 'sets' && currentProjectId && (
				<FeatureSetsTab
					projectId={currentProjectId}
					featureSets={featureSets}
					features={featureCatalog}
					isLoading={isLoadingSets}
					canCreate={canCreate}
					canDeleteSet={(fs) => canAccessRecord('deleteFeature', fs.user_id)}
					onCreateSet={async (payload) => {
						await createFeatureSet.mutateAsync(payload);
					}}
					onDeleteSet={async (featureSetId) => {
						await deleteFeatureSet.mutateAsync(featureSetId);
					}}
				/>
			)}
		</div>
	);
}
