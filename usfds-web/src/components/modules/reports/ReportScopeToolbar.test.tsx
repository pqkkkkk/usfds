import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { insightReportApi } from '@/api/insightReportApi';
import type { ReportScopeFilter } from '@/types';
import { renderWithProviders } from '@/test/renderWithProviders';
import { API, server } from '@/test/server';
import { ReportScopeToolbar } from './ReportScopeToolbar';

const PROJECT_ID = '11111111-1111-1111-1111-111111111111';

function Harness() {
	const [scope, setScope] = useState<ReportScopeFilter>({});
	useQuery({
		queryKey: ['scope-toolbar-test', scope],
		queryFn: () => insightReportApi.getOverview(PROJECT_ID, scope),
	});
	return <ReportScopeToolbar scope={scope} onChange={setScope} />;
}

describe('ReportScopeToolbar', () => {
	it('filters by transaction date range without job picker', async () => {
		const requests: URLSearchParams[] = [];
		server.use(
			http.get(`${API}/v1/reports/overview`, ({ request }) => {
				requests.push(new URL(request.url).searchParams);
				return HttpResponse.json({ success: true, data: { kpis: {}, funnel: [] } });
			})
		);

		renderWithProviders(<Harness />);

		expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
		expect(screen.queryByLabelText('Phạm vi phiên phát hiện')).not.toBeInTheDocument();

		fireEvent.change(screen.getByLabelText('Từ ngày'), { target: { value: '2026-11-01' } });
		fireEvent.change(screen.getByLabelText('Đến ngày'), { target: { value: '2026-11-30' } });

		await waitFor(() =>
			expect(
				requests.some(
					(p) => p.get('date_from') === '2026-11-01T00:00:00Z' && p.get('date_to') === '2026-11-30T23:59:59Z'
				)
			).toBe(true)
		);
		expect(requests.every((p) => !p.has('job_ids'))).toBe(true);
	});
});
