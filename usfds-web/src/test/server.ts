import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

// Tests run with VITE_API_BASE_URL='' (see vite.config.ts `test.env`), so the client calls `/api/...`.
export const API = '/api';

// Default handlers for requests every render makes (ProjectProvider loads projects on mount).
// Override per test with `server.use(...)`.
export const defaultHandlers = [
	http.get(`${API}/v1/auth/mode`, () =>
		HttpResponse.json({ success: true, data: { auth_mode: 'local_auto' } })
	),
	http.get(`${API}/v1/auth/me`, () =>
		HttpResponse.json({
			success: true,
			data: {
				user_id: '00000000-0000-0000-0000-000000000001',
				username: 'admin',
				email: 'admin@usfds.local',
				full_name: 'System Admin',
				status: 'ACTIVE',
				last_login_at: null,
				is_system_admin: true,
				system_role_keys: ['system_admin'],
				system_permissions: {},
				projects: [],
			},
		})
	),
	http.get(`${API}/v1/projects`, () => HttpResponse.json({ success: true, data: [] })),
];

export const server = setupServer(...defaultHandlers);
