import { useMemo, useState } from 'react';
import {
	AlertCircle,
	AlertTriangle,
	CheckCircle2,
	Code2,
	Copy,
	Database,
	Edit3,
	Play,
	Search,
	Trash2,
} from 'lucide-react';
import type {
	FeatureCompatibilityItem,
	FeatureMegafamily,
	FeaturePreviewResponse,
	FeatureResponse,
} from '@/types/feature';

const MEGAFAMILIES: Array<{ value: 'ALL' | FeatureMegafamily; label: string }> = [
	{ value: 'ALL', label: 'Tất cả' },
	{ value: 'ORDERS', label: 'ORDERS' },
	{ value: 'MONETARY', label: 'MONETARY' },
	{ value: 'IDENTITY', label: 'IDENTITY' },
	{ value: 'PAYMENT', label: 'PAYMENT' },
	{ value: 'LOCATIONS', label: 'LOCATIONS' },
	{ value: 'NETWORK', label: 'NETWORK' },
];

interface FeatureCatalogTabProps {
	features: FeatureResponse[];
	compatibilityItems: FeatureCompatibilityItem[];
	isLoading: boolean;
	search?: string;
	onSearchChange?: (val: string) => void;
	megafamily?: 'ALL' | FeatureMegafamily;
	onMegafamilyChange?: (val: 'ALL' | FeatureMegafamily) => void;
	originFilter?: 'ALL' | 'BUILTIN' | 'CUSTOM';
	onOriginFilterChange?: (val: 'ALL' | 'BUILTIN' | 'CUSTOM') => void;
	hasNextPage?: boolean;
	isFetchingNextPage?: boolean;
	onLoadMore?: () => void;
	canCreate: boolean;
	canUpdateFeature: (f: FeatureResponse) => boolean;
	canDeleteFeature: (f: FeatureResponse) => boolean;
	previewArtifactId?: string;
	onClone: (f: FeatureResponse) => Promise<void>;
	onEdit: (f: FeatureResponse) => void;
	onDelete: (f: FeatureResponse) => Promise<void>;
	onPreview: (f: FeatureResponse) => Promise<FeaturePreviewResponse | null>;
}

