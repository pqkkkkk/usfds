import { useMemo, useState } from 'react';
import { Layers, Plus, Trash2 } from 'lucide-react';
import type {
	CreateFeatureSetRequest,
	FeatureResponse,
	FeatureSetResponse,
} from '@/types/feature';

interface FeatureSetsTabProps {
	projectId: string;
	featureSets: FeatureSetResponse[];
	features: FeatureResponse[];
	isLoading: boolean;
	canCreate: boolean;
	canDeleteSet: (fs: FeatureSetResponse) => boolean;
	onCreateSet: (payload: CreateFeatureSetRequest) => Promise<void>;
	onDeleteSet: (featureSetId: string) => Promise<void>;
}

export function FeatureSetsTab({
	projectId,
	featureSets,
	features,
	isLoading,
	canCreate,
	canDeleteSet,
	onCreateSet,
	onDeleteSet,
}: FeatureSetsTabProps) {
	const [showCreateForm, setShowCreateForm] = useState(false);
	const [setKey, setSetKey] = useState('');
	const [name, setName] = useState('');
	const [domainTag, setDomainTag] = useState('CUSTOM');
	const [description, setDescription] = useState('');
	const [selectedFeatureIds, setSelectedFeatureIds] = useState<string[]>([]);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);

	const featureById = useMemo(() => {
		const map = new Map<string, FeatureResponse>();
		for (const f of features) {
			map.set(f.feature_id, f);
		}
		return map;
	}, [features]);

	const toggleFeatureId = (featureId: string) => {
		setSelectedFeatureIds((prev) =>
			prev.includes(featureId) ? prev.filter((id) => id !== featureId) : [...prev, featureId]
		);
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setErrorMsg(null);
		if (!setKey.trim() || !name.trim()) {
			setErrorMsg('Vui lòng nhập mã gói và tên gói đặc trưng.');
			return;
		}
		try {
			await onCreateSet({
				project_id: projectId,
				set_key: setKey.trim(),
				name: name.trim(),
				domain_tag: domainTag.trim() || 'CUSTOM',
				description: description.trim() || null,
				feature_ids: selectedFeatureIds,
			});
			setSetKey('');
			setName('');
			setDescription('');
			setSelectedFeatureIds([]);
			setShowCreateForm(false);
		} catch (err) {
			setErrorMsg(err instanceof Error ? err.message : 'Không thể tạo gói đặc trưng.');
		}
	};

	return (
		<div className="space-y-4">
			<div className="flex items-center justify-between">
				<div>
					<h3 className="text-sm font-semibold text-slate-100">
						Gói đặc trưng theo miền nghiệp vụ (Feature Sets)
					</h3>
					<p className="text-xs text-slate-400">
						Gồm 5 gói chuẩn hệ thống và các gói tùy chỉnh cho dự án hiện tại.
					</p>
				</div>
				{canCreate && (
					<button
						type="button"
						onClick={() => setShowCreateForm((v) => !v)}
						className="px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-medium text-white inline-flex items-center gap-1.5 transition"
					>
						<Plus className="w-3.5 h-3.5" />
						<span>{showCreateForm ? 'Đóng biểu mẫu' : 'Tạo gói đặc trưng'}</span>
					</button>
				)}
			</div>

			{showCreateForm && canCreate && (
				<form
					onSubmit={(e) => void handleSubmit(e)}
					className="bg-dark-900 border border-dark-800 rounded-xl p-4 space-y-3"
				>
					<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
						<div>
							<label className="block text-xs text-slate-300 mb-1">Mã gói (set_key)</label>
							<input
								type="text"
								value={setKey}
								onChange={(e) => setSetKey(e.target.value)}
								placeholder="vd: pkg_custom_v1"
								className="w-full bg-dark-950 border border-dark-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-100"
							/>
						</div>
						<div>
							<label className="block text-xs text-slate-300 mb-1">Tên gói</label>
							<input
								type="text"
								value={name}
								onChange={(e) => setName(e.target.value)}
								placeholder="Gói đặc trưng dự án"
								className="w-full bg-dark-950 border border-dark-700 rounded-lg px-3 py-1.5 text-xs text-slate-100"
							/>
						</div>
						<div>
							<label className="block text-xs text-slate-300 mb-1">Thẻ domain</label>
							<input
								type="text"
								value={domainTag}
								onChange={(e) => setDomainTag(e.target.value)}
								className="w-full bg-dark-950 border border-dark-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-100"
							/>
						</div>
					</div>

					<div>
						<label className="block text-xs text-slate-300 mb-1">
							Chọn đặc trưng trong gói ({selectedFeatureIds.length} đã chọn)
						</label>
						<div className="max-h-40 overflow-y-auto bg-dark-950 border border-dark-800 rounded-lg p-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
							{features.map((f) => (
								<label
									key={f.feature_id}
									className="flex items-center gap-2 px-2 py-1 rounded hover:bg-dark-900 text-xs text-slate-300 cursor-pointer"
								>
									<input
										type="checkbox"
										checked={selectedFeatureIds.includes(f.feature_id)}
										onChange={() => toggleFeatureId(f.feature_id)}
									/>
									<span className="font-mono truncate">{f.feature_key}</span>
								</label>
							))}
						</div>
					</div>

					{errorMsg && (
						<div className="text-xs text-rose-300 bg-rose-500/10 border border-rose-500/30 rounded-lg p-2">
							{errorMsg}
						</div>
					)}

					<div className="flex justify-end">
						<button
							type="submit"
							className="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white"
						>
							Lưu gói đặc trưng
						</button>
					</div>
				</form>
			)}

			{isLoading ? (
				<div className="p-8 text-center text-xs text-slate-400 bg-dark-900 border border-dark-800 rounded-xl">
					Đang tải danh sách gói đặc trưng...
				</div>
			) : (
				<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
					{featureSets.map((fs) => (
						<div
							key={fs.feature_set_id}
							className="bg-dark-900 border border-dark-800 rounded-xl p-4 space-y-3"
						>
							<div className="flex items-start justify-between gap-2">
								<div>
									<div className="flex items-center gap-2">
										<Layers className="w-4 h-4 text-brand-400" />
										<span className="font-mono text-xs font-semibold text-slate-100">
											{fs.set_key}
										</span>
										<span className="px-1.5 py-0.5 rounded text-[10px] bg-dark-950 border border-dark-700 text-slate-300 font-mono">
											{fs.domain_tag}
										</span>
										<span
											className={`px-1.5 py-0.5 rounded text-[10px] border ${
												fs.is_builtin
													? 'bg-slate-800 text-slate-300 border-slate-700'
													: 'bg-brand-500/10 text-brand-300 border-brand-500/30'
											}`}
										>
											{fs.is_builtin ? 'Built-in' : 'Custom'}
										</span>
									</div>
									<h4 className="text-sm font-medium text-slate-200 mt-1">{fs.name}</h4>
								</div>
								{!fs.is_builtin && canDeleteSet(fs) && (
									<button
										type="button"
										onClick={() => void onDeleteSet(fs.feature_set_id)}
										className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30"
										title="Xóa gói đặc trưng"
									>
										<Trash2 className="w-3.5 h-3.5" />
									</button>
								)}
							</div>

							{fs.description && (
								<p className="text-xs text-slate-400">{fs.description}</p>
							)}

							<div className="flex flex-wrap gap-1.5 pt-1">
								{fs.feature_ids.map((fid) => {
									const f = featureById.get(fid);
									return (
										<span
											key={fid}
											className="px-2 py-0.5 rounded bg-dark-950 border border-dark-800 font-mono text-[11px] text-slate-300"
										>
											{f ? f.feature_key : fid}
										</span>
									);
								})}
							</div>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
