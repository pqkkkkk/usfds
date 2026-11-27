import { describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { TrainingWizardView } from './TrainingWizardView';

const PROJECT_ID = '11111111-1111-1111-1111-111111111111';
const DATASET_ID = '22222222-2222-2222-2222-222222222222';
const ARTIFACT_ID = '33333333-3333-3333-3333-333333333333';
const MODEL_ID = '44444444-4444-4444-4444-444444444444';

function registerWizardCatalogHandlers() {
	server.use(
		http.get(`${API}/v1/projects`, () =>
			HttpResponse.json({
				success: true,
				data: {
					items: [
						{
							project_id: PROJECT_ID,
							project_name: 'Fraud Lab',
							description: 'Test project',
							created_at: '2026-11-20T00:00:00Z',
						},
					],
					nextCursor: null,
				},
			})
		),
		http.get(`${API}/v1/datasets`, () =>
			HttpResponse.json({
				success: true,
				data: {
					items: [
						{
							dataset_id: DATASET_ID,
							project_id: PROJECT_ID,
							dataset_name: 'fraud_tx',
							display_name: 'Giao dịch gian lận',
							created_at: '2026-11-20T00:00:00Z',
						},
					],
					nextCursor: null,
				},
			})
		),
		http.get(`${API}/v1/datasets/${DATASET_ID}`, () =>
			HttpResponse.json({
				success: true,
				data: {
					dataset: {
						dataset_id: DATASET_ID,
						project_id: PROJECT_ID,
						dataset_name: 'fraud_tx',
						display_name: 'Giao dịch gian lận',
					},
					artifacts: [
						{
							artifact_id: ARTIFACT_ID,
							dataset_id: DATASET_ID,
							pipeline_stage: 'FEATURE_ENGINEERED',
							validation_status: 'PASSED',
							row_count: 150000,
							column_count: 24,
							storage_path: 'datasets/fe',
							created_at: '2026-11-20T00:00:00Z',
						},
					],
				},
			})
		),
		http.get(`${API}/v1/training/models`, () =>
			HttpResponse.json({
				success: true,
				data: {
					items: [
						{
							model_id: MODEL_ID,
							project_id: null,
							model_name: 'random_forest',
							display_name: 'Random Forest Classifier',
							execution_type: 'BUILTIN',
							default_hyperparameters: { n_estimators: 100 },
							hyperparameter_schema: null,
							created_at: '2026-11-20T00:00:00Z',
						},
					],
					nextCursor: null,
				},
			})
		)
	);
}

describe('TrainingWizardView compute target selector (ISS-009)', () => {
	it('test_training_wizard_displays_compute_recommendation_and_submits_target', async () => {
		registerWizardCatalogHandlers();

		const capturedPayloads: Array<Record<string, unknown>> = [];
		server.use(
			http.get(`${API}/v1/training/compute-targets`, () =>
				HttpResponse.json({
					success: true,
					data: {
						targets: [
							{
								target_id: 'auto',
								display_name: 'Tự động chọn (Auto)',
								provider_type: 'auto',
								available: true,
								reason: 'Tự động chọn theo quy mô dữ liệu và loại mô hình.',
								resource_tiers: ['cpu', 'gpu'],
							},
							{
								target_id: 'local',
								display_name: 'Local / Dedicated Worker',
								provider_type: 'local',
								available: true,
								reason: null,
								resource_tiers: ['cpu'],
							},
							{
								target_id: 'modal',
								display_name: 'Modal Serverless',
								provider_type: 'remote',
								available: true,
								reason: null,
								resource_tiers: ['cpu', 'gpu'],
							},
						],
						recommendation: {
							requested_target: 'auto',
							resolved_target: 'modal',
							resource_tier: 'cpu',
							provider: 'modal',
							selection_reason: 'Tập dữ liệu lớn (150,000 dòng >= 100,000); đề xuất chạy CPU từ xa trên Modal Serverless.',
						},
					},
				})
			),
			http.post(`${API}/v1/training/runs`, async ({ request }) => {
				capturedPayloads.push((await request.json()) as Record<string, unknown>);
				return HttpResponse.json({
					success: true,
					data: {
						run_id: '55555555-5555-5555-5555-555555555555',
						project_id: PROJECT_ID,
						model_id: MODEL_ID,
						run_name: 'run-modal-test',
						status: 'RUNNING',
						compute_target: 'modal',
						external_job_id: 'fc-999',
						default_threshold: 0.5,
						created_at: '2026-11-25T00:00:00Z',
					},
				});
			})
		);

		renderWithProviders(<TrainingWizardView />, {
			initialEntries: [`/models/train?modelId=${MODEL_ID}&artifactId=${ARTIFACT_ID}`],
		});

		// Step 1 -> Step 2
		const nextToModelBtn = await screen.findByRole('button', {
			name: /tiếp theo: thuật toán & siêu tham số/i,
		});
		await waitFor(() => expect(nextToModelBtn).not.toBeDisabled());
		fireEvent.click(nextToModelBtn);

		// Step 2 -> Step 3
		const nextToReviewBtn = await screen.findByRole('button', {
			name: /tiếp theo: xem lại & khởi chạy/i,
		});
		await waitFor(() => expect(nextToReviewBtn).not.toBeDisabled());
		fireEvent.click(nextToReviewBtn);

		// Verify recommendation and Vietnamese reason are rendered
		expect(
			await screen.findByText(/Tập dữ liệu lớn \(150,000 dòng >= 100,000\)/i)
		).toBeInTheDocument();
		expect(screen.getByText('Modal Serverless')).toBeInTheDocument();

		// Manually select Modal Serverless and submit
		fireEvent.click(screen.getByRole('button', { name: /Modal Serverless/i }));
		fireEvent.click(screen.getByRole('button', { name: /Bắt đầu huấn luyện/i }));

		await waitFor(() => {
			expect(capturedPayloads).toHaveLength(1);
		});
		expect(capturedPayloads[0]?.compute_target).toBe('modal');
	});

	it('displays Vietnamese error message when compute-targets endpoint fails', async () => {
		registerWizardCatalogHandlers();

		server.use(
			http.get(`${API}/v1/training/compute-targets`, () =>
				HttpResponse.json(
					{ success: false, error: 'Lỗi máy chủ compute-targets' },
					{ status: 500 }
				)
			)
		);

		renderWithProviders(<TrainingWizardView />, {
			initialEntries: [`/models/train?modelId=${MODEL_ID}&artifactId=${ARTIFACT_ID}`],
		});

		const nextToModelBtn = await screen.findByRole('button', {
			name: /tiếp theo: thuật toán & siêu tham số/i,
		});
		await waitFor(() => expect(nextToModelBtn).not.toBeDisabled());
		fireEvent.click(nextToModelBtn);

		const nextToReviewBtn = await screen.findByRole('button', {
			name: /tiếp theo: xem lại & khởi chạy/i,
		});
		await waitFor(() => expect(nextToReviewBtn).not.toBeDisabled());
		fireEvent.click(nextToReviewBtn);

		expect(
			await screen.findByText(/Không tải được gợi ý môi trường tính toán/i)
		).toBeInTheDocument();
	});
});
