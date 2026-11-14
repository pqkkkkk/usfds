import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { Sidebar } from './Sidebar';

/** Covers ISS-005: module labels are Vietnamese only. */
describe('Sidebar', () => {
	it('test_sidebar_module_labels_are_vietnamese', () => {
		renderWithProviders(
			<Sidebar
				activeModule="data-management"
				onSelectModule={vi.fn()}
				collapsed={false}
				onToggleCollapse={vi.fn()}
			/>
		);

		expect(screen.getByText('Quản lý dữ liệu')).toBeInTheDocument();
		expect(screen.getByText('Quản lý mô hình')).toBeInTheDocument();
		expect(screen.getByText('Quản lý luật')).toBeInTheDocument();
		expect(screen.getByText('Phát hiện gian lận')).toBeInTheDocument();
		expect(screen.getByText('Điều tra')).toBeInTheDocument();
		expect(screen.getByText('Phân tích & Báo cáo')).toBeInTheDocument();
		expect(screen.getByText('Cài đặt dự án')).toBeInTheDocument();
	});
});
