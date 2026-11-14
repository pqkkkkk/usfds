import { apiClient, axios } from './client';
import { systemApi } from './systemApi';
import type { ApiResponse } from '@/types';

export type StorageUploadPurpose = 'dataset_raw' | 'detection_input' | 'model_plugin';

export interface PresignedUploadData {
	upload_url: string;
	object_key: string;
	expires_in: number;
}

export interface PresignedDownloadData {
	download_url: string;
	object_key: string;
	filename: string;
	expires_in: number;
}

export type PresignedDownloadUrlResponse = PresignedDownloadData;

let cachedStorageType: string | null = null;

export const storageApi = {
	isS3StorageBackend: async (): Promise<boolean> => {
		if (cachedStorageType !== null) {
			return cachedStorageType === 's3';
		}
		try {
			const res = await systemApi.checkHealth();
			if (res.success && res.data?.storage?.type) {
				cachedStorageType = res.data.storage.type;
				return cachedStorageType === 's3';
			}
		} catch {
			// Fallback to local if health check fails
		}
		return false;
	},

	requestPresignedUpload: async (params: {
		filename: string;
		purpose: StorageUploadPurpose;
		projectId?: string;
		contentType?: string;
	}): Promise<ApiResponse<PresignedUploadData>> => {
		return apiClient.post<PresignedUploadData>('/v1/storage/presigned-upload', {
			filename: params.filename,
			purpose: params.purpose,
			project_id: params.projectId || undefined,
			content_type: params.contentType || undefined,
		});
	},

	requestPresignedDownload: async (params: {
		objectKey: string;
		filename?: string;
	}): Promise<ApiResponse<PresignedDownloadData>> => {
		return apiClient.get<PresignedDownloadData>('/v1/storage/presigned-download', {
			object_key: params.objectKey,
			filename: params.filename,
		});
	},

	uploadFileViaPresignedUrl: async (params: {
		file: File;
		purpose: StorageUploadPurpose;
		projectId?: string;
	}): Promise<string> => {
		const contentType = params.file.type || 'application/octet-stream';
		const presignRes = await storageApi.requestPresignedUpload({
			filename: params.file.name,
			purpose: params.purpose,
			projectId: params.projectId,
			contentType,
		});

		if (!presignRes.success || !presignRes.data) {
			throw new Error(presignRes.error || 'Failed to obtain presigned upload URL.');
		}

		const { upload_url, object_key } = presignRes.data;
		await axios.put(upload_url, params.file, {
			headers: {
				'Content-Type': contentType,
			},
		});

		return object_key;
	},

	resolveStoragePath: async (params: {
		file?: File | null;
		filePath?: string;
		purpose: StorageUploadPurpose;
		projectId?: string;
	}): Promise<string> => {
		const isS3 = await storageApi.isS3StorageBackend();
		if (isS3 && params.file) {
			return storageApi.uploadFileViaPresignedUrl({
				file: params.file,
				purpose: params.purpose,
				projectId: params.projectId,
			});
		}
		return (params.filePath || '').trim();
	},

	triggerBrowserDownload: (url: string, filename?: string): void => {
		const link = document.createElement('a');
		link.href = url;
		if (filename) {
			link.download = filename;
		}
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	},
};