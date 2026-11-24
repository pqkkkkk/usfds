import { describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { Case, Workbench } from '@/types/investigation';
import { CaseWorkbenchView } from './CaseWorkbenchView';
import { InvestigationModule } from '../InvestigationModule';
import { NetworkGraphExplorer } from './NetworkGraphExplorer';
import { Route, Routes } from 'react-router-dom';

const PROJECT_ID = 'p-1';

const HUBS_PAYLOAD = {
	available: true,
	message: null,
	days: 90,
	total_nodes: 4,
	total_edges: 3,
	hubs: [
		{
			id: 'DEVICE_ID:DEV-HUB',
			entity_type: 'DEVICE_ID',
			entity_value: 'DEV-HUB',
			label: 'DEV-HUB',
			distinct_users: 3,
			tx_count: 5,
			flagged_tx_count: 3,
			flagged_users: 2,
			max_model_score: 0.93,
			risk_status: 'WARNING',
			is_blacklisted: false,
			is_super_node: false,
			pattern_type: 'DEVICE_IP_CARD_HUB',
			merchant_category: null,
		},
	],
};

const SUBGRAPH_PAYLOAD = {
	available: true,
	message: null,
	seed_node_id: 'USER_ID:U-1',
	hops: 2,
	days: 90,
	nodes: [
		{
			id: 'USER_ID:U-1',
			entity_type: 'USER_ID',
			entity_value: 'U-1',
			label: 'U-1',
			tx_count: 2,
			flagged_tx_count: 1,
			total_amount: 500,
			max_model_score: 0.91,
			distinct_users: 0,
			merchant_category: null,
			risk_status: 'WARNING',
			is_blacklisted: false,
			open_case_count: 1,
			resolved_fraud_count: 0,
			case_ids: ['c-1'],
			is_super_node: false,
			is_seed: true,
			pattern_tags: [],
		},
		{
			id: 'DEVICE_ID:DEV-HUB',
			entity_type: 'DEVICE_ID',
			entity_value: 'DEV-HUB',
			label: 'DEV-HUB',
			tx_count: 5,
			flagged_tx_count: 3,
			total_amount: 0,
			max_model_score: 0.93,
			distinct_users: 3,
			merchant_category: null,
			risk_status: 'WARNING',
			is_blacklisted: false,
			open_case_count: 0,
			resolved_fraud_count: 0,
			case_ids: [],
			is_super_node: false,
			is_seed: false,
			pattern_tags: ['DEVICE_IP_CARD_HUB'],
		},
	],
	edges: [
		{
			id: 'USER_ID:U-1->DEVICE_ID:DEV-HUB',
			source: 'USER_ID:U-1',
			target: 'DEVICE_ID:DEV-HUB',
			rel_type: 'USED_DEVICE',
			entity_type: 'DEVICE_ID',
			entity_value: 'DEV-HUB',
			user_id: 'U-1',
			tx_count: 2,
			flagged_tx_count: 1,
			total_amount: 500,
			max_model_score: 0.91,
			first_tx_at: '2026-11-10T01:00:00Z',
			last_tx_at: '2026-11-10T02:00:00Z',
		},
	],
	patterns: [
		{
			pattern_type: 'DEVICE_IP_CARD_HUB',
			node_id: 'DEVICE_ID:DEV-HUB',
			entity_type: 'DEVICE_ID',
			entity_value: 'DEV-HUB',
			distinct_users: 3,
			flagged_users: 2,
			tx_count: 5,
			flagged_tx_count: 3,
			flagged_rate: 0.6,
			summary: 'Cụm chia sẻ DEVICE_ID: 3 tài khoản liên kết (2 tài khoản rủi ro)',
			involved_node_ids: ['DEVICE_ID:DEV-HUB', 'USER_ID:U-1'],
		},
	],
	stats: { node_count: 2, edge_count: 1, pattern_count: 1, flagged_node_count: 2 },
	truncated_neighbors: false,
	total_neighbors: 1,
	canvas_limit_reached: false,
	notice: null,
};

const CASE_SAMPLE: Case = {
	case_id: 'c-1',
	case_code: 'CASE-2026-0001',
	project_id: PROJECT_ID,
	event_id: 'EV-1',
	user_id: 'U-1',
	tx_timestamp: '2026-11-10T02:00:00Z',
	amount: 500,
	model_score: 0.91,
	final_action: 'REJECT',
	dataset_artifact_id: null,
	detection_job_id: 'j-1',
	model_version_id: null,
	triggered_rules: [],
	triggered_rule_codes: ['R1'],
	feature_contributions: [],
	attributes: {},
	status: 'OPEN',
	priority: 'HIGH',
	priority_score: 80,
	resolution_reason: null,
	resolution_summary: null,
	resolved_by: null,
	resolved_at: null,
	verified_label: null,
	version: 1,
	created_at: '2026-11-10T03:00:00Z',
	updated_at: '2026-11-10T03:00:00Z',
};

const WORKBENCH_SAMPLE: Workbench = {
	case: CASE_SAMPLE,
	subject_status: 'ACTIVE',
	related_cases: [],
	related_total: 0,
	profile: { available: true, comparison: [], timeline: [] },
	audit_logs: [],
};

describe('NetworkGraphExplorer & Investigation network integration (ISS-041 / SUC-19)', () => {
	it('NetworkGraphExplorer: renders subgraph, expands node, inspects edge transactions, and runs bulk actions', async () => {
		let capturedBlacklistBody: unknown = null;
		let capturedIntakeBody: unknown = null;

		server.use(
			http.get(`${API}/v1/network/hubs`, () => HttpResponse.json({ success: true, data: HUBS_PAYLOAD })),
			http.get(`${API}/v1/network/subgraph`, () => HttpResponse.json({ success: true, data: SUBGRAPH_PAYLOAD })),
			http.post(`${API}/v1/network/expand`, () =>
				HttpResponse.json({
					success: true,
					data: {
						available: true,
						message: null,
						center_node_id: 'DEVICE_ID:DEV-HUB',
						added_nodes: [
							{
								id: 'USER_ID:U-2',
								entity_type: 'USER_ID',
								entity_value: 'U-2',
								label: 'U-2',
								tx_count: 3,
								flagged_tx_count: 2,
								total_amount: 900,
								max_model_score: 0.89,
								distinct_users: 0,
								merchant_category: null,
								risk_status: 'WARNING',
								is_blacklisted: false,
								open_case_count: 0,
								resolved_fraud_count: 0,
								case_ids: [],
								is_super_node: false,
								is_seed: false,
								pattern_tags: [],
							},
						],
						added_edges: [
							{
								id: 'USER_ID:U-2->DEVICE_ID:DEV-HUB',
								source: 'USER_ID:U-2',
								target: 'DEVICE_ID:DEV-HUB',
								rel_type: 'USED_DEVICE',
								entity_type: 'DEVICE_ID',
								entity_value: 'DEV-HUB',
								user_id: 'U-2',
								tx_count: 3,
								flagged_tx_count: 2,
								total_amount: 900,
								max_model_score: 0.89,
								first_tx_at: '2026-11-10T01:00:00Z',
								last_tx_at: '2026-11-10T03:00:00Z',
							},
						],
						patterns: [],
						truncated_neighbors: true,
						total_neighbors: 75,
						canvas_limit_reached: false,
						notice: 'Thực thể này có 75 liên kết. Hệ thống đang hiển thị 50 liên kết có điểm rủi ro cao nhất để đảm bảo hiệu năng trực quan.',
					},
				})
			),
			http.get(`${API}/v1/network/edge-transactions`, () =>
				HttpResponse.json({
					success: true,
					data: {
						available: true,
						message: null,
						user_id: 'U-1',
						entity_type: 'DEVICE_ID',
						entity_value: 'DEV-HUB',
						total: 1,
						transactions: [
							{
								event_id: 'EV-NEW-99',
								job_id: 'job-99',
								user_id: 'U-1',
								tx_timestamp: '2026-11-10T02:00:00Z',
								amount: 450,
								model_score: 0.91,
								final_action: 'REJECT',
								is_flagged: true,
								rule_codes: ['R_DEV'],
								case_id: null,
							},
						],
					},
				})
			),
			http.post(`${API}/v1/blacklist/bulk`, async ({ request }) => {
				capturedBlacklistBody = await request.json();
				return HttpResponse.json(
					{ success: true, data: { added: [], skipped: [], added_count: 2, skipped_count: 0 } },
					{ status: 201 }
				);
			}),
			http.post(`${API}/v1/cases/bulk-intake`, async ({ request }) => {
				capturedIntakeBody = await request.json();
				return HttpResponse.json(
					{ success: true, data: { created_case_ids: ['c-99'], accepted_count: 1, skipped_event_ids: [] } },
					{ status: 201 }
				);
			})
		);

		renderWithProviders(
			<NetworkGraphExplorer
				projectId={PROJECT_ID}
				readOnly={false}
				initialSeedType="USER_ID"
				initialSeedValue="U-1"
			/>
		);

		expect(await screen.findByText(/Cụm chia sẻ DEVICE_ID/i)).toBeInTheDocument();
		expect(screen.getAllByText('DEV-HUB').length).toBeGreaterThanOrEqual(1);

		// Expand DEV-HUB node
		fireEvent.click(screen.getByRole('button', { name: /Mở rộng DEVICE_ID:DEV-HUB/i }));
		expect(await screen.findByText(/hiển thị 50 liên kết có điểm rủi ro cao nhất/i)).toBeInTheDocument();
		expect(screen.getByText('U-2')).toBeInTheDocument();

		// Inspect edge transactions
		fireEvent.click(screen.getByRole('button', { name: /Xem cạnh U-1 -> DEV-HUB/i }));
		expect(await screen.findByText('EV-NEW-99')).toBeInTheDocument();

		// Select flagged transaction without case and run bulk-intake
		fireEvent.click(screen.getByLabelText(/Chọn giao dịch EV-NEW-99/i));
		fireEvent.click(screen.getByRole('button', { name: /Tạo hồ sơ điều tra/i }));
		await waitFor(() => {
			expect(capturedIntakeBody).toEqual({
				project_id: PROJECT_ID,
				items: [{ detection_job_id: 'job-99', event_id: 'EV-NEW-99' }],
				analyst_notes: null,
			});
		});

		// Select 2 nodes and run bulk-blacklist (requires >= 10 char reason)
		fireEvent.click(screen.getByLabelText(/Chọn nút USER_ID:U-1/i));
		fireEvent.click(screen.getByLabelText(/Chọn nút DEVICE_ID:DEV-HUB/i));
		const reasonInput = screen.getByPlaceholderText(/Lý do chặn hàng loạt/i);
		fireEvent.change(reasonInput, { target: { value: 'Too short' } });
		expect(screen.getByRole('button', { name: /Chặn hàng loạt thực thể/i })).toBeDisabled();

		fireEvent.change(reasonInput, { target: { value: 'Confirmed device sharing fraud ring from graph' } });
		fireEvent.click(screen.getByRole('button', { name: /Chặn hàng loạt thực thể/i }));
		await waitFor(() => {
			expect(capturedBlacklistBody).toEqual({
				project_id: PROJECT_ID,
				entities: [
					{ entity_type: 'USER_ID', entity_value: 'U-1' },
					{ entity_type: 'DEVICE_ID', entity_value: 'DEV-HUB' },
				],
				reason: 'Confirmed device sharing fraud ring from graph',
				source_case_id: null,
			});
		});

		// RBAC: viewer without blacklist:manage or case:create sees no bulk write buttons
		server.use(
			http.get(`${API}/v1/auth/me`, () =>
				HttpResponse.json({
					success: true,
					data: {
						user_id: 'u-viewer',
						username: 'viewer',
						is_system_admin: false,
						system_role_keys: [],
						system_permissions: {},
						projects: [{ project_id: PROJECT_ID, role_keys: ['viewer'], permissions: { 'case:read': ['PROJECT'] } }],
					},
				})
			)
		);
		const restricted = renderWithProviders(
			<NetworkGraphExplorer
				projectId={PROJECT_ID}
				readOnly={false}
				initialSeedType="USER_ID"
				initialSeedValue="U-1"
			/>
		);
		await restricted.findAllByText(/Cụm chia sẻ DEVICE_ID/i);
		expect(restricted.container.querySelector('button[data-action="bulk-blacklist"]')).toBeNull();
	});

	it('CaseWorkbenchView & InvestigationModule: integrates Network Graph tab and standalone /investigation/network route', async () => {
		server.use(
			http.get(`${API}/v1/cases/c-1/workbench`, () => HttpResponse.json({ success: true, data: WORKBENCH_SAMPLE })),
			http.get(`${API}/v1/network/hubs`, () => HttpResponse.json({ success: true, data: HUBS_PAYLOAD })),
			http.get(`${API}/v1/network/subgraph`, ({ request }) => {
				const url = new URL(request.url);
				expect(url.searchParams.get('seed_value')).toBe('U-1');
				return HttpResponse.json({ success: true, data: SUBGRAPH_PAYLOAD });
			})
		);

		const wb = renderWithProviders(
			<Routes>
				<Route path="/investigation/cases/:caseId" element={<CaseWorkbenchView projectId={PROJECT_ID} readOnly={false} />} />
			</Routes>,
			{ initialEntries: ['/investigation/cases/c-1'] }
		);

		expect(await wb.findByText('CASE-2026-0001')).toBeInTheDocument();
		fireEvent.click(wb.getByRole('button', { name: /Đồ thị mạng lưới/i }));
		expect(await wb.findByRole('link', { name: /Mở toàn màn hình/i })).toHaveAttribute(
			'href',
			'/investigation/network?seed_type=USER_ID&seed_value=U-1&case_id=c-1'
		);
		wb.unmount();

		server.use(
			http.get(`${API}/v1/projects`, () =>
				HttpResponse.json({
					success: true,
					data: {
						items: [{ project_id: PROJECT_ID, project_name: 'Demo', status: 'ACTIVE' }],
						nextCursor: null,
					},
				})
			)
		);
		renderWithProviders(
			<Routes>
				<Route path="/investigation/*" element={<InvestigationModule />} />
			</Routes>,
			{ initialEntries: ['/investigation/network'] }
		);

		expect(await screen.findByRole('heading', { name: /Cụm rủi ro nổi bật/i })).toBeInTheDocument();
		expect(screen.getByPlaceholderText(/Nhập mã thực thể hạt giống/i)).toBeInTheDocument();
	});

	it('NetworkGraphExplorer: shows Vietnamese error notice when subgraph request fails with HTTP 500', async () => {
		server.use(
			http.get(`${API}/v1/network/hubs`, () => HttpResponse.json({ success: true, data: HUBS_PAYLOAD })),
			http.get(`${API}/v1/network/subgraph`, () =>
				HttpResponse.json({ detail: 'Graph engine temporarily unavailable' }, { status: 500 })
			)
		);

		renderWithProviders(
			<NetworkGraphExplorer
				projectId={PROJECT_ID}
				readOnly={false}
				initialSeedType="USER_ID"
				initialSeedValue="U-1"
			/>
		);

		expect(await screen.findByRole('alert')).toHaveTextContent('Graph engine temporarily unavailable');
	});
});
