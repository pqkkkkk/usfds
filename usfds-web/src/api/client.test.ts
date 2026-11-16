import { describe, expect, it } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import React from 'react';
import { API, server } from '@/test/server';
import { apiClient, ApiClientError } from './client';

describe('ApiClient error propagation (ISS-028)', () => {
	it('rejects with ApiClientError on HTTP 4xx/5xx', async () => {
		server.use(
			http.get(`${API}/v1/test-error`, () => HttpResponse.json({ detail: 'Lỗi server' }, { status: 500 })),
			http.post(`${API}/v1/test-error`, () => HttpResponse.json({ detail: 'Dữ liệu không hợp lệ' }, { status: 400 })),
			http.put(`${API}/v1/test-error`, () => HttpResponse.json({ detail: 'Lỗi cập nhật' }, { status: 500 })),
			http.patch(`${API}/v1/test-error`, () => HttpResponse.json({ detail: 'Lỗi vá' }, { status: 422 })),
			http.delete(`${API}/v1/test-error`, () => HttpResponse.json({ detail: 'Lỗi xóa' }, { status: 404 }))
		);

		await expect(apiClient.get('/v1/test-error')).rejects.toMatchObject({
			name: 'ApiClientError',
			message: 'Lỗi server',
			statusCode: 500,
		});
		await expect(apiClient.get('/v1/test-error')).rejects.toBeInstanceOf(ApiClientError);
		await expect(apiClient.post('/v1/test-error', {})).rejects.toMatchObject({
			message: 'Dữ liệu không hợp lệ',
			statusCode: 400,
		});
		await expect(apiClient.put('/v1/test-error', {})).rejects.toMatchObject({
			message: 'Lỗi cập nhật',
			statusCode: 500,
		});
		await expect(apiClient.patch('/v1/test-error', {})).rejects.toMatchObject({
			message: 'Lỗi vá',
			statusCode: 422,
		});
		await expect(apiClient.delete('/v1/test-error')).rejects.toMatchObject({
			message: 'Lỗi xóa',
			statusCode: 404,
		});
	});

	it('rejects with ApiClientError when response has success: false', async () => {
		server.use(
			http.post(`${API}/v1/test-biz-error`, () =>
				HttpResponse.json({ success: false, data: null, error: 'Thao tác thất bại', code: 400 }, { status: 200 })
			)
		);

		await expect(apiClient.post('/v1/test-biz-error', {})).rejects.toBeInstanceOf(ApiClientError);
		await expect(apiClient.post('/v1/test-biz-error', {})).rejects.toMatchObject({
			message: 'Thao tác thất bại',
		});
	});

	it('retries once then enters react-query error state on failure', async () => {
		let callCount = 0;
		server.use(
			http.get(`${API}/v1/test-retry`, () => {
				callCount += 1;
				return HttpResponse.json({ detail: 'Tạm thời lỗi' }, { status: 500 });
			})
		);

		const testQueryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: 1,
					retryDelay: 0,
				},
			},
		});

		const wrapper = ({ children }: { children: React.ReactNode }) =>
			React.createElement(QueryClientProvider, { client: testQueryClient }, children);

		const { result } = renderHook(
			() =>
				useQuery({
					queryKey: ['test-retry'],
					queryFn: () => apiClient.get('/v1/test-retry'),
				}),
			{ wrapper }
		);

		await waitFor(() => expect(result.current.isError).toBe(true));
		expect(callCount).toBe(2);
		expect(result.current.error).toBeInstanceOf(ApiClientError);
		expect((result.current.error as Error).message).toBe('Tạm thời lỗi');
	});
});
