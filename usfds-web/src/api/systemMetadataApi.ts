import { apiClient } from './client';
import type {
	CreateSystemColumnPayload,
	SystemColumnMetadata,
	UpdateSystemColumnPayload,
} from '@/types/systemMetadata';

export const systemMetadataApi = {
	listColumns: async (includeInactive = false): Promise<SystemColumnMetadata[]> => {
		const res = await apiClient.get<SystemColumnMetadata[]>(
			'/v1/system-metadata/columns',
			includeInactive ? { include_inactive: true } : undefined
		);
		if (!res.success || !res.data) {
			throw new Error(res.error || res.message || 'Không thể tải danh sách siêu dữ liệu cột hệ thống');
		}
		return res.data;
	},

	createColumn: async (payload: CreateSystemColumnPayload): Promise<SystemColumnMetadata> => {
		const res = await apiClient.post<SystemColumnMetadata>('/v1/system-metadata/columns', payload);
		if (!res.success || !res.data) {
			throw new Error(res.error || res.message || 'Không thể tạo cột siêu dữ liệu mới');
		}
		return res.data;
	},

	updateColumn: async (
		metadataId: string,
		payload: UpdateSystemColumnPayload
	): Promise<SystemColumnMetadata> => {
		const res = await apiClient.patch<SystemColumnMetadata>(
			`/v1/system-metadata/columns/${metadataId}`,
			payload
		);
		if (!res.success || !res.data) {
			throw new Error(res.error || res.message || 'Không thể cập nhật cột siêu dữ liệu');
		}
		return res.data;
	},

	deleteColumn: async (metadataId: string): Promise<void> => {
		const res = await apiClient.delete<null>(`/v1/system-metadata/columns/${metadataId}`);
		if (!res.success) {
			throw new Error(res.error || res.message || 'Không thể xóa cột siêu dữ liệu');
		}
	},
};
