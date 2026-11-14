import { X } from 'lucide-react';
import { ModelLineagePanel } from './ModelLineagePanel';
import type { ModelVersionResponse } from '@/types/model';

interface ModelLineageModalProps {
	isOpen: boolean;
	version: ModelVersionResponse | null;
	onClose: () => void;
}

export const ModelLineageModal = ({
	isOpen,
	version,
	onClose,
}: ModelLineageModalProps) => {
	if (!isOpen || !version) return null;

	return (
		<div
			className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
			role="dialog"
			aria-modal="true"
		>
			<div className="w-full max-w-5xl bg-dark-900 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden">
				<div className="px-5 py-3.5 border-b border-dark-800 flex items-center justify-between">
					<h3 className="text-sm font-bold text-slate-100">
						Phả hệ dữ liệu phiên bản v{version.semver}
					</h3>
					<button
						type="button"
						onClick={onClose}
						aria-label="Đóng"
						className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition"
					>
						<X className="w-4 h-4" />
					</button>
				</div>

				<div className="p-4">
					<ModelLineagePanel versionId={version.version_id} compact />
				</div>
			</div>
		</div>
	);
};
