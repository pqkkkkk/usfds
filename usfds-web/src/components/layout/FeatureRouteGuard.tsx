import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { useActorContext, type ActorFeatureKey } from '@/hooks/useActorContext';

interface FeatureRouteGuardProps {
	feature: ActorFeatureKey;
	projectId?: string | null;
	fallbackPath?: string;
	children: ReactNode;
}

/** Route guard driven by ActorContext feature policy; hides unauthorized pages with Vietnamese notice. */
export function FeatureRouteGuard({
	feature,
	projectId,
	fallbackPath = '/projects',
	children,
}: FeatureRouteGuardProps) {
	const navigate = useNavigate();
	const { actor, loading, canOpenFeature: can } = useActorContext(projectId);

	if (loading && !actor) {
		return (
			<div className="flex-1 flex items-center justify-center p-6 text-xs text-slate-400">
				Đang kiểm tra quyền truy cập...
			</div>
		);
	}

	if (!can(feature, projectId)) {
		return (
			<div className="flex-1 bg-dark-950 text-slate-100 flex flex-col items-center justify-center gap-4 p-6 text-center">
				<div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400">
					<ShieldAlert className="w-6 h-6" />
				</div>
				<div className="space-y-1 max-w-md">
					<h2 className="text-sm font-bold text-slate-100">Không có quyền truy cập</h2>
					<p className="text-xs text-slate-400">
						Bạn không có quyền truy cập tính năng này trong ngữ cảnh hiện tại.
					</p>
				</div>
				<button
					type="button"
					onClick={() => navigate(fallbackPath, { replace: true })}
					className="px-4 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-700 text-xs text-slate-200 inline-flex items-center gap-1.5 transition"
				>
					<ArrowLeft className="w-3.5 h-3.5" />
					<span>Quay lại trang khả dụng</span>
				</button>
			</div>
		);
	}

	return <>{children}</>;
}
