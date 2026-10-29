import React, { useState } from 'react';
import {
	Rocket,
	X,
	ShieldCheck,
	ShieldAlert,
	Loader2,
	CheckCircle2,
	Sliders,
} from 'lucide-react';
import { trainingApi } from '../../../api/trainingApi';
import type { ModelResponse, ModelVersionResponse } from '../../../types/model';

interface ActivateModelModalProps {
	isOpen: boolean;
	version: ModelVersionResponse | null;
	model?: ModelResponse | null;
	initialThreshold?: number;
	onClose: () => void;
	onSuccess: (updatedVersion: ModelVersionResponse) => void;
}

const ActivateModelDialogContent: React.FC<Omit<ActivateModelModalProps, 'isOpen'>> = ({
	version,
	model,
	initialThreshold,
	onClose,
	onSuccess,
}) => {
	const defaultThresholdVal =
		initialThreshold !== undefined
			? initialThreshold
			: version?.decision_threshold ?? 0.5;

	const [thresholdInput, setThresholdInput] = useState<string>(
		Number(defaultThresholdVal).toFixed(4)
	);
	const [description, setDescription] = useState<string>(version?.description || '');
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [errorMsg, setErrorMsg] = useState<string | null>(null);

	if (!version) {
		return null;
	}

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		const parsedThreshold = parseFloat(thresholdInput);
		if (Number.isNaN(parsedThreshold) || parsedThreshold <= 0 || parsedThreshold >= 1) {
			setErrorMsg('Ngưỡng quyết định (decision_threshold) phải nằm trong khoảng (0.0, 1.0).');
			return;
		}

		setIsSubmitting(true);
		setErrorMsg(null);
		try {
			const res = await trainingApi.activateModelVersion(version.version_id, {
				decision_threshold: parsedThreshold,
				description: description.trim() || undefined,
			});
			if (!res.success || !res.data) {
				setErrorMsg(res.error || 'Kích hoạt phiên bản mô hình thất bại.');
				return;
			}
			onSuccess(res.data);
			onClose();
		} catch (err: any) {
			setErrorMsg(err?.message || 'Kích hoạt phiên bản mô hình thất bại.');
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div
			className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
			role="dialog"
			aria-modal="true"
			aria-labelledby="activate-model-modal-title"
		>
			<div className="w-full max-w-lg bg-dark-900 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
				{/* Header */}
				<div className="flex items-start justify-between p-5 border-b border-dark-800 bg-dark-950/60">
					<div className="flex items-center gap-3">
						<div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
							<Rocket className="w-4 h-4" />
						</div>
						<div>
							<h2 id="activate-model-modal-title" className="text-sm font-bold text-slate-100">
								Kích hoạt Phiên bản Mô hình
							</h2>
							<p className="text-[11px] text-slate-400 mt-0.5">
								Xác thực mã băm SHA-256 và đưa phiên bản mô hình sang trạng thái APPROVED
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

				{/* Body */}
				<form onSubmit={handleSubmit} className="p-5 space-y-4">
					{errorMsg && (
						<div
							role="alert"
							className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2.5"
						>
							<ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
							<span>{errorMsg}</span>
						</div>
					)}

					{/* Metadata summary */}
					<div className="p-3.5 rounded-xl bg-dark-950 border border-dark-800 space-y-2.5">
						<div className="flex items-center justify-between text-xs">
							<span className="text-slate-400">Mô hình:</span>
							<span className="font-semibold text-slate-100">
								{model?.display_name || model?.model_name || version.model_id}
							</span>
						</div>
						<div className="flex items-center justify-between text-xs">
							<span className="text-slate-400">Phiên bản (SemVer):</span>
							<span className="font-mono font-bold text-brand-400">v{version.semver}</span>
						</div>
						<div className="flex items-center justify-between text-xs">
							<span className="text-slate-400">Framework:</span>
							<span className="font-mono text-slate-200">{version.framework || 'scikit-learn'}</span>
						</div>
						<div className="flex items-center justify-between text-xs">
							<span className="text-slate-400">SHA-256 Checksum:</span>
							<span
								className="font-mono text-[11px] text-emerald-400 flex items-center gap-1"
								title={version.checksum_sha256 || ''}
							>
								<ShieldCheck className="w-3.5 h-3.5" />
								{version.checksum_sha256
									? `${version.checksum_sha256.slice(0, 12)}...${version.checksum_sha256.slice(-8)}`
									: 'Verified on Storage'}
							</span>
						</div>
					</div>

					{/* Decision Threshold Input */}
					<div>
						<label
							htmlFor="activate-threshold-input"
							className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 flex items-center gap-1.5"
						>
							<Sliders className="w-3.5 h-3.5 text-brand-400" />
							Ngưỡng quyết định vận hành (Decision Threshold) <span className="text-rose-400">*</span>
						</label>
						<div className="flex items-center gap-3">
							<input
								id="activate-threshold-input"
								type="number"
								step="0.0001"
								min="0.0001"
								max="0.9999"
								value={thresholdInput}
								onChange={(e) => setThresholdInput(e.target.value)}
								required
								className="w-36 px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none transition"
							/>
							<span className="text-[11px] text-slate-400">
								Giao dịch có xác suất dự đoán ≥ ngưỡng này sẽ bị gắn cờ nghi vấn gian lận.
							</span>
						</div>
					</div>

					{/* Optional Description / Release Note */}
					<div>
						<label
							htmlFor="activate-desc-input"
							className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
						>
							Ghi chú kích hoạt (Release Note)
						</label>
						<textarea
							id="activate-desc-input"
							rows={2}
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							placeholder="Ghi chú lý do chọn ngưỡng hoặc mục đích vận hành..."
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-200 focus:border-brand-500 focus:outline-none transition resize-none"
						/>
					</div>

					<div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-300 flex items-start gap-2">
						<CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
						<span>
							Phiên bản này sẽ chuyển sang trạng thái <strong className="font-mono">APPROVED</strong> độc lập và sẵn sàng được lựa chọn trong các tác vụ Batch Detection.
						</span>
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
							className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold transition flex items-center gap-2"
						>
							{isSubmitting ? (
								<>
									<Loader2 className="w-3.5 h-3.5 animate-spin" />
									<span>Đang kiểm định & kích hoạt...</span>
								</>
							) : (
								<>
									<Rocket className="w-3.5 h-3.5" />
									<span>Confirm Activate</span>
								</>
							)}
						</button>
					</div>
				</form>
			</div>
		</div>
	);
};

export const ActivateModelModal: React.FC<ActivateModelModalProps> = (props) => {
	if (!props.isOpen || !props.version) {
		return null;
	}
	return (
		<ActivateModelDialogContent
			key={`${props.version.version_id}-${props.initialThreshold ?? props.version.decision_threshold}`}
			{...props}
		/>
	);
};
