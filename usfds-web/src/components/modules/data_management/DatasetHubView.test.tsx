import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { DatasetHubView } from './DatasetHubView';

// Covers ISS-005 (R1): headings and primary action use Vietnamese only.
describe('DatasetHubView', () => {
	it('test_dataset_hub_headings_are_vietnamese', async () => {
		server.use(http.get(`${API}/v1/datasets`, () => HttpResponse.json({ success: true, data: [] })));

		renderWithProviders(<DatasetHubView />);

		expect((await screen.findAllByText('Quản lý dữ liệu')).length).toBeGreaterThan(0);
		expect(screen.getByText('Nhập tập dữ liệu')).toBeInTheDocument();
		expect(screen.getByText('Tổng số tập dữ liệu')).toBeInTheDocument();
	});
});
