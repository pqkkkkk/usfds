import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import App from '@/App';
import { renderWithProviders } from './renderWithProviders';
import { API, server } from './server';

const PROJECT_1_ID = '11111111-1111-1111-1111-111111111111';

const SAMPLE_PROJECT = {
	project_id: PROJECT_1_ID,
	project_name: 'Dự án RBAC Shell',
	description: 'Test',
	user_id: '22222222-2222-2222-2222-222222222222',
	status: 'ACTIVE',
	is_schema_locked: false,
	raw_schema: null,
	datasets_count: 0,
	rules_count: 0,
	detection_jobs_count: 0,
	created_at: new Date().toISOString(),
	updated_at: new Date().toISOString(),
};

function mockActor(permissions: Record<string, string[]>, roleKey: string) {
	server.use(
		http.get(`${API}/v1/auth/mode`, () =>
			HttpResponse.json({ success: true, data: { auth_mode: 'local_auto' } })
		),
		http.get(`${API}/v1/auth/me`, () =>
			HttpResponse.json({
				success: true,
				data: {
					user_id: '22222222-2222-2222-2222-222222222222',
					username: roleKey,
					email: `${roleKey}@usfds.local`,
					full_name: roleKey,
					status: 'ACTIVE',
					last_login_at: null,
					is_system_admin: false,
					system_role_keys: ['system_member'],
					system_permissions: {},
					projects: [
						{
							project_id: PROJECT_1_ID,
							role_keys: [roleKey],
							permissions,
						},
					],
				},
			})
		),
		http.get(`${API}/v1/projects`, () =>
			HttpResponse.json({ success: true, data: [SAMPLE_PROJECT] })
		),
		http.get(`${API}/v1/datasets`, () => HttpResponse.json({ success: true, data: [] })),
		http.get(`${API}/v1/rules`, () => HttpResponse.json({ success: true, data: [] })),
		http.get(`${API}/v1/detection/jobs`, () => HttpResponse.json({ success: true, data: [] })),
		http.get(`${API}/v1/cases`, () =>
			HttpResponse.json({ success: true, data: { items: [], total: 0, page: 1, size: 50 } })
		),
		http.get(`${API}/v1/cases/kpis`, () => HttpResponse.json({ success: true, data: {} }))
	);
}

describe('M3 Feature visibility in Shell & Route Guards', () => {
	beforeEach(() => {
		localStorage.clear();
		localStorage.setItem('usfds_active_project_id', PROJECT_1_ID);
	});

	it('test_sidebar_omnisearch_and_route_guard_by_role', async () => {
		const user = userEvent.setup();

		// 1. fraud_analyst: no modelManagement, no createProject, no adminUsers
		mockActor(
			{
				'project:read': ['PROJECT'],
				'dataset:read': ['PROJECT'],
				'rule:read': ['PROJECT'],
				'detection:read': ['PROJECT'],
				'case:read': ['PROJECT'],
				'report:read': ['PROJECT'],
			},
			'fraud_analyst'
		);

		const { unmount } = renderWithProviders(<App />, { initialEntries: ['/datasets'] });

		await waitFor(() => {
			expect(screen.getByText('Điều tra')).toBeInTheDocument();
		});
		expect(screen.queryByText('Quản lý mô hình')).not.toBeInTheDocument();

		// Topbar dropdown hides "Dự án mới" when lacking project:create
		await user.click(screen.getByRole('button', { name: 'Chọn dự án' }));
		expect(screen.queryByText('Dự án mới')).not.toBeInTheDocument();

		// Omnisearch hides "Quản lý mô hình"
		await user.click(screen.getByRole('button', { name: /Tìm kiếm tập dữ liệu/i }));
		expect(screen.getByRole('dialog', { name: 'Tìm kiếm nhanh' })).toBeInTheDocument();
		expect(screen.queryByText(/Quản lý mô hình/i)).not.toBeInTheDocument();

		unmount();

		// Direct URL /models is blocked for fraud_analyst
		const { unmount: unmountModels } = renderWithProviders(<App />, { initialEntries: ['/models'] });
		await waitFor(() => {
			expect(screen.getByText(/Bạn không có quyền truy cập/i)).toBeInTheDocument();
		});
		unmountModels();

		// 2. data_scientist: hides Điều tra in Sidebar & blocks /investigation
		mockActor(
			{
				'project:read': ['PROJECT'],
				'dataset:read': ['PROJECT'],
				'model:read': ['PROJECT'],
				'training:read': ['PROJECT'],
				'rule:read': ['PROJECT'],
				'detection:read': ['PROJECT'],
				'report:read': ['PROJECT'],
			},
			'data_scientist'
		);

		renderWithProviders(<App />, { initialEntries: ['/investigation'] });
		await waitFor(() => {
			expect(screen.getByText(/Bạn không có quyền truy cập/i)).toBeInTheDocument();
		});
		expect(screen.queryByText('Điều tra')).not.toBeInTheDocument();
		expect(screen.getByText('Quản lý mô hình')).toBeInTheDocument();
	});
});
