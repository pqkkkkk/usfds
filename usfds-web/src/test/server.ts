import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

// Tests run with VITE_API_BASE_URL='' (see vite.config.ts `test.env`), so the client calls `/api/...`.
export const API = '/api';

// Default handlers for requests every render makes (ProjectProvider loads projects on mount).
// Override per test with `server.use(...)`.
export const defaultHandlers = [
	http.get(`${API}/v1/projects`, () => HttpResponse.json({ success: true, data: [] })),
];

export const server = setupServer(...defaultHandlers);
