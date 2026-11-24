import { FeatureRouteGuard } from '@/components/layout/FeatureRouteGuard';
import { FeatureManagementModule } from '@/components/modules/feature_management/FeatureManagementModule';
import { useProject } from '@/hooks';

export function FeatureManagementPage() {
	const { currentProjectId } = useProject();
	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden">
			<FeatureRouteGuard
				feature="featureManagement"
				projectId={currentProjectId}
				fallbackPath="/projects"
			>
				<FeatureManagementModule />
			</FeatureRouteGuard>
		</div>
	);
}
