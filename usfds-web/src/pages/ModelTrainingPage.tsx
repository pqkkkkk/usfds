import { Routes, Route, Navigate } from 'react-router-dom';
import {
	ModelHubView,
	TrainingWizardView,
	TrainingRunDetailView,
} from '@/components/modules/model';
import { FeatureRouteGuard } from '@/components/layout/FeatureRouteGuard';
import { useProject } from '@/hooks';

export function ModelTrainingPage() {
	const { currentProjectId } = useProject();
	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden">
			<Routes>
				<Route index element={<ModelHubView />} />
				<Route
					path="train"
					element={
						<FeatureRouteGuard feature="createTraining" projectId={currentProjectId} fallbackPath="/models">
							<TrainingWizardView />
						</FeatureRouteGuard>
					}
				/>
				<Route path="runs/:runId" element={<TrainingRunDetailView />} />
				<Route path="*" element={<Navigate to="/models" replace />} />
			</Routes>
		</div>
	);
}
