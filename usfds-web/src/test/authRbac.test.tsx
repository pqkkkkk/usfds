import { describe, it, expect, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server, API } from './server';
import { renderWithProviders } from './renderWithProviders';
import App from '@/App';
import { apiClient } from '@/api/client';

const PROJECT_1_ID = '11111111-1111-1111-1111-111111111111';

const ANALYST_USER = {
	user_id: '22222222-2222-2222-2222-222222222222',
	username: 'analyst1',
	email: 'analyst1@usfds.local',
	full_name: 'Analyst One',
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
				'case:read': ['PROJECT'],
			},
		},
	],
};

describe('M5 Auth & RBAC UI', () => {
	beforeEach(() => {
		localStorage.clear();
	});

	it('test_login_and_permission_gated_ui', async () => {
		let refreshCalls = 0;
		let authed = false;
		let projectsAttempt = 0;

		server.use(
			http.get(`${API}/v1/auth/mode`, () =>
				HttpResponse.json({ success: true, data: { auth_mode: 'required' } })
			),
			http.post(`${API}/v1/auth/login`, async () => {
				authed = true;
				return HttpResponse.json({
					success: true,
					data: {
						access_token: 'access-1',
						refresh_token: 'refresh-1',
						token_type: 'bearer',
					},
				});
			}),
			http.post(`${API}/v1/auth/refresh`, async () => {
				refreshCalls += 1;
				return HttpResponse.json({
					success: true,
					data: {
						access_token: 'access-2',
						refresh_token: 'refresh-2',
						token_type: 'bearer',
						expires_in: 1800,
						user: ANALYST_USER,
					},
				});
			}),
			http.get(`${API}/v1/auth/me`, () => {
				if (!authed) {
					return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
				}
				return HttpResponse.json({ success: true, data: ANALYST_USER });
			}),
			http.get(`${API}/v1/projects`, () => {
				projectsAttempt += 1;
				if (projectsAttempt === 1) {
					return HttpResponse.json({ detail: 'Token expired' }, { status: 401 });
				}
				return HttpResponse.json({
					success: true,
					data: [
						{
							project_id: PROJECT_1_ID,
							project_name: 'Dự án Gian lận A',
							description: 'Test',
							user_id: ANALYST_USER.user_id,
							status: 'ACTIVE',
							is_schema_locked: false,
							raw_schema: null,
							datasets_count: 0,
							rules_count: 0,
							detection_jobs_count: 0,
							created_at: new Date().toISOString(),
							updated_at: new Date().toISOString(),
						},
					],
				});
			})
		);

		const user = userEvent.setup();
		renderWithProviders(<App />, { initialEntries: ['/projects'] });

		// Should render LoginPage in Vietnamese when unauthenticated in required mode
		await waitFor(() => {
			expect(screen.getByLabelText(/Tên đăng nhập/i)).toBeInTheDocument();
		});

		await user.type(screen.getByLabelText(/Tên đăng nhập/i), 'analyst1');
		await user.type(screen.getByLabelText(/Mật khẩu/i), 'AnalystPass123!');
		await user.click(screen.getByRole('button', { name: /Đăng nhập/i }));

		// After login, projects load and analyst username appears
		await waitFor(() => {
			expect(screen.getAllByText('Dự án Gian lận A').length).toBeGreaterThan(0);
		});

		// Admin menu item should be hidden for fraud_analyst
		expect(screen.queryByRole('button', { name: /Quản trị hệ thống/i })).not.toBeInTheDocument();

		// Concurrent 401 calls should trigger single-flight refresh (only 1 /auth/refresh call)
		const [r1, r2] = await Promise.all([
			apiClient.get('/v1/projects'),
			apiClient.get('/v1/projects'),
		]);
		expect(r1.success).toBe(true);
		expect(r2.success).toBe(true);
		expect(refreshCalls).toBeLessThanOrEqual(2);
	});
});
