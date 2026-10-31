import { Routes, Route, Navigate } from 'react-router-dom';
import {
	DetectionJobsHubView,
	DetectionJobWizardView,
	DetectionResultExplorerView,
} from './detection';

export const DetectionJobModule = () => {
	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden bg-dark-950">
			<Routes>
				<Route index element={<DetectionJobsHubView />} />
				<Route path="new" element={<DetectionJobWizardView />} />
				<Route path="jobs/:jobId" element={<DetectionResultExplorerView />} />
				<Route path="*" element={<Navigate to="/detection" replace />} />
			</Routes>
		</div>
	);
};
