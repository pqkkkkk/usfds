import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { Case, Workbench } from '@/types/investigation';
import { CaseQueueView } from './CaseQueueView';
import { DecisionAndAuditColumn } from './WorkbenchResolutionColumn';

const PROJECT_ID = 'p-1';

const BASE_CASE: Case = {
	case_id: 'c-1',
	case_code: 'CASE-2026-0001',
	project_id: PROJECT_ID,
	event_id: 'EV-100',
	user_id: 'U-100',
	tx_timestamp: '2026-11-22T01:00:00Z',
	amount: 1500,
	model_score: 0.91,
	final_action: 'REJECT',
	dataset_artifact_id: null,
	detection_job_id: 'j-1',
	model_version_id: null,
	triggered_rules: [],
	triggered_rule_codes: ['R-001'],
	feature_contributions: [],
	attributes: {},
	status: 'OPEN',
	priority: 'HIGH',
	priority_score: 72,
	resolution_reason: null,
	resolution_summary: null,
	resolved_by: null,
	resolved_at: null,
	verified_label: null,
	version: 1,
	created_at: '2026-11-22T01:05:00Z',
	updated_at: '2026-11-22T01:05:00Z',
};

const BASE_WORKBENCH: Workbench = {
	case: BASE_CASE,
	subject_status: 'ACTIVE',
	related_cases: [],
	related_total: 0,
	profile: {
		available: true,
		comparison: [],
		timeline: [],
	},
	audit_logs: [],
};

describe('Investigation workflow without Assign/Claim (ISS-045)', () => {
	it('CaseQueueView & WorkbenchResolutionColumn: no assign/claim UI and escalate requires only note', async () => {
		server.use(
			http.get(`${API}/v1/cases`, () =>
				HttpResponse.json({
					success: true,
					data: { items: [BASE_CASE], total: 1, page: 1, size: 50 },
				})
			),
			http.get(`${API}/v1/cases/kpis`, () =>
				HttpResponse.json({
					success: true,
					data: {
						open: 1,
						in_progress: 0,
						pending_customer: 0,
						critical: 0,
						resolved: 0,
						confirmed_fraud_ratio: null,
					},
				})
			)
		);

		const queueRender = renderWithProviders(<CaseQueueView projectId={PROJECT_ID} readOnly={false} />);
		expect(await screen.findByText('CASE-2026-0001')).toBeInTheDocument();

		expect(screen.queryByLabelText('Phân công')).not.toBeInTheDocument();
		expect(screen.queryByText('Assignee')).not.toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /Nhận xử lý/i })).not.toBeInTheDocument();
		expect(screen.getByRole('link', { name: /Điều tra/i })).toHaveAttribute(
			'href',
			'/investigation/cases/c-1'
		);
		queueRender.unmount();

		const onMutate = vi.fn();
		renderWithProviders(
			<DecisionAndAuditColumn
				projectId={PROJECT_ID}
				data={BASE_WORKBENCH}
				disabled={false}
				draftPending={false}
				onMutate={onMutate}
				onCreateRuleDraft={vi.fn()}
			/>
		);

		await waitFor(() =>
			expect(screen.getByRole('button', { name: /Leo thang lên mức ưu tiên nghiêm trọng/i })).toBeInTheDocument()
		);
		expect(screen.queryByRole('button', { name: /Nhận \/ giao cho tôi/i })).not.toBeInTheDocument();
		expect(screen.queryByLabelText('Phân công cho chuyên viên')).not.toBeInTheDocument();
		expect(screen.queryByText('Người được giao leo thang')).not.toBeInTheDocument();

		const noteInput = screen.getByPlaceholderText(/Nhập kết quả liên hệ khách hàng hoặc lý do leo thang/i);
		fireEvent.change(noteInput, { target: { value: 'Phát hiện chuỗi giao dịch bất thường cần ưu tiên' } });

		const escalateBtn = screen.getByRole('button', { name: /Leo thang lên mức ưu tiên nghiêm trọng/i });
		expect(escalateBtn).toBeEnabled();
		fireEvent.click(escalateBtn);

		expect(onMutate).toHaveBeenCalledWith('escalate', {
			expected_version: 1,
			summary: 'Phát hiện chuỗi giao dịch bất thường cần ưu tiên',
		});
	});

	it('CaseQueueView displays API error notice on HTTP 500', async () => {
		server.use(
			http.get(`${API}/v1/cases`, () =>
				HttpResponse.json({ detail: 'Case queue unavailable' }, { status: 500 })
			),
			http.get(`${API}/v1/cases/kpis`, () =>
				HttpResponse.json({
					success: true,
					data: {
						open: 0,
						in_progress: 0,
						pending_customer: 0,
						critical: 0,
						resolved: 0,
						confirmed_fraud_ratio: null,
					},
				})
			)
		);

		renderWithProviders(<CaseQueueView projectId={PROJECT_ID} readOnly={false} />);
		expect(await screen.findByRole('alert')).toHaveTextContent('Case queue unavailable');
	});
});
