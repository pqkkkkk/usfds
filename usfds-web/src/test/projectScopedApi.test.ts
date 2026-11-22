import { describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { datasetApi } from '@/api/datasetApi';
import { trainingApi } from '@/api/trainingApi';
import { detectionApi } from '@/api/detectionApi';
import { ruleApi } from '@/api/ruleApi';
import { storageApi } from '@/api/storageApi';

describe('Project-scoped API clients (ISS-042)', () => {
	it('test_web_api_clients_attach_project_id_on_all_list_and_get_by_id_calls', async () => {
		const projectId = '00000000-0000-0000-0000-000000000111';
		const seenProjectIds: Record<string, string | null> = {};

		const capture = (key: string) => ({ request }: { request: Request }) => {
			seenProjectIds[key] = new URL(request.url).searchParams.get('project_id');
			return HttpResponse.json({ success: true, data: [] });
		};
		const captureObj = (key: string, data: unknown = {}) => ({ request }: { request: Request }) => {
			seenProjectIds[key] = new URL(request.url).searchParams.get('project_id');
			return HttpResponse.json({ success: true, data });
		};

		(storageApi as unknown as { clearStorageTypeCache?: () => void }).clearStorageTypeCache?.();
		const blobSpy = vi.spyOn(storageApi, 'triggerBlobDownload').mockImplementation(() => {});

		server.use(
			http.get(`${API}/health`, () =>
				HttpResponse.json({
					status: 'healthy',
					storage: { status: 'ready', type: 'local_filesystem' },
				})
			),
			http.get(`${API}/v1/datasets`, capture('listDatasets')),
			http.get(`${API}/v1/datasets/ds-1`, captureObj('getDatasetDetail')),
			http.get(`${API}/v1/datasets/ds-1/artifacts/art-1`, captureObj('getArtifact')),
			http.get(`${API}/v1/training/models`, capture('listModels')),
			http.get(`${API}/v1/training/models/m-1`, captureObj('getModel')),
			http.get(`${API}/v1/training/models/m-1/versions`, capture('listModelVersions')),
			http.get(`${API}/v1/training/versions/v-1`, captureObj('getModelVersion')),
			http.get(`${API}/v1/training/runs`, capture('listTrainingRuns')),
			http.get(`${API}/v1/training/runs/r-1`, captureObj('getTrainingRun')),
			http.get(`${API}/v1/training/versions/v-1/lineage`, captureObj('getModelVersionLineage')),
			http.get(`${API}/v1/training/runs/r-1/lineage`, captureObj('getTrainingRunLineage')),
			http.get(`${API}/v1/detection/jobs`, capture('listJobs')),
			http.get(`${API}/v1/detection/jobs/j-1`, captureObj('getJob')),
			http.get(`${API}/v1/detection/jobs/j-1/results`, captureObj('getJobResults')),
			http.get(`${API}/v1/detection/jobs/j-1/export`, ({ request }) => {
				seenProjectIds.exportResults = new URL(request.url).searchParams.get('project_id');
				return new HttpResponse('id\n1\n', {
					status: 200,
					headers: { 'Content-Type': 'text/csv' },
				});
			}),
			http.get(`${API}/v1/rules`, capture('listRules')),
			http.get(`${API}/v1/rules/rule-1`, captureObj('getRule')),
			http.get(`${API}/v1/rules/rule-1/versions`, capture('getRuleVersions')),
			http.get(
				`${API}/v1/storage/presigned-download`,
				captureObj('requestPresignedDownload', {
					download_url: 'https://s3.example.test/file.csv',
					object_key: 'exports/projects/p1/file.csv',
					filename: 'file.csv',
					expires_in: 900,
				})
			)
		);

		await datasetApi.listDatasets(projectId);
		await datasetApi.getDatasetDetail('ds-1', projectId);
		await datasetApi.getArtifact('ds-1', 'art-1', projectId);
		await trainingApi.listModels(projectId);
		await trainingApi.getModel('m-1', projectId);
		await trainingApi.listModelVersions('m-1', projectId);
		await trainingApi.getModelVersion('v-1', projectId);
		await trainingApi.listTrainingRuns({ projectId });
		await trainingApi.getTrainingRun('r-1', projectId);
		await trainingApi.getModelVersionLineage('v-1', projectId);
		await trainingApi.getTrainingRunLineage('r-1', projectId);
		await detectionApi.listJobs({ projectId });
		await detectionApi.getJob('j-1', projectId);
		await detectionApi.getJobResults({ jobId: 'j-1', projectId });
		const exportUrl = detectionApi.getExportUrl({ jobId: 'j-1', projectId });
		await detectionApi.exportResults({ jobId: 'j-1', projectId, fileFormat: 'csv' });
		await ruleApi.listRules(projectId);
		await ruleApi.getRule('rule-1', projectId);
		await ruleApi.getRuleVersions('rule-1', projectId);
		await storageApi.requestPresignedDownload({
			objectKey: 'exports/projects/p1/file.csv',
			projectId,
		});

		blobSpy.mockRestore();

		expect(exportUrl).toContain(`project_id=${projectId}`);
		expect(seenProjectIds).toEqual({
			listDatasets: projectId,
			getDatasetDetail: projectId,
			getArtifact: projectId,
			listModels: projectId,
			getModel: projectId,
			listModelVersions: projectId,
			getModelVersion: projectId,
			listTrainingRuns: projectId,
			getTrainingRun: projectId,
			getModelVersionLineage: projectId,
			getTrainingRunLineage: projectId,
			listJobs: projectId,
			getJob: projectId,
			getJobResults: projectId,
			exportResults: projectId,
			listRules: projectId,
			getRule: projectId,
			getRuleVersions: projectId,
			requestPresignedDownload: projectId,
		});
	});
});
