import { Routes, Route, Navigate } from 'react-router-dom';
import {
	ModelHubView,
	TrainingWizardView,
	TrainingRunDetailView,
} from '@/components/modules/model';

export function ModelTrainingPage() {
	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden">
			<Routes>
				<Route index element={<ModelHubView />} />
				<Route path="train" element={<TrainingWizardView />} />
				<Route path="runs/:runId" element={<TrainingRunDetailView />} />
				<Route path="*" element={<Navigate to="/models" replace />} />
			</Routes>
		</div>
	);
}