export function FeatureCatalogTab({
	features,
	compatibilityItems,
	isLoading,
	search: controlledSearch,
	onSearchChange,
	megafamily: controlledMegafamily,
	onMegafamilyChange,
	originFilter: controlledOriginFilter,
	onOriginFilterChange,
	hasNextPage = false,
	isFetchingNextPage = false,
	onLoadMore,
	canCreate,
	canUpdateFeature,
	canDeleteFeature,
	previewArtifactId,
	onClone,
	onEdit,
	onDelete,
	onPreview,
}: FeatureCatalogTabProps) {
	const [internalSearch, setInternalSearch] = useState('');
	const [internalMegafamily, setInternalMegafamily] = useState<'ALL' | FeatureMegafamily>('ALL');
	const [internalOriginFilter, setInternalOriginFilter] = useState<'ALL' | 'BUILTIN' | 'CUSTOM'>('ALL');
	const search = controlledSearch ?? internalSearch;
	const megafamily = controlledMegafamily ?? internalMegafamily;
	const originFilter = controlledOriginFilter ?? internalOriginFilter;
	const setSearch = onSearchChange ?? setInternalSearch;
	const setMegafamily = onMegafamilyChange ?? setInternalMegafamily;
	const setOriginFilter = onOriginFilterChange ?? setInternalOriginFilter;
	const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(null);
	const [previewResult, setPreviewResult] = useState<FeaturePreviewResponse | null>(null);
	const [actionError, setActionError] = useState<string | null>(null);

	const compatById = useMemo(() => {
		const map = new Map<string, FeatureCompatibilityItem>();
		for (const item of compatibilityItems) {
			map.set(item.feature_id, item);
		}
		return map;
	}, [compatibilityItems]);

	const filteredFeatures = useMemo(() => {
		const q = search.trim().toLowerCase();
		return features.filter((f) => {
			if (megafamily !== 'ALL' && f.megafamily !== megafamily) return false;
			if (originFilter === 'BUILTIN' && !f.is_builtin) return false;
			if (originFilter === 'CUSTOM' && f.is_builtin) return false;
			if (!q) return true;
			return (
				f.feature_key.toLowerCase().includes(q) ||
				f.display_name.toLowerCase().includes(q) ||
				(f.description || '').toLowerCase().includes(q)
			);
		});
	}, [features, search, megafamily, originFilter]);

	const selectedFeature = useMemo(
		() => features.find((f) => f.feature_id === selectedFeatureId) || null,
		[features, selectedFeatureId]
	);

	const renderCompatibilityBadge = (featureId: string) => {
		const compat = compatById.get(featureId);
		if (!compat) {
			return (
				<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-slate-800 text-slate-400 border border-slate-700">
					Chưa kiểm tra
				</span>
			);
		}
		if (compat.status === 'AVAILABLE') {
			return (
				<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
					<CheckCircle2 className="w-3 h-3" />
					<span>Khả dụng</span>
				</span>
			);
		}
		if (compat.status === 'MISSING_INPUTS') {
			return (
				<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-amber-500/10 text-amber-300 border border-amber-500/30">
					<AlertTriangle className="w-3 h-3" />
					<span>Thiếu cột: {compat.missing_inputs.join(', ')}</span>
				</span>
			);
		}
		if (compat.missing_packages.length > 0) {
			return (
				<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-rose-500/10 text-rose-300 border border-rose-500/30">
					<AlertCircle className="w-3 h-3" />
					<span>Thiếu thư viện: {compat.missing_packages.join(', ')}</span>
				</span>
			);
		}
		return (
			<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-rose-500/10 text-rose-300 border border-rose-500/30">
				<AlertCircle className="w-3 h-3" />
				<span>Thiếu phụ thuộc</span>
			</span>
		);
	};

	const handleRunPreview = async (f: FeatureResponse) => {
		setActionError(null);
		try {
			const result = await onPreview(f);
			setPreviewResult(result);
		} catch (err) {
			setActionError(err instanceof Error ? err.message : 'Chạy thử Preview thất bại.');
		}
	};

	return (
		<div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
			<div className="xl:col-span-2 space-y-3">
				<div className="flex flex-wrap items-center gap-2 bg-dark-900 border border-dark-800 rounded-xl p-3">
					<div className="relative flex-1 min-w-[200px]">
						<Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
						<input
							type="text"
							value={search}
							onChange={(e) => setSearch(e.target.value)}
							placeholder="Tìm theo mã đặc trưng, tên hiển thị..."
							className="w-full bg-dark-950 border border-dark-700 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500"
						/>
					</div>

					<select
						value={originFilter}
						onChange={(e) => setOriginFilter(e.target.value as 'ALL' | 'BUILTIN' | 'CUSTOM')}
						aria-label="Lọc nguồn đặc trưng"
						className="bg-dark-950 border border-dark-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
					>
						<option value="ALL">Tất cả nguồn</option>
						<option value="BUILTIN">Hệ thống (Built-in)</option>
						<option value="CUSTOM">Tùy chỉnh (Custom)</option>
					</select>
				</div>

				<div className="flex flex-wrap gap-1.5">
					{MEGAFAMILIES.map((mf) => {
						const active = megafamily === mf.value;
						return (
							<button
								key={mf.value}
								type="button"
								onClick={() => setMegafamily(mf.value)}
								className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition ${
									active
										? 'bg-brand-500/15 text-brand-300 border-brand-500/40'
										: 'bg-dark-900 text-slate-400 border-dark-800 hover:text-slate-200'
								}`}
							>
								{mf.label}
							</button>
						);
					})}
				</div>

				<div className="bg-dark-900 border border-dark-800 rounded-xl overflow-hidden">
					{isLoading ? (
						<div className="p-8 text-center text-xs text-slate-400">
							Đang tải danh mục đặc trưng...
						</div>
					) : filteredFeatures.length === 0 ? (
						<div className="p-8 text-center text-xs text-slate-400">
							Không có đặc trưng nào phù hợp bộ lọc.
						</div>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-left border-collapse">
								<thead>
									<tr className="border-b border-dark-800 bg-dark-950/60 text-[11px] uppercase tracking-wider text-slate-400">
										<th className="py-2.5 px-3">Mã / Tên đặc trưng</th>
										<th className="py-2.5 px-3">Nhóm</th>
										<th className="py-2.5 px-3">Thực thi</th>
										<th className="py-2.5 px-3">Tương thích</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800/70 text-xs">
									{filteredFeatures.map((item) => {
										const isSelected = selectedFeatureId === item.feature_id;
										return (
											<tr
												key={item.feature_id}
												onClick={() => {
													setSelectedFeatureId(item.feature_id);
													setPreviewResult(null);
													setActionError(null);
												}}
												className={`cursor-pointer transition ${
													isSelected ? 'bg-brand-500/10' : 'hover:bg-dark-800/50'
												}`}
											>
												<td className="py-2.5 px-3">
													<div className="flex items-center gap-2">
														<span className="font-mono font-semibold text-slate-100">
															{item.feature_key}
														</span>
														<span
															className={`px-1.5 py-0.5 rounded text-[10px] border ${
																item.is_builtin
																	? 'bg-slate-800 text-slate-300 border-slate-700'
																	: 'bg-brand-500/10 text-brand-300 border-brand-500/30'
															}`}
														>
															{item.is_builtin ? 'Built-in' : 'Custom'}
														</span>
														{item.requires_label && (
															<span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30">
																Cần nhãn
															</span>
														)}
													</div>
													<div className="text-slate-400 mt-0.5">{item.display_name}</div>
												</td>
												<td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">
													{item.megafamily}
												</td>
												<td className="py-2.5 px-3">
													<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-dark-950 border border-dark-700 font-mono text-[11px] text-slate-300">
														{item.compute_kind === 'PYTHON_CODE' ? (
															<Code2 className="w-3 h-3 text-sky-400" />
														) : (
															<Database className="w-3 h-3 text-emerald-400" />
														)}
														<span>{item.compute_kind}</span>
													</span>
												</td>
												<td className="py-2.5 px-3">{renderCompatibilityBadge(item.feature_id)}</td>
											</tr>
										);
									})}
								</tbody>
							</table>
						</div>
					)}
					{hasNextPage && onLoadMore && (
						<div className="p-3 border-t border-dark-800 flex justify-center bg-dark-950/40">
							<button
								type="button"
								disabled={isFetchingNextPage}
								onClick={onLoadMore}
								className="px-4 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-xs text-slate-200 font-medium disabled:opacity-50"
							>
								{isFetchingNextPage ? 'Đang tải...' : 'Tải thêm'}
							</button>
						</div>
					)}
				</div>
			</div>

			<div className="bg-dark-900 border border-dark-800 rounded-xl p-4 space-y-4 h-fit">
				{!selectedFeature ? (
					<div className="text-xs text-slate-400 py-8 text-center">
						Chọn một đặc trưng để xem logic thực thi, cột phụ thuộc và thao tác.
					</div>
				) : (
					<>
						<div className="flex items-start justify-between gap-2 border-b border-dark-800 pb-3">
							<div>
								<div className="font-mono text-sm font-semibold text-slate-100">
									{selectedFeature.feature_key}
								</div>
								<div className="text-xs text-slate-400 mt-0.5">
									{selectedFeature.display_name}
								</div>
							</div>
							{renderCompatibilityBadge(selectedFeature.feature_id)}
						</div>

						{selectedFeature.description && (
							<p className="text-xs text-slate-300 leading-relaxed">
								{selectedFeature.description}
							</p>
						)}

						<div className="grid grid-cols-2 gap-2 text-xs">
							<div className="bg-dark-950 border border-dark-800 rounded-lg p-2">
								<div className="text-[11px] text-slate-500">Kiểu đầu ra</div>
								<div className="font-mono text-slate-200 mt-0.5">
									{selectedFeature.output_type}
								</div>
							</div>
							<div className="bg-dark-950 border border-dark-800 rounded-lg p-2">
								<div className="text-[11px] text-slate-500">Stateful / Nhãn</div>
								<div className="text-slate-200 mt-0.5">
									{selectedFeature.is_stateful ? 'Có Fit' : 'Stateless'} •{' '}
									{selectedFeature.requires_label ? 'Cần nhãn' : 'Không nhãn'}
								</div>
							</div>
						</div>

						<div>
							<div className="text-[11px] font-medium text-slate-400 mb-1">
								Cột đầu vào bắt buộc ({selectedFeature.required_inputs.length})
							</div>
							<div className="flex flex-wrap gap-1.5">
								{selectedFeature.required_inputs.length === 0 ? (
									<span className="text-xs text-slate-500">Không có</span>
								) : (
									selectedFeature.required_inputs.map((col) => (
										<span
											key={col}
											className="px-2 py-0.5 rounded bg-dark-950 border border-dark-700 font-mono text-[11px] text-slate-300"
										>
											{col}
										</span>
									))
								)}
							</div>
						</div>

						{selectedFeature.compiled_sql_preview && (
							<div>
								<div className="text-[11px] font-medium text-slate-400 mb-1">
									DuckDB SQL biên dịch
								</div>
								<pre className="bg-dark-950 border border-dark-800 rounded-lg p-2.5 text-[11px] font-mono text-emerald-300 overflow-x-auto whitespace-pre-wrap">
									{selectedFeature.compiled_sql_preview}
								</pre>
							</div>
						)}

						{selectedFeature.source_code && (
							<div>
								<div className="text-[11px] font-medium text-slate-400 mb-1">
									Mã nguồn Python (Dynamic Script)
								</div>
								<pre className="bg-dark-950 border border-dark-800 rounded-lg p-2.5 text-[11px] font-mono text-sky-300 overflow-x-auto whitespace-pre">
									{selectedFeature.source_code}
								</pre>
							</div>
						)}

						{actionError && (
							<div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">
								{actionError}
							</div>
						)}

						{previewResult && (
							<div className="space-y-2 bg-dark-950 border border-dark-800 rounded-lg p-2.5">
								<div className="flex items-center justify-between text-[11px] text-slate-400">
									<span>Kết quả Preview ({previewResult.sample_rows.length} dòng)</span>
									<span className="font-mono">{previewResult.execution_time_ms} ms</span>
								</div>
								<pre className="text-[11px] font-mono text-slate-300 overflow-x-auto max-h-40">
									{JSON.stringify(previewResult.sample_rows.slice(0, 5), null, 2)}
								</pre>
							</div>
						)}

						<div className="flex flex-wrap gap-2 pt-2 border-t border-dark-800">
							{canCreate && (
								<button
									type="button"
									onClick={() => void onClone(selectedFeature)}
									className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-xs text-slate-200 inline-flex items-center gap-1.5 transition"
								>
									<Copy className="w-3.5 h-3.5" />
									<span>Clone & Sửa</span>
								</button>
							)}
							{previewArtifactId && (
								<button
									type="button"
									onClick={() => void handleRunPreview(selectedFeature)}
									className="px-3 py-1.5 rounded-lg bg-brand-600/20 hover:bg-brand-600/30 border border-brand-500/40 text-xs text-brand-300 inline-flex items-center gap-1.5 transition"
								>
									<Play className="w-3.5 h-3.5" />
									<span>Chạy thử Preview</span>
								</button>
							)}
							{!selectedFeature.is_builtin && canUpdateFeature(selectedFeature) && (
								<button
									type="button"
									onClick={() => onEdit(selectedFeature)}
									className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-xs text-slate-200 inline-flex items-center gap-1.5 transition"
								>
									<Edit3 className="w-3.5 h-3.5" />
									<span>Chỉnh sửa</span>
								</button>
							)}
							{!selectedFeature.is_builtin && canDeleteFeature(selectedFeature) && (
								<button
									type="button"
									onClick={() => void onDelete(selectedFeature)}
									className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-xs text-rose-300 inline-flex items-center gap-1.5 transition"
								>
									<Trash2 className="w-3.5 h-3.5" />
									<span>Xóa</span>
								</button>
							)}
						</div>
					</>
				)}
			</div>
		</div>
	);
}
