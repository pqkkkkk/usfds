import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { ModelHubView } from './ModelHubView';

// Covers ISS-005 (R2): headings use Vietnamese copy only.
describe('ModelHubView', () => {
	it('test_model_hub_headings_are_vietnamese', async () => {
		server.use(
			http.get(`${API}/v1/training/models`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/training/runs`, () => HttpResponse.json({ success: true, data: [] }))
		);

		renderWithProviders(<ModelHubView />);

		expect((await screen.findAllByText('Quản lý mô hình')).length).toBeGreaterThan(0);
	});
});
