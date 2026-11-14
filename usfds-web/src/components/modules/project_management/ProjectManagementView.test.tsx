import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/renderWithProviders';
import { ProjectManagementView } from './ProjectManagementView';

// Covers ISS-005 (R1): primary action is Vietnamese only.
describe('ProjectManagementView', () => {
	it('test_project_management_actions_are_vietnamese', async () => {
		renderWithProviders(<ProjectManagementView />);

		expect(await screen.findByText('Dự án mới')).toBeInTheDocument();
	});
});
