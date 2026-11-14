import { describe, expect, it } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { ModelLineagePanel } from './ModelLineagePanel';
import { ModelHubView } from './ModelHubView';

describe('ModelLineagePanel & ModelHubView Lineage (ISS-008)', () => {
	it('test_model_lineage_panel_renders_nodes_and_inspector', async () => {
		const versionId = 'ver-001';
		server.use(
			http.get(`${API}/v1/training/versions/${versionId}/lineage`, () =>
				HttpResponse.json({
					success: true,
					data: {
						root_version_id: versionId,
						root_run_id: 'run-001',
						nodes: [
							{
								id: 'art-raw-1',
								node_type: 'DATASET_ARTIFACT',
								stage: 'RAW',
								label: 'RAW',
								created_at: '2026-11-14T01:00:00Z',
								parent_id: null,
								dataset_id: 'ds-001',
								metadata: {
									row_count: 1000,
									column_count: 12,
									validation_status: 'PASSED',
								},
							},
							{
								id: 'art-mapped-1',
								node_type: 'DATASET_ARTIFACT',
								stage: 'MAPPED',
								label: 'MAPPED',
								created_at: '2026-11-14T01:01:00Z',
								parent_id: 'art-raw-1',
								dataset_id: 'ds-001',
								metadata: {
									row_count: 1000,
									column_count: 12,
									validation_status: 'PASSED',
								},
							},
							{
								id: 'run-001',
								node_type: 'TRAINING_RUN',
								stage: 'TRAINING_RUN',
								label: 'rf-run-001',
								created_at: '2026-11-14T01:02:00Z',
								parent_id: 'art-mapped-1',
								metadata: {
									run_name: 'rf-run-001',
									status: 'COMPLETED',
									model_name: 'random_forest',
								},
							},
							{
								id: versionId,
								node_type: 'MODEL_VERSION',
								stage: 'MODEL_VERSION',
								label: 'v1.0.0',
								created_at: '2026-11-14T01:03:00Z',
								parent_id: 'run-001',
								metadata: {
									semver: '1.0.0',
									status: 'APPROVED',
									framework: 'scikit-learn',
									decision_threshold: 0.55,
								},
							},
						],
						edges: [
							{ source: 'art-raw-1', target: 'art-mapped-1' },
							{ source: 'art-mapped-1', target: 'run-001' },
							{ source: 'run-001', target: versionId },
						],
					},
				})
			)
		);

		renderWithProviders(<ModelLineagePanel versionId={versionId} />);

		expect((await screen.findAllByText('v1.0.0')).length).toBeGreaterThan(0);
		expect(screen.getByText('rf-run-001')).toBeInTheDocument();
		expect(screen.getByText('RAW')).toBeInTheDocument();

		// Click RAW node and verify inspector updates with RAW metadata
		fireEvent.click(screen.getByText('RAW'));
		const inspector = screen.getByTestId('lineage-node-inspector');
		expect(within(inspector).getByText('art-raw-1')).toBeInTheDocument();
		expect(within(inspector).getByText('1.000')).toBeInTheDocument();
	});

	it('test_model_lineage_panel_shows_error_state', async () => {
		const runId = 'run-missing';
		server.use(
			http.get(`${API}/v1/training/runs/${runId}/lineage`, () =>
				HttpResponse.json({ detail: 'TrainingRun not found' }, { status: 404 })
			)
		);

		renderWithProviders(<ModelLineagePanel runId={runId} />);

		expect(await screen.findByText(/Không thể tải phả hệ/)).toBeInTheDocument();
	});

	it('test_model_hub_opens_lineage_modal_for_version', async () => {
		const modelId = 'mod-001';
		const versionId = 'ver-100';

		server.use(
			http.get(`${API}/v1/training/models`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{
							model_id: modelId,
							user_id: 'u-1',
							model_name: 'random_forest',
							display_name: 'Random Forest',
							execution_type: 'BUILTIN',
							created_at: '2026-11-14T00:00:00Z',
						},
					],
				})
			),
			http.get(`${API}/v1/training/runs`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/training/models/${modelId}/versions`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{
							version_id: versionId,
							model_id: modelId,
							run_id: 'run-100',
							semver: '1.0.0',
							artifact_uri: 'models/rf/1.0.0/model.joblib',
							decision_threshold: 0.5,
							status: 'CANDIDATE',
							registered_at: '2026-11-14T01:03:00Z',
						},
					],
				})
			),
			http.get(`${API}/v1/training/versions/${versionId}/lineage`, () =>
				HttpResponse.json({
					success: true,
					data: {
						root_version_id: versionId,
						root_run_id: 'run-100',
						nodes: [
							{
								id: 'art-raw-100',
								node_type: 'DATASET_ARTIFACT',
								stage: 'RAW',
								label: 'RAW',
								created_at: '2026-11-14T01:00:00Z',
								parent_id: null,
								dataset_id: 'ds-100',
								metadata: {},
							},
							{
								id: versionId,
								node_type: 'MODEL_VERSION',
								stage: 'MODEL_VERSION',
								label: 'v1.0.0',
								created_at: '2026-11-14T01:03:00Z',
								parent_id: 'art-raw-100',
								metadata: { semver: '1.0.0', status: 'CANDIDATE' },
							},
						],
						edges: [{ source: 'art-raw-100', target: versionId }],
					},
				})
			)
		);

		renderWithProviders(<ModelHubView />);

		// Switch to Model Registry tab
		const registryTab = await screen.findByRole('button', { name: /Model Registry/i });
		fireEvent.click(registryTab);

		// Expand the model row
		const modelRow = await screen.findByText('Random Forest');
		fireEvent.click(modelRow);

		// Click "Phả hệ" button on the version row
		const lineageBtn = await screen.findByRole('button', { name: /Phả hệ/i });
		fireEvent.click(lineageBtn);

		// Modal opens and renders the lineage graph
		expect(await screen.findByText(/Phả hệ dữ liệu phiên bản v1\.0\.0/i)).toBeInTheDocument();
		expect(await screen.findByText('art-raw-100'.slice(0, 14) + '...')).toBeInTheDocument();
	});
});
