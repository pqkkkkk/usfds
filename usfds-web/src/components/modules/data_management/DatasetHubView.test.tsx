import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { DatasetHubView } from './DatasetHubView';
import { storageApi } from '@/api/storageApi';
import { datasetApi } from '@/api/datasetApi';
import { detectionApi } from '@/api/detectionApi';
import { insightReportApi } from '@/api/insightReportApi';
import { ACCESS_TOKEN_KEY } from '@/api/client';

// Covers ISS-005 (R1): headings and primary action use Vietnamese only.
describe('DatasetHubView', () => {
	beforeEach(() => {
		localStorage.clear();
		(storageApi as any).clearStorageTypeCache?.();
	});

	afterEach(() => {
		delete (window as any).electronAPI;
		vi.restoreAllMocks();
	});

	it('test_dataset_hub_headings_are_vietnamese', async () => {
		server.use(http.get(`${API}/v1/datasets`, () => HttpResponse.json({ success: true, data: [] })));

		renderWithProviders(<DatasetHubView />);

		expect((await screen.findAllByText('Quản lý dữ liệu')).length).toBeGreaterThan(0);
		expect(screen.getByText('Nhập tập dữ liệu')).toBeInTheDocument();
		expect(screen.getByText('Tổng số tập dữ liệu')).toBeInTheDocument();
	});

	// Covers ISS-036: Browser S3 mode uses presigned upload and does not fabricate ../datasets/ paths.
	it('test_dataset_import_uses_presigned_upload_when_storage_is_s3', async () => {
		let presignBody: any = null;
		let uploadedToS3 = false;
		let importBody: any = null;

		server.use(
			http.get(`${API}/v1/datasets`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/health`, () =>
				HttpResponse.json({
					status: 'healthy',
					storage: { status: 'ready', type: 's3' },
				})
			),
			http.post(`${API}/v1/storage/presigned-upload`, async ({ request }) => {
				presignBody = await request.json();
				return HttpResponse.json({
					success: true,
					data: {
						upload_url: 'https://s3.example.test/bucket/uploads/dataset_raw/tx.csv?sig=1',
						object_key: 'uploads/dataset_raw/tx.csv',
						expires_in: 900,
					},
				});
			}),
			http.put('https://s3.example.test/bucket/uploads/dataset_raw/tx.csv', () => {
				uploadedToS3 = true;
				return new HttpResponse(null, { status: 200 });
			}),
			http.post(`${API}/v1/datasets/import`, async ({ request }) => {
				importBody = await request.json();
				return HttpResponse.json(
					{
						success: true,
						data: {
							dataset_id: 'ds-1',
							dataset_name: importBody.dataset_name,
							status: 'IMPORTED',
						},
					},
					{ status: 201 }
				);
			})
		);

		const { container } = renderWithProviders(<DatasetHubView />);
		fireEvent.click(await screen.findByText('Nhập tập dữ liệu'));

		const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
		expect(fileInput).toBeTruthy();
		expect(fileInput.getAttribute('accept')).toContain('.pq');
		expect(fileInput.getAttribute('accept')).toContain('.txt');

		const csvFile = new File(['step,amount\n1,100\n'], 'tx.csv', { type: 'text/csv' });
		fireEvent.change(fileInput, { target: { files: [csvFile] } });

		fireEvent.click(screen.getByText('Tiếp tục'));

		await waitFor(() => {
			expect(importBody).not.toBeNull();
		});
		expect(presignBody?.purpose).toBe('dataset_raw');
		expect(uploadedToS3).toBe(true);
		expect(importBody.file_path).toBe('uploads/dataset_raw/tx.csv');
		expect(importBody.user_id).toBeUndefined();
	});

	// Covers ISS-036: Electron local mode skips presigned upload and sends native file path.
	it('test_dataset_import_uses_native_path_in_electron_local_mode', async () => {
		let presignCalled = false;
		let importBody: any = null;

		(window as any).electronAPI = {
			getPathForFile: () => '/Users/alice/tx.csv',
		};

		server.use(
			http.get(`${API}/v1/datasets`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/health`, () =>
				HttpResponse.json({
					status: 'healthy',
					storage: { status: 'ready', type: 'local_filesystem' },
				})
			),
			http.post(`${API}/v1/storage/presigned-upload`, () => {
				presignCalled = true;
				return HttpResponse.json({ success: true, data: {} });
			}),
			http.post(`${API}/v1/datasets/import`, async ({ request }) => {
				importBody = await request.json();
				return HttpResponse.json(
					{
						success: true,
						data: {
							dataset_id: 'ds-2',
							dataset_name: importBody.dataset_name,
							status: 'IMPORTED',
						},
					},
					{ status: 201 }
				);
			})
		);

		const { container } = renderWithProviders(<DatasetHubView />);
		fireEvent.click(await screen.findByText('Nhập tập dữ liệu'));

		const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
		const csvFile = new File(['step,amount\n1,100\n'], 'tx.csv', { type: 'text/csv' });
		fireEvent.change(fileInput, { target: { files: [csvFile] } });

		fireEvent.click(screen.getByText('Tiếp tục'));

		await waitFor(() => {
			expect(importBody).not.toBeNull();
		});
		expect(presignCalled).toBe(false);
		expect(importBody.file_path).toBe('/Users/alice/tx.csv');
	});

	// Covers ISS-036: All exports use presigned URLs on S3 (including HTML reports) and authenticated axios on local.
	it('test_exports_use_presigned_url_on_s3_and_authenticated_axios_on_local', async () => {
		const triggerSpy = vi
			.spyOn(storageApi, 'triggerBrowserDownload')
			.mockImplementation(() => {});
		const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
		vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:mock-url');
		vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {});

		let reportPresignedHtmlCalled = false;
		const localAuthHeaders: Array<string | null> = [];
		const exportReq = {
			include_train: true,
			include_test: true,
			include_pipeline: false,
			include_schema: true,
			file_format: 'csv',
		};

		// 1. S3 mode
		server.use(
			http.get(`${API}/health`, () =>
				HttpResponse.json({ status: 'healthy', storage: { status: 'ready', type: 's3' } })
			),
			http.post(`${API}/v1/datasets/ds-1/artifacts/art-1/export`, () =>
				HttpResponse.json({
					success: true,
					data: {
						download_url: 'https://s3.example.test/dataset.zip',
						object_key: 'exports/dataset.zip',
						filename: 'dataset.zip',
						expires_in: 900,
					},
				})
			),
			http.get(`${API}/v1/detection/jobs/job-1/export`, () =>
				HttpResponse.json({
					success: true,
					data: {
						download_url: 'https://s3.example.test/detection.csv',
						object_key: 'exports/detection.csv',
						filename: 'detection.csv',
						expires_in: 900,
					},
				})
			),
			http.get(`${API}/v1/reports/export`, ({ request }) => {
				const url = new URL(request.url);
				if (url.searchParams.get('presigned') === 'true' && url.searchParams.get('file_format') === 'html') {
					reportPresignedHtmlCalled = true;
				}
				return HttpResponse.json({
					success: true,
					data: {
						download_url: 'https://s3.example.test/report.html',
						object_key: 'exports/report.html',
						filename: 'report.html',
						expires_in: 900,
					},
				});
			})
		);

		await datasetApi.exportDataset('ds-1', 'art-1', exportReq);
		await detectionApi.exportResults({ jobId: 'job-1', projectId: 'proj-1', fileFormat: 'csv' });
		await insightReportApi.exportReport({
			projectId: 'proj-1',
			template: 'EXECUTIVE_AUDIT_REPORT',
			format: 'html',
		});

		expect(reportPresignedHtmlCalled).toBe(true);
		expect(triggerSpy).toHaveBeenCalledWith('https://s3.example.test/dataset.zip', 'dataset.zip');
		expect(triggerSpy).toHaveBeenCalledWith('https://s3.example.test/detection.csv', 'detection.csv');
		expect(triggerSpy).toHaveBeenCalledWith('https://s3.example.test/report.html', 'report.html');

		// 2. Local mode with Bearer token
		(storageApi as any).clearStorageTypeCache?.();
		localStorage.setItem(ACCESS_TOKEN_KEY, 'test-jwt-token');

		server.use(
			http.get(`${API}/health`, () =>
				HttpResponse.json({
					status: 'healthy',
					storage: { status: 'ready', type: 'local_filesystem' },
				})
			),
			http.post(`${API}/v1/datasets/ds-1/artifacts/art-1/export`, ({ request }) => {
				localAuthHeaders.push(request.headers.get('authorization'));
				return new HttpResponse('zip-bytes', {
					status: 200,
					headers: { 'Content-Type': 'application/zip' },
				});
			}),
			http.get(`${API}/v1/detection/jobs/job-1/export`, ({ request }) => {
				localAuthHeaders.push(request.headers.get('authorization'));
				return new HttpResponse('col1,col2\n1,2\n', {
					status: 200,
					headers: { 'Content-Type': 'text/csv' },
				});
			}),
			http.get(`${API}/v1/reports/export`, ({ request }) => {
				localAuthHeaders.push(request.headers.get('authorization'));
				return new HttpResponse('<html><body>Report</body></html>', {
					status: 200,
					headers: { 'Content-Type': 'text/html' },
				});
			})
		);

		await datasetApi.exportDataset('ds-1', 'art-1', exportReq);
		await detectionApi.exportResults({ jobId: 'job-1', projectId: 'proj-1', fileFormat: 'csv' });
		await insightReportApi.exportReport({
			projectId: 'proj-1',
			template: 'EXECUTIVE_AUDIT_REPORT',
			format: 'html',
		});

		expect(windowOpenSpy).not.toHaveBeenCalled();
		expect(localAuthHeaders).toEqual([
			'Bearer test-jwt-token',
			'Bearer test-jwt-token',
			'Bearer test-jwt-token',
		]);
	});
});
