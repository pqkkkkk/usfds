import { screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { Topbar } from './Topbar';

/** Covers ISS-005: project menu copy is Vietnamese only. */
describe('Topbar', () => {
	it('test_topbar_project_menu_labels_are_vietnamese', () => {
		renderWithProviders(
			<Topbar
				projects={[]}
				currentProject={null}
				onSelectProject={vi.fn()}
				onCreateProjectClick={vi.fn()}
				onManageProjectsClick={vi.fn()}
				onOpenOmnisearch={vi.fn()}
			/>
		);

		fireEvent.click(screen.getByRole('button', { name: 'Chọn dự án' }));

		expect(screen.getByText('Dự án')).toBeInTheDocument();
		expect(screen.getByText('Chưa chọn dự án')).toBeInTheDocument();
	});
});
