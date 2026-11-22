import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { ProjectManagementView } from '@/components/modules/project_management/ProjectManagementView';
import { ProjectSettingsView } from '@/components/modules/project_management/ProjectSettingsView';
import { renderWithProviders } from './renderWithProviders';
import { API, server } from './server';

const PROJECT_1_ID = '11111111-1111-1111-1111-111111111111';
const PROJECT_2_ID = '22222222-2222-2222-2222-222222222222';

const PROJECTS = [
	{
		project_id: PROJECT_1_ID,
		project_name: 'Dự án 1',
		description: 'Read only project',
		user_id: '33333333-3333-3333-3333-333333333333',
		status: 'ACTIVE',
		is_schema_locked: true,
		raw_schema: { columns: { amount: { logical_type: 'NUMERIC', physical_dtype: 'float64', nullable: false } } },
		datasets_count: 0,
		rules_count: 0,
		detection_jobs_count: 0,
		created_at: new Date().toISOString(),
		updated_at: new Date().toISOString(),
	},
	{
		project_id: PROJECT_2_ID,
		project_name: 'Dự án 2',
		description: 'Admin project',
		user_id: '33333333-3333-3333-3333-333333333333',
		status: 'ACTIVE',
		is_schema_locked: true,
		raw_schema: { columns: { amount: { logical_type: 'NUMERIC', physical_dtype: 'float64', nullable: false } } },
		datasets_count: 0,
		rules_count: 0,
		detection_jobs_count: 0,
		created_at: new Date().toISOString(),
		updated_at: new Date().toISOString(),
	},
];

describe('M4 Project Portal & Settings Feature Visibility', () => {
	beforeEach(() => {
		localStorage.clear();
		server.use(
			http.get(`${API}/v1/auth/mode`, () =>
				HttpResponse.json({ success: true, data: { auth_mode: 'local_auto' } })
			),
			http.get(`${API}/v1/auth/me`, () =>
				HttpResponse.json({
					success: true,
					data: {
						user_id: '33333333-3333-3333-3333-333333333333',
						username: 'multi_proj_user',
						email: 'user@usfds.local',
						full_name: 'Multi Project User',
						status: 'ACTIVE',
						last_login_at: null,
						is_system_admin: false,
						system_role_keys: ['system_member'],
						system_permissions: {},
						projects: [
							{
								project_id: PROJECT_1_ID,
								role_keys: ['fraud_analyst'],
								permissions: {
									'project:read': ['PROJECT'],
								},
							},
							{
								project_id: PROJECT_2_ID,
								role_keys: ['project_admin'],
								permissions: {
									'project:read': ['PROJECT'],
									'project:update': ['PROJECT'],
									'project:delete': ['PROJECT'],
									'project:reset_schema': ['PROJECT'],
									'project_member:read': ['PROJECT'],
									'project_member:manage': ['PROJECT'],
								},
							},
						],
					},
				})
			),
			http.get(`${API}/v1/projects`, () =>
				HttpResponse.json({ success: true, data: { items: PROJECTS, nextCursor: null } })
			),
			http.get(`${API}/v1/projects/${PROJECT_2_ID}/members`, () =>
				HttpResponse.json({ success: true, data: [] })
			),
			http.get(`${API}/v1/rbac/roles`, () =>
				HttpResponse.json({ success: true, data: [] })
			)
		);
	});

	it('test_project_portal_and_settings_gates', async () => {
		const { unmount } = renderWithProviders(<ProjectManagementView />);

		await waitFor(() => {
			expect(screen.getAllByText('Dự án 1').length).toBeGreaterThan(0);
			expect(screen.getByText('Dự án 2')).toBeInTheDocument();
		});

		// Create project hidden when lacking project:create
		expect(screen.queryByText('Dự án mới')).not.toBeInTheDocument();

		// Project 1 (fraud_analyst): edit/archive/delete hidden
		expect(screen.queryByLabelText('Chỉnh sửa Dự án 1')).not.toBeInTheDocument();
		expect(screen.queryByLabelText('Archive Dự án 1')).not.toBeInTheDocument();
		expect(screen.queryByLabelText('Xóa Dự án 1')).not.toBeInTheDocument();

		// Project 2 (project_admin): edit/archive/delete visible
		expect(screen.getByLabelText('Chỉnh sửa Dự án 2')).toBeInTheDocument();
		expect(screen.getByLabelText('Archive Dự án 2')).toBeInTheDocument();
		expect(screen.getByLabelText('Xóa Dự án 2')).toBeInTheDocument();

		unmount();

		// Settings for Project 1: edit, reset schema, and members section hidden (no members API call)
		localStorage.setItem('usfds_active_project_id', PROJECT_1_ID);
		const { unmount: unmountS1 } = renderWithProviders(<ProjectSettingsView />);
		await waitFor(() => {
			expect(screen.getByRole('heading', { name: 'Dự án 1' })).toBeInTheDocument();
		});
		expect(screen.queryByText('Chỉnh sửa thông tin dự án')).not.toBeInTheDocument();
		expect(screen.queryByText('Đặt lại lược đồ thô')).not.toBeInTheDocument();
		expect(screen.queryByText('Thành viên & Phân quyền dự án')).not.toBeInTheDocument();
		unmountS1();

		// Settings for Project 2: edit, reset schema, and members section visible
		localStorage.setItem('usfds_active_project_id', PROJECT_2_ID);
		renderWithProviders(<ProjectSettingsView />);
		await waitFor(() => {
			expect(screen.getByRole('heading', { name: 'Dự án 2' })).toBeInTheDocument();
		});
		expect(screen.getByText('Chỉnh sửa thông tin dự án')).toBeInTheDocument();
		expect(screen.getByText('Đặt lại lược đồ thô')).toBeInTheDocument();
		expect(screen.getByText('Thành viên & Phân quyền dự án')).toBeInTheDocument();
	});
});
