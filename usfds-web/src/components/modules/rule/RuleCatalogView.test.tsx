import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { RuleCatalogView } from './RuleCatalogView';

// Covers ISS-005 (R2): headings use Vietnamese copy only.
describe('RuleCatalogView', () => {
	it('test_rule_catalog_headings_are_vietnamese', async () => {
		server.use(http.get(`${API}/v1/rules`, () => HttpResponse.json({ success: true, data: [] })));

		renderWithProviders(<RuleCatalogView />);

		expect((await screen.findAllByText('Quản lý luật')).length).toBeGreaterThan(0);
	});
});
