import { useEffect, useState } from 'react';
import { Code2, Database, Play, Save, X } from 'lucide-react';
import type {
	CreateFeatureRequest,
	FeatureComputeKind,
	FeatureMegafamily,
	FeatureOutputType,
	FeaturePreviewResponse,
	FeatureResponse,
	UpdateFeatureRequest,
} from '@/types/feature';

const DEFAULT_PYTHON_TEMPLATE =
	'def compute(df, params):\n\treturn df["amount"].astype(float)\n';

interface FeatureBuilderTabProps {
	projectId: string;
	editingFeature: FeatureResponse | null;
	previewArtifactId?: string;
	isSaving: boolean;
	isPreviewing: boolean;
	onCancelEdit: () => void;
	onCreate: (payload: CreateFeatureRequest) => Promise<void>;
	onUpdate: (featureId: string, payload: UpdateFeatureRequest) => Promise<void>;
	onPreviewSpec: (spec: Record<string, unknown>) => Promise<FeaturePreviewResponse | null>;
}

export function FeatureBuilderTab({
	projectId,
	editingFeature,
	previewArtifactId,
	isSaving,
	isPreviewing,
	onCancelEdit,
	onCreate,
	onUpdate,
	onPreviewSpec,
}: FeatureBuilderTabProps) {
	const [featureKey, setFeatureKey] = useState('');
	const [displayName, setDisplayName] = useState('');
	const [description, setDescription] = useState('');
	const [megafamily, setMegafamily] = useState<FeatureMegafamily>('ORDERS');
	const [computeKind, setComputeKind] = useState<FeatureComputeKind>('VELOCITY');
	const [outputType, setOutputType] = useState<FeatureOutputType>('NUMERIC');
	const [requiredInputsText, setRequiredInputsText] = useState('user_id, timestamp');
	const [isStateful, setIsStateful] = useState(false);
	const [requiresLabel, setRequiresLabel] = useState(false);

	// Velocity config
	const [entityKey, setEntityKey] = useState('user_id');
	const [aggFn, setAggFn] = useState('COUNT');
	const [valueCol, setValueCol] = useState('');
	const [windowStr, setWindowStr] = useState('1h');

	// Expression config
	const [formula, setFormula] = useState('amount / 100.0');
	const [defaultValue, setDefaultValue] = useState('0');

	// Target rate config
	const [groupBy, setGroupBy] = useState('card_bin');
	const [smoothing, setSmoothing] = useState('10');

	// Python config
	const [sourceCode, setSourceCode] = useState(DEFAULT_PYTHON_TEMPLATE);
	const [requiredPackagesText, setRequiredPackagesText] = useState('');

	const [errorMsg, setErrorMsg] = useState<string | null>(null);
	const [successMsg, setSuccessMsg] = useState<string | null>(null);
	const [previewResult, setPreviewResult] = useState<FeaturePreviewResponse | null>(null);

	useEffect(() => {
		if (!editingFeature) return;
		setFeatureKey(editingFeature.feature_key);
		setDisplayName(editingFeature.display_name);
		setDescription(editingFeature.description || '');
		setMegafamily(editingFeature.megafamily);
		setComputeKind(editingFeature.compute_kind);
		setOutputType(editingFeature.output_type);
		setRequiredInputsText(editingFeature.required_inputs.join(', '));
		setIsStateful(editingFeature.is_stateful);
		setRequiresLabel(editingFeature.requires_label);

		const cfg = editingFeature.config_json || {};
		if (editingFeature.compute_kind === 'VELOCITY') {
			setEntityKey(String(cfg.entity_key || 'user_id'));
			setAggFn(String(cfg.agg_fn || 'COUNT'));
			setValueCol(cfg.value_col ? String(cfg.value_col) : '');
			setWindowStr(String(cfg.window || '1h'));
		} else if (editingFeature.compute_kind === 'EXPRESSION') {
			setFormula(String(cfg.formula || 'amount'));
			setDefaultValue(cfg.default_value !== undefined ? String(cfg.default_value) : '0');
		} else if (editingFeature.compute_kind === 'TARGET_RATE') {
			setGroupBy(String(cfg.group_by || 'card_bin'));
			setSmoothing(String(cfg.smoothing || 10));
		} else if (editingFeature.compute_kind === 'PYTHON_CODE') {
			setSourceCode(editingFeature.source_code || DEFAULT_PYTHON_TEMPLATE);
			const pkgs = Array.isArray(cfg.required_packages)
				? (cfg.required_packages as string[])
				: [];
			setRequiredPackagesText(pkgs.join(', '));
		}
		setErrorMsg(null);
		setSuccessMsg(null);
		setPreviewResult(null);
	}, [editingFeature]);

	const buildConfigAndCode = () => {
		if (computeKind === 'VELOCITY') {
			return {
				config_json: {
					entity_key: entityKey.trim() || 'user_id',
					agg_fn: aggFn,
					value_col: valueCol.trim() || null,
					window: windowStr.trim() || '1h',
				},
				source_code: null,
				effectiveRequiresLabel: requiresLabel,
				effectiveStateful: false,
			};
		}
		if (computeKind === 'EXPRESSION') {
			return {
				config_json: {
					formula: formula.trim(),
					default_value: Number(defaultValue) || 0,
				},
				source_code: null,
				effectiveRequiresLabel: requiresLabel,
				effectiveStateful: false,
			};
		}
		if (computeKind === 'TARGET_RATE') {
			return {
				config_json: {
					group_by: groupBy.trim() || 'card_bin',
					smoothing: Number(smoothing) || 10,
				},
				source_code: null,
				effectiveRequiresLabel: true,
				effectiveStateful: true,
			};
		}
		const pkgs = requiredPackagesText
			.split(',')
			.map((s) => s.trim())
			.filter(Boolean);
		return {
			config_json: {
				required_packages: pkgs,
				params: {},
			},
			source_code: sourceCode,
			effectiveRequiresLabel: requiresLabel,
			effectiveStateful: isStateful,
		};
	};

	const parseInputs = () =>
		requiredInputsText
			.split(',')
			.map((s) => s.trim())
			.filter(Boolean);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setErrorMsg(null);
		setSuccessMsg(null);

		if (!featureKey.trim() || !displayName.trim()) {
			setErrorMsg('Vui lòng nhập đầy đủ mã đặc trưng và tên hiển thị.');
			return;
		}

		const { config_json, source_code, effectiveRequiresLabel, effectiveStateful } =
			buildConfigAndCode();

		try {
			if (editingFeature) {
				await onUpdate(editingFeature.feature_id, {
					display_name: displayName.trim(),
					description: description.trim() || null,
					megafamily,
					output_type: outputType,
					is_stateful: effectiveStateful,
					requires_label: effectiveRequiresLabel,
					config_json,
					source_code,
					required_inputs: parseInputs(),
				});
				setSuccessMsg(`Đã cập nhật đặc trưng ${featureKey}.`);
			} else {
				await onCreate({
					project_id: projectId,
					feature_key: featureKey.trim(),
					display_name: displayName.trim(),
					description: description.trim() || null,
					megafamily,
					compute_kind: computeKind,
					output_type: outputType,
					is_stateful: effectiveStateful,
					requires_label: effectiveRequiresLabel,
					config_json,
					source_code,
					required_inputs: parseInputs(),
					status: 'ACTIVE',
				});
				setSuccessMsg(`Đã lưu đặc trưng ${featureKey}.`);
				setFeatureKey('');
				setDisplayName('');
				setDescription('');
			}
		} catch (err) {
			setErrorMsg(err instanceof Error ? err.message : 'Lưu đặc trưng thất bại.');
		}
	};

	const handlePreview = async () => {
		setErrorMsg(null);
		const { config_json, source_code, effectiveRequiresLabel, effectiveStateful } =
			buildConfigAndCode();
		try {
			const res = await onPreviewSpec({
				feature_key: featureKey.trim() || 'preview_feature',
				display_name: displayName.trim() || 'Preview',
				megafamily,
				compute_kind: computeKind,
				output_type: outputType,
				is_stateful: effectiveStateful,
				requires_label: effectiveRequiresLabel,
				config_json,
				source_code,
				required_inputs: parseInputs(),
			});
			setPreviewResult(res);
		} catch (err) {
			setErrorMsg(err instanceof Error ? err.message : 'Chạy thử Preview thất bại.');
		}
	};

	return (
		<form onSubmit={(e) => void handleSubmit(e)} className="bg-dark-900 border border-dark-800 rounded-xl p-5 space-y-5">
			<div className="flex items-center justify-between border-b border-dark-800 pb-3">
				<div>
					<h3 className="text-sm font-semibold text-slate-100">
						{editingFeature
							? `Chỉnh sửa đặc trưng: ${editingFeature.feature_key}`
							: 'Tạo đặc trưng mới (2-Tier Dynamic Builder)'}
					</h3>
					<p className="text-xs text-slate-400 mt-0.5">
						Chọn công thức SQL (DuckDB) hoặc mã Python động được kiểm tra AST trước khi lưu.
					</p>
				</div>
				{editingFeature && (
					<button
						type="button"
						onClick={onCancelEdit}
						className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-700 text-xs text-slate-300 inline-flex items-center gap-1"
					>
						<X className="w-3.5 h-3.5" />
						<span>Hủy chỉnh sửa</span>
					</button>
				)}
			</div>

			<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
				<div>
					<label htmlFor="builder-feature-key" className="block text-xs font-medium text-slate-300 mb-1">
						Mã đặc trưng
					</label>
					<input
						id="builder-feature-key"
						type="text"
						value={featureKey}
						onChange={(e) => setFeatureKey(e.target.value)}
						disabled={Boolean(editingFeature)}
						placeholder="vd: custom_vel_6h"
						className="w-full bg-dark-950 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-brand-500 disabled:opacity-50"
					/>
				</div>

				<div>
					<label htmlFor="builder-display-name" className="block text-xs font-medium text-slate-300 mb-1">
						Tên hiển thị
					</label>
					<input
						id="builder-display-name"
						type="text"
						value={displayName}
						onChange={(e) => setDisplayName(e.target.value)}
						placeholder="vd: Tần suất giao dịch 6 giờ"
						className="w-full bg-dark-950 border border-dark-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
					/>
				</div>

				<div>
					<label htmlFor="builder-megafamily" className="block text-xs font-medium text-slate-300 mb-1">
						Nhóm đặc trưng (Megafamily)
					</label>
					<select
						id="builder-megafamily"
						value={megafamily}
						onChange={(e) => setMegafamily(e.target.value as FeatureMegafamily)}
						className="w-full bg-dark-950 border border-dark-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
					>
						<option value="ORDERS">ORDERS</option>
						<option value="MONETARY">MONETARY</option>
						<option value="IDENTITY">IDENTITY</option>
						<option value="PAYMENT">PAYMENT</option>
						<option value="LOCATIONS">LOCATIONS</option>
						<option value="NETWORK">NETWORK</option>
					</select>
				</div>

				<div>
					<label htmlFor="builder-output-type" className="block text-xs font-medium text-slate-300 mb-1">
						Kiểu dữ liệu đầu ra
					</label>
					<select
						id="builder-output-type"
						value={outputType}
						onChange={(e) => setOutputType(e.target.value as FeatureOutputType)}
						className="w-full bg-dark-950 border border-dark-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
					>
						<option value="NUMERIC">NUMERIC (Số thực)</option>
						<option value="BOOLEAN">BOOLEAN (Đúng/Sai)</option>
						<option value="STRING">STRING (Chuỗi)</option>
					</select>
				</div>
			</div>

			<div>
				<label htmlFor="builder-required-inputs" className="block text-xs font-medium text-slate-300 mb-1">
					Cột đầu vào bắt buộc (phân tách bằng dấu phẩy)
				</label>
				<input
					id="builder-required-inputs"
					type="text"
					value={requiredInputsText}
					onChange={(e) => setRequiredInputsText(e.target.value)}
					placeholder="user_id, timestamp, amount"
					className="w-full bg-dark-950 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-brand-500"
				/>
			</div>

			<div className="space-y-2">
				<div className="text-xs font-medium text-slate-300">Cơ chế thực thi (Compute Kind)</div>
				<div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
					{(
						[
							{ id: 'VELOCITY', label: 'Cửa sổ trượt (Velocity)', tier: 'Tier 1 SQL' },
							{ id: 'EXPRESSION', label: 'Biểu thức (Expression)', tier: 'Tier 1 SQL' },
							{ id: 'TARGET_RATE', label: 'Tỷ lệ nhãn (Target Rate)', tier: 'Tier 1 Fit' },
							{ id: 'PYTHON_CODE', label: 'Mã Python', tier: 'Tier 2 Subprocess' },
						] as const
					).map((kind) => {
						const active = computeKind === kind.id;
						return (
							<button
								key={kind.id}
								type="button"
								disabled={Boolean(editingFeature)}
								onClick={() => setComputeKind(kind.id)}
								className={`p-2.5 rounded-lg border text-left transition ${
									active
										? 'bg-brand-500/15 border-brand-500/50 text-brand-200'
										: 'bg-dark-950 border-dark-800 text-slate-400 hover:border-dark-700'
								} disabled:opacity-50`}
							>
								<div className="flex items-center gap-1.5 text-xs font-medium">
									{kind.id === 'PYTHON_CODE' ? (
										<Code2 className="w-3.5 h-3.5 text-sky-400" />
									) : (
										<Database className="w-3.5 h-3.5 text-emerald-400" />
									)}
									<span>{kind.label}</span>
								</div>
								<div className="text-[10px] text-slate-500 mt-1">{kind.tier}</div>
							</button>
						);
					})}
				</div>
			</div>

			{computeKind === 'VELOCITY' && (
				<div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-dark-950 border border-dark-800 rounded-lg p-3.5">
					<div>
						<label className="block text-[11px] text-slate-400 mb-1">Khóa thực thể (Entity)</label>
						<input
							type="text"
							value={entityKey}
							onChange={(e) => setEntityKey(e.target.value)}
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
					<div>
						<label className="block text-[11px] text-slate-400 mb-1">Hàm tổng hợp</label>
						<select
							value={aggFn}
							onChange={(e) => setAggFn(e.target.value)}
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						>
							<option value="COUNT">COUNT</option>
							<option value="SUM">SUM</option>
							<option value="MEAN">MEAN</option>
							<option value="MAX">MAX</option>
							<option value="MIN">MIN</option>
							<option value="STD">STD</option>
						</select>
					</div>
					<div>
						<label className="block text-[11px] text-slate-400 mb-1">Cột giá trị (nếu khác COUNT)</label>
						<input
							type="text"
							value={valueCol}
							onChange={(e) => setValueCol(e.target.value)}
							placeholder="amount"
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
					<div>
						<label className="block text-[11px] text-slate-400 mb-1">Cửa sổ thời gian</label>
						<input
							type="text"
							value={windowStr}
							onChange={(e) => setWindowStr(e.target.value)}
							placeholder="1h, 24h, 7d"
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
				</div>
			)}

			{computeKind === 'EXPRESSION' && (
				<div className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-dark-950 border border-dark-800 rounded-lg p-3.5">
					<div className="md:col-span-2">
						<label className="block text-[11px] text-slate-400 mb-1">Công thức toán học</label>
						<input
							type="text"
							value={formula}
							onChange={(e) => setFormula(e.target.value)}
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
					<div>
						<label className="block text-[11px] text-slate-400 mb-1">Giá trị mặc định (khi Null/0)</label>
						<input
							type="number"
							value={defaultValue}
							onChange={(e) => setDefaultValue(e.target.value)}
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
				</div>
			)}

			{computeKind === 'TARGET_RATE' && (
				<div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-dark-950 border border-dark-800 rounded-lg p-3.5">
					<div>
						<label className="block text-[11px] text-slate-400 mb-1">Nhóm theo cột (group_by)</label>
						<input
							type="text"
							value={groupBy}
							onChange={(e) => setGroupBy(e.target.value)}
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
					<div>
						<label className="block text-[11px] text-slate-400 mb-1">Hệ số làm mượt Laplace (smoothing)</label>
						<input
							type="number"
							value={smoothing}
							onChange={(e) => setSmoothing(e.target.value)}
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>
				</div>
			)}

			{computeKind === 'PYTHON_CODE' && (
				<div className="space-y-3 bg-dark-950 border border-dark-800 rounded-lg p-3.5">
					<div className="flex flex-wrap items-center gap-4 text-xs">
						<label className="inline-flex items-center gap-2 text-slate-300 cursor-pointer">
							<input
								type="checkbox"
								checked={isStateful}
								onChange={(e) => setIsStateful(e.target.checked)}
								className="rounded border-dark-700 bg-dark-900 text-brand-500"
							/>
							<span>Stateful (yêu cầu fit(train_df, params))</span>
						</label>
						<label className="inline-flex items-center gap-2 text-slate-300 cursor-pointer">
							<input
								type="checkbox"
								checked={requiresLabel}
								onChange={(e) => setRequiresLabel(e.target.checked)}
								className="rounded border-dark-700 bg-dark-900 text-brand-500"
							/>
							<span>Cần cột nhãn (chỉ dùng cho Training, cảnh báo khi chạy Rule-only)</span>
						</label>
					</div>

					<div>
						<label className="block text-[11px] text-slate-400 mb-1">
							Thư viện bên ngoài phụ thuộc (nếu có, phân tách dấu phẩy)
						</label>
						<input
							type="text"
							value={requiredPackagesText}
							onChange={(e) => setRequiredPackagesText(e.target.value)}
							placeholder="pandas, numpy"
							className="w-full bg-dark-900 border border-dark-700 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100"
						/>
					</div>

					<div>
						<label htmlFor="builder-source-code" className="block text-[11px] text-slate-400 mb-1">
							Mã nguồn Python (hàm compute(df, params) -&gt; Series)
						</label>
						<textarea
							id="builder-source-code"
							rows={7}
							value={sourceCode}
							onChange={(e) => setSourceCode(e.target.value)}
							className="w-full bg-dark-900 border border-dark-700 rounded-lg p-3 text-xs font-mono text-sky-300 focus:outline-none focus:border-brand-500"
						/>
					</div>
				</div>
			)}

			{errorMsg && (
				<div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">
					{errorMsg}
				</div>
			)}

			{successMsg && (
				<div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300">
					{successMsg}
				</div>
			)}

			{previewResult && (
				<div className="bg-dark-950 border border-dark-800 rounded-lg p-3 space-y-2">
					<div className="flex items-center justify-between text-xs text-slate-400">
						<span>Preview kết quả ({previewResult.execution_time_ms} ms)</span>
						<span className="font-mono text-brand-300">{previewResult.output_type}</span>
					</div>
					<pre className="text-[11px] font-mono text-slate-300 overflow-x-auto max-h-44">
						{JSON.stringify(previewResult.sample_rows.slice(0, 5), null, 2)}
					</pre>
				</div>
			)}

			<div className="flex items-center justify-end gap-2 pt-2 border-t border-dark-800">
				{previewArtifactId && (
					<button
						type="button"
						disabled={isPreviewing}
						onClick={() => void handlePreview()}
						className="px-3.5 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-xs font-medium text-slate-200 inline-flex items-center gap-1.5 transition"
					>
						<Play className="w-3.5 h-3.5 text-brand-400" />
						<span>{isPreviewing ? 'Đang chạy thử...' : 'Chạy thử Preview'}</span>
					</button>
				)}
				<button
					type="submit"
					disabled={isSaving}
					className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white inline-flex items-center gap-1.5 transition disabled:opacity-50"
				>
					<Save className="w-3.5 h-3.5" />
					<span>{isSaving ? 'Đang lưu...' : 'Lưu đặc trưng'}</span>
				</button>
			</div>
		</form>
	);
}
