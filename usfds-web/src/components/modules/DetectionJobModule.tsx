import { Routes, Route, Navigate } from 'react-router-dom';
import {
	DetectionJobsHubView,
	DetectionJobWizardView,
	DetectionResultExplorerView,
} from './detection';
import { FeatureRouteGuard } from '@/components/layout/FeatureRouteGuard';
import { useProject } from '@/hooks';

export const DetectionJobModule = () => {
	const { currentProjectId } = useProject();
	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden bg-dark-950">
			<Routes>
				<Route index element={<DetectionJobsHubView />} />
				<Route
					path="new"
					element={
						<FeatureRouteGuard feature="createDetection" projectId={currentProjectId} fallbackPath="/detection">
							<DetectionJobWizardView />
						</FeatureRouteGuard>
					}
				/>
				<Route path="jobs/:jobId" element={<DetectionResultExplorerView />} />
				<Route path="*" element={<Navigate to="/detection" replace />} />
			</Routes>
		</div>
	);
};
