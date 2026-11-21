import { describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
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

	it('ModelHubView renders partial data when per-model version fetch fails', async () => {
		server.use(
			http.get(`${API}/v1/training/models`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{
							model_id: 'm1',
							model_name: 'Model Alpha',
							display_name: 'Model Alpha',
							description: '',
							model_type: 'BUILTIN',
							created_at: '2026-11-16T00:00:00Z',
						},
						{
							model_id: 'm2',
							model_name: 'Model Beta',
							display_name: 'Model Beta',
							description: '',
							model_type: 'BUILTIN',
							created_at: '2026-11-16T00:00:00Z',
						},
					],
				})
			),
			http.get(`${API}/v1/training/runs`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/training/models/m1/versions`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{
							version_id: 'v1',
							model_id: 'm1',
							version: 'v1.0',
							status: 'APPROVED',
							is_active: true,
							created_at: '2026-11-16T00:00:00Z',
						},
					],
				})
			),
			http.get(`${API}/v1/training/models/m2/versions`, () =>
				HttpResponse.json({ detail: 'Lỗi tải phiên bản' }, { status: 500 })
			)
		);

		renderWithProviders(<ModelHubView />);

		expect(await screen.findByText('Model Alpha')).toBeInTheDocument();
		expect(screen.getByText('Model Beta')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /Model Registry \(2\)/ }));
		expect(await screen.findByText('1 APPROVED')).toBeInTheDocument();
	});

	it('test_model_hub_passes_project_id_to_list_model_versions', async () => {
		const seenProjectQueries: Array<string | null> = [];
		server.use(
			http.get(`${API}/v1/projects`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{
							project_id: 'proj-1',
							project_name: 'Project One',
							status: 'ACTIVE',
							created_at: '2026-11-16T00:00:00Z',
						},
					],
				})
			),
			http.get(`${API}/v1/training/models`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{
							model_id: 'm1',
							model_name: 'random_forest',
							display_name: 'Random Forest',
							execution_type: 'BUILTIN',
							created_at: '2026-11-16T00:00:00Z',
						},
					],
				})
			),
			http.get(`${API}/v1/training/runs`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/training/models/m1/versions`, ({ request }) => {
				const url = new URL(request.url);
				seenProjectQueries.push(url.searchParams.get('project_id'));
				return HttpResponse.json({ success: true, data: [] });
			})
		);

		renderWithProviders(<ModelHubView />);

		expect(await screen.findByText('Random Forest')).toBeInTheDocument();
		await waitFor(() => {
			expect(seenProjectQueries).toContain('proj-1');
		});
	});
});
