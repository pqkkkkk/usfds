import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { systemMetadataApi } from '@/api/systemMetadataApi';
import type {
	CreateSystemColumnPayload,
	SystemColumnMetadata,
	UpdateSystemColumnPayload,
} from '@/types/systemMetadata';

export const SYSTEM_METADATA_QUERY_KEY = ['system-metadata', 'columns'] as const;

export interface UseSystemMetadataOptions {
	includeInactive?: boolean;
	enabled?: boolean;
}

export function useSystemMetadata(options: UseSystemMetadataOptions = {}) {
	const { includeInactive = false, enabled = true } = options;
	const queryClient = useQueryClient();

	const query = useQuery<SystemColumnMetadata[], Error>({
		queryKey: [...SYSTEM_METADATA_QUERY_KEY, { includeInactive }],
		queryFn: () => systemMetadataApi.listColumns(includeInactive),
		enabled,
	});

	const createMutation = useMutation<SystemColumnMetadata, Error, CreateSystemColumnPayload>({
		mutationFn: (payload) => systemMetadataApi.createColumn(payload),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: SYSTEM_METADATA_QUERY_KEY });
		},
	});

	const updateMutation = useMutation<
		SystemColumnMetadata,
		Error,
		{ metadataId: string; payload: UpdateSystemColumnPayload }
	>({
		mutationFn: ({ metadataId, payload }) => systemMetadataApi.updateColumn(metadataId, payload),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: SYSTEM_METADATA_QUERY_KEY });
		},
	});

	const deleteMutation = useMutation<void, Error, string>({
		mutationFn: (metadataId) => systemMetadataApi.deleteColumn(metadataId),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: SYSTEM_METADATA_QUERY_KEY });
		},
	});

	return {
		columns: query.data ?? [],
		isLoading: query.isLoading,
		isError: query.isError,
		error: query.error,
		refetch: query.refetch,
		createColumn: createMutation.mutateAsync,
		isCreating: createMutation.isPending,
		updateColumn: updateMutation.mutateAsync,
		isUpdating: updateMutation.isPending,
		deleteColumn: deleteMutation.mutateAsync,
		isDeleting: deleteMutation.isPending,
	};
}
