import React, { useRef, useState } from 'react';
import {
	UploadCloud,
	FolderOpen,
	FileArchive,
	X,
	ShieldAlert,
	ShieldCheck,
	Loader2,
	Code2,
	ChevronDown,
	ChevronRight,
} from 'lucide-react';
import { trainingApi } from '../../../api/trainingApi';
import type {
	DataFormat,
	DataModality,
	ModelFramework,
	ModelPluginManifest,
	ModelResponse,
} from '../../../types/model';

interface ImportCustomModelModalProps {
	isOpen: boolean;
	projectId?: string;
	onClose: () => void;
	onSuccess: (model: ModelResponse) => void;
}

type SourceMode = 'upload_zip' | 'local_path';

export const ImportCustomModelModal: React.FC<ImportCustomModelModalProps> = ({
	isOpen,
	projectId,
	onClose,
	onSuccess,
}) => {
	const [sourceMode, setSourceMode] = useState<SourceMode>('upload_zip');
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const [localPath, setLocalPath] = useState<string>('');
	const [enableManifestOverride, setEnableManifestOverride] = useState<boolean>(false);

	// Manifest override fields
	const [modelName, setModelName] = useState<string>('');
	const [displayName, setDisplayName] = useState<string>('');
	const [description, setDescription] = useState<string>('');
	const [framework, setFramework] = useState<ModelFramework>('scikit-learn');
	const [dataModality, setDataModality] = useState<DataModality>('tabular');
	const [dataFormat, setDataFormat] = useState<DataFormat>('parquet');
	const [defaultHyperparamsJson, setDefaultHyperparamsJson] = useState<string>('{\n\t"C": 1.0,\n\t"max_iter": 200\n}');
	const [hyperparamSchemaJson, setHyperparamSchemaJson] = useState<string>(
		'{\n\t"C": { "type": "float", "min": 0.001, "max": 100.0 },\n\t"max_iter": { "type": "int", "min": 10, "max": 2000 }\n}'
	);

	const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);
	const fileInputRef = useRef<HTMLInputElement | null>(null);

	if (!isOpen) {
		return null;
	}

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const f = e.target.files?.[0];
		if (!f) {
			return;
		}
		if (!f.name.toLowerCase().endsWith('.zip')) {
			setErrorMsg('Gói mô hình tải lên phải có định dạng nén .zip.');
			return;
		}
		setSelectedFile(f);
		setErrorMsg(null);
	};

	const handleBrowseLocalFile = async () => {
		const electronApi = (window as any).electronAPI;
		if (electronApi?.openFileDialog) {
			try {
				const selected = await electronApi.openFileDialog({
					filters: [{ name: 'Model Plugin (.zip)', extensions: ['zip'] }],
				});
				if (selected) {
					setLocalPath(selected);
					setErrorMsg(null);
				}
			} catch {
				// Ignore cancellation
			}
		}
	};

	const buildManifestOverride = (): ModelPluginManifest | undefined => {
		if (!enableManifestOverride) {
			return undefined;
		}
		const trimmedModelName = modelName.trim();
		if (!trimmedModelName) {
			throw new Error('Khi bật Manifest Override, trường model_name là bắt buộc.');
		}
		let parsedDefaults: Record<string, any> = {};
		let parsedSchema: Record<string, any> = {};
		try {
			if (defaultHyperparamsJson.trim()) {
				parsedDefaults = JSON.parse(defaultHyperparamsJson);
			}
		} catch {
			throw new Error('JSON của default_hyperparameters không hợp lệ.');
		}
		try {
			if (hyperparamSchemaJson.trim()) {
				parsedSchema = JSON.parse(hyperparamSchemaJson);
			}
		} catch {
			throw new Error('JSON của hyperparameter_schema không hợp lệ.');
		}

		return {
			model_name: trimmedModelName,
			display_name: displayName.trim() || trimmedModelName,
			description: description.trim() || undefined,
			framework: framework as any,
			data_modality: dataModality,
			data_format: dataFormat,
			default_hyperparameters: parsedDefaults,
			hyperparameter_schema: parsedSchema,
		};
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setErrorMsg(null);

		let manifestOverride: ModelPluginManifest | undefined;
		try {
			manifestOverride = buildManifestOverride();
		} catch (err: any) {
			setErrorMsg(err.message);
			return;
		}

		if (sourceMode === 'upload_zip' && !selectedFile) {
			setErrorMsg('Vui lòng chọn tệp .zip chứa mã nguồn plugin mô hình.');
			return;
		}
		if (sourceMode === 'local_path' && !localPath.trim()) {
			setErrorMsg('Vui lòng nhập đường dẫn tới thư mục hoặc tệp .zip của plugin.');
			return;
		}

		setIsSubmitting(true);
		try {
			let res;
			if (sourceMode === 'upload_zip' && selectedFile) {
				res = await trainingApi.uploadPluggedModelZip({
					file: selectedFile,
					projectId,
					manifestOverride,
				});
			} else {
				res = await trainingApi.registerPluggedModel({
					model_artifact_path: localPath.trim(),
					project_id: projectId,
					manifest_override: manifestOverride,
				});
			}

			if (!res.success || !res.data) {
				setErrorMsg(res.error || 'Kiểm định hoặc đăng ký Custom Model Plugin thất bại.');
				return;
			}

			onSuccess(res.data);
			onClose();
		} catch (err: any) {
			setErrorMsg(err?.message || 'Lỗi khi đăng ký Custom Model Plugin.');
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div
			className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
			role="dialog"
			aria-modal="true"
			aria-labelledby="import-plugin-modal-title"
		>
			<div className="w-full max-w-2xl bg-dark-900 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
				{/* Header */}
				<div className="flex items-start justify-between p-5 border-b border-dark-800 bg-dark-950/60">
					<div className="flex items-center gap-3">
						<div className="w-9 h-9 rounded-xl bg-brand-500/15 border border-brand-500/30 flex items-center justify-center text-brand-400">
							<Code2 className="w-4 h-4" />
						</div>
						<div>
							<h2 id="import-plugin-modal-title" className="text-sm font-bold text-slate-100">
								Import Custom Model Plugin (SUC-17)
							</h2>
							<p className="text-[11px] text-slate-400 mt-0.5">
								Tích hợp thuật toán học máy tùy chỉnh qua kiểm định 2 giai đoạn (Static AST + Dynamic Dry-Run)
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						aria-label="Đóng hộp thoại"
						className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
					>
						<X className="w-4 h-4" />
					</button>
				</div>

				{/* Form Body */}
				<form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-4">
					{errorMsg && (
						<div
							role="alert"
							className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2.5 whitespace-pre-wrap"
						>
							<ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
							<span>{errorMsg}</span>
						</div>
					)}

					{/* Source Mode Selector */}
					<div>
						<label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
							Phương thức nạp gói mã nguồn (Source Method)
						</label>
						<div className="grid grid-cols-2 gap-2.5">
							<button
								type="button"
								onClick={() => {
									setSourceMode('upload_zip');
									setErrorMsg(null);
								}}
								className={`p-3 rounded-xl border text-left flex items-center gap-2.5 transition ${
									sourceMode === 'upload_zip'
										? 'bg-brand-500/15 border-brand-500/40 text-brand-300'
										: 'bg-dark-950 border-dark-800 text-slate-400 hover:text-slate-200'
								}`}
							>
								<UploadCloud className="w-4 h-4 shrink-0" />
								<div>
									<div className="text-xs font-bold">Upload .zip Archive</div>
									<div className="text-[10px] opacity-80">Tải tệp .zip trực tiếp từ trình duyệt</div>
								</div>
							</button>

							<button
								type="button"
								onClick={() => {
									setSourceMode('local_path');
									setErrorMsg(null);
								}}
								className={`p-3 rounded-xl border text-left flex items-center gap-2.5 transition ${
									sourceMode === 'local_path'
										? 'bg-brand-500/15 border-brand-500/40 text-brand-300'
										: 'bg-dark-950 border-dark-800 text-slate-400 hover:text-slate-200'
								}`}
							>
								<FolderOpen className="w-4 h-4 shrink-0" />
								<div>
									<div className="text-xs font-bold">Local Directory / Path</div>
									<div className="text-[10px] opacity-80">Trỏ đường dẫn thư mục hoặc .zip cục bộ</div>
								</div>
							</button>
						</div>
					</div>

					{/* Source Input */}
					{sourceMode === 'upload_zip' ? (
						<div>
							<input
								ref={fileInputRef}
								type="file"
								accept=".zip"
								onChange={handleFileChange}
								className="hidden"
							/>
							<div
								onClick={() => fileInputRef.current?.click()}
								className="p-5 rounded-xl border-2 border-dashed border-dark-700 hover:border-brand-500/60 bg-dark-950/60 cursor-pointer transition text-center space-y-2"
							>
								<FileArchive className="w-7 h-7 text-brand-400 mx-auto" />
								{selectedFile ? (
									<div>
										<p className="text-xs font-semibold text-emerald-400 font-mono">
											{selectedFile.name}
										</p>
										<p className="text-[11px] text-slate-400 mt-0.5">
											{(selectedFile.size / 1024).toFixed(1)} KB — Nhấp để chọn tệp khác
										</p>
									</div>
								) : (
									<div>
										<p className="text-xs font-semibold text-slate-200">
											Nhấp để chọn gói mã nguồn <span className="font-mono text-brand-400">.zip</span>
										</p>
										<p className="text-[11px] text-slate-500 mt-0.5">
											Bao gồm <span className="font-mono">main.py</span> (định nghĩa <span className="font-mono">run_training</span> & <span className="font-mono">run_inference</span>) và <span className="font-mono">plugin_manifest.json</span>
										</p>
									</div>
								)}
							</div>
						</div>
					) : (
						<div>
							<label
								htmlFor="plugin-local-path-input"
								className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
							>
								Đường dẫn Gói Plugin (`model_artifact_path`) <span className="text-rose-400">*</span>
							</label>
							<div className="flex gap-2">
								<input
									id="plugin-local-path-input"
									type="text"
									value={localPath}
									onChange={(e) => setLocalPath(e.target.value)}
									placeholder="Ví dụ: custom-models/logistic_regression hoặc D:/models/my_plugin.zip"
									className="flex-1 px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none transition"
								/>
								{Boolean((window as any).electronAPI?.openFileDialog) && (
									<button
										type="button"
										onClick={handleBrowseLocalFile}
										className="px-3 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-xs text-slate-200 transition"
									>
										Browse...
									</button>
								)}
							</div>
						</div>
					)}

					{/* Contract Reminder Banner */}
					<div className="p-3 rounded-xl bg-dark-950 border border-dark-800 text-[11px] text-slate-400 flex items-start gap-2.5">
						<ShieldCheck className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
						<div className="space-y-1">
							<div className="font-semibold text-slate-200">Hợp đồng kiểm định 2 giai đoạn (2-Stage Validation):</div>
							<div>
								1. <strong className="text-slate-300">Static AST Check:</strong> Kiểm tra chữ ký hàm <span className="font-mono text-slate-300">run_training</span>, <span className="font-mono text-slate-300">run_inference</span> và chặn các thư viện mạng/hệ thống nguy hiểm.
							</div>
							<div>
								2. <strong className="text-slate-300">Dynamic Dry-Run:</strong> Tự động chạy thử huấn luyện & suy diễn trên dữ liệu giả lập <span className="font-mono text-slate-300">FEATURE_ENGINEERED</span> để xác nhận sinh đủ trọng số và <span className="font-mono text-slate-300">preprocessor.joblib</span>.
							</div>
						</div>
					</div>

					{/* Optional Manifest Override */}
					<div className="border border-dark-800 rounded-xl overflow-hidden bg-dark-950/50">
						<button
							type="button"
							onClick={() => setEnableManifestOverride(!enableManifestOverride)}
							className="w-full flex items-center justify-between px-4 py-2.5 text-left text-xs font-semibold text-slate-200 hover:bg-dark-800/50 transition"
						>
							<span className="flex items-center gap-2">
								{enableManifestOverride ? (
									<ChevronDown className="w-4 h-4 text-brand-400" />
								) : (
									<ChevronRight className="w-4 h-4 text-slate-400" />
								)}
								Khai báo / Ghi đè Manifest (`manifest_override` — Tùy chọn)
							</span>
							<span className="text-[10px] font-mono text-slate-400">
								{enableManifestOverride ? 'ENABLED' : 'BUNDLED plugin_manifest.json'}
							</span>
						</button>

						{enableManifestOverride && (
							<div className="p-4 border-t border-dark-800 space-y-3">
								<div className="grid grid-cols-2 gap-3">
									<div>
										<label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
											Model Technical Name (`model_name`) *
										</label>
										<input
											type="text"
											value={modelName}
											onChange={(e) => setModelName(e.target.value)}
											placeholder="custom_logistic_regression"
											className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none"
										/>
									</div>
									<div>
										<label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
											Display Name (`display_name`)
										</label>
										<input
											type="text"
											value={displayName}
											onChange={(e) => setDisplayName(e.target.value)}
											placeholder="Custom Logistic Regression"
											className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
										/>
									</div>
								</div>

								<div className="grid grid-cols-3 gap-3">
									<div>
										<label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
											Framework
										</label>
										<select
											value={framework}
											onChange={(e) => setFramework(e.target.value)}
											className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
										>
											<option value="scikit-learn">scikit-learn</option>
											<option value="xgboost">xgboost</option>
											<option value="lightgbm">lightgbm</option>
											<option value="pytorch">pytorch</option>
											<option value="pyg">pyg</option>
											<option value="onnx">onnx</option>
										</select>
									</div>
									<div>
										<label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
											Data Modality
										</label>
										<select
											value={dataModality}
											onChange={(e) => setDataModality(e.target.value as DataModality)}
											className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
										>
											<option value="tabular">tabular</option>
											<option value="sequence">sequence</option>
											<option value="matrix_2d">matrix_2d</option>
											<option value="graph">graph</option>
										</select>
									</div>
									<div>
										<label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
											Input Format
										</label>
										<select
											value={dataFormat}
											onChange={(e) => setDataFormat(e.target.value as DataFormat)}
											className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
										>
											<option value="parquet">parquet</option>
											<option value="csv">csv</option>
										</select>
									</div>
								</div>

								<div>
									<label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
										Description
									</label>
									<input
										type="text"
										value={description}
										onChange={(e) => setDescription(e.target.value)}
										placeholder="Mô tả thuật toán và phương pháp chuẩn hóa..."
										className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
									/>
								</div>

								<div className="grid grid-cols-2 gap-3">
									<div>
										<label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
											Default Hyperparameters (JSON)
										</label>
										<textarea
											rows={4}
											value={defaultHyperparamsJson}
											onChange={(e) => setDefaultHyperparamsJson(e.target.value)}
											className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-[11px] font-mono text-slate-200 focus:border-brand-500 focus:outline-none"
										/>
									</div>
									<div>
										<label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
											Hyperparameter Schema (JSON)
										</label>
										<textarea
											rows={4}
											value={hyperparamSchemaJson}
											onChange={(e) => setHyperparamSchemaJson(e.target.value)}
											className="w-full px-2.5 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-[11px] font-mono text-slate-200 focus:border-brand-500 focus:outline-none"
										/>
									</div>
								</div>
							</div>
						)}
					</div>

					{/* Footer */}
					<div className="flex items-center justify-end gap-2.5 pt-3 border-t border-dark-800">
						<button
							type="button"
							onClick={onClose}
							disabled={isSubmitting}
							className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
						>
							Hủy
						</button>
						<button
							type="submit"
							disabled={isSubmitting}
							className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-xs font-semibold shadow-glow-blue transition flex items-center gap-2"
						>
							{isSubmitting ? (
								<>
									<Loader2 className="w-3.5 h-3.5 animate-spin" />
									<span>Đang chạy AST & Dry-Run...</span>
								</>
							) : (
								<>
									<ShieldCheck className="w-3.5 h-3.5" />
									<span>Validate & Register Plugin</span>
								</>
							)}
						</button>
					</div>
				</form>
			</div>
		</div>
	);
};
