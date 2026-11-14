import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/renderWithProviders';
import { DetectionJobsHubView } from './DetectionJobsHubView';

// Covers ISS-005 (R2): headings use Vietnamese copy only.
describe('DetectionJobsHubView', () => {
	it('test_detection_jobs_hub_headings_are_vietnamese', async () => {
		renderWithProviders(<DetectionJobsHubView />);

		expect(await screen.findByText('Phát hiện gian lận & suy luận theo lô')).toBeInTheDocument();
	});
});
