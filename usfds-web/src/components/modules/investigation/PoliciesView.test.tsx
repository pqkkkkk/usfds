import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { BlacklistEntry } from '@/types/investigation';
import { PoliciesView } from './PoliciesView';

// Example component test: real component + real api client, network mocked by MSW.
const PROJECT_ID = 'p-1';

const ENTRY: BlacklistEntry = {
	blacklist_id: 'b-1',
	entity_type: 'USER_ID',
	entity_value: 'user-42',
	status: 'ACTIVE',
	reason: 'Confirmed account takeover',
	source_case_id: null,
	created_at: '2026-11-01T10:00:00Z',
	created_by: 'analyst',
	removed_at: null,
	removed_by: null,
};

describe('PoliciesView', () => {
	it('renders blacklist entries loaded from the API', async () => {
		server.use(
			http.get(`${API}/v1/blacklist`, ({ request }) => {
				expect(new URL(request.url).searchParams.get('project_id')).toBe(PROJECT_ID);
				return HttpResponse.json({ success: true, data: [ENTRY] });
			}),
			http.get(`${API}/v1/cases/rule-feedback`, () => HttpResponse.json({ success: true, data: [] }))
		);

		renderWithProviders(<PoliciesView projectId={PROJECT_ID} readOnly={false} />);

		expect(await screen.findByText('user-42')).toBeInTheDocument();
		expect(screen.getByText('Confirmed account takeover')).toBeInTheDocument();
		expect(screen.queryByRole('alert')).not.toBeInTheDocument();
	});

	// Covers ISS-005 (R2): table headers use Vietnamese copy only.
	it('test_policies_view_column_labels_are_vietnamese', async () => {
		server.use(
			http.get(`${API}/v1/blacklist`, () => HttpResponse.json({ success: true, data: [ENTRY] })),
			http.get(`${API}/v1/cases/rule-feedback`, () => HttpResponse.json({ success: true, data: [] }))
		);

		renderWithProviders(<PoliciesView projectId={PROJECT_ID} readOnly={false} />);

		await screen.findByText('user-42');
		expect(screen.getByText('Loại & giá trị thực thể')).toBeInTheDocument();
		expect(screen.getByText('Lý do & hồ sơ nguồn')).toBeInTheDocument();
		expect(screen.getByText('Siêu dữ liệu kiểm toán')).toBeInTheDocument();
	});

	it('shows the server error message on HTTP 500', async () => {
		server.use(
			http.get(`${API}/v1/blacklist`, () =>
				HttpResponse.json({ detail: 'Blacklist store unavailable' }, { status: 500 })
			),
			http.get(`${API}/v1/cases/rule-feedback`, () => HttpResponse.json({ success: true, data: [] }))
		);

		renderWithProviders(<PoliciesView projectId={PROJECT_ID} readOnly={false} />);

		// apiClient.get() does NOT throw on 500 (ISS-028): it resolves {success:false, error}.
		// The error reaches react-query only because investigationApi's `unwrap` re-throws it.
		expect(await screen.findByRole('alert')).toHaveTextContent('Blacklist store unavailable');
		expect(screen.queryByText('user-42')).not.toBeInTheDocument();
	});
});
