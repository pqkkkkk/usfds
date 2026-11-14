import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useDatasetPipeline } from './useDatasetPipeline';

// Covers ISS-005 (R1): step action labels are Vietnamese only.
// Alert texts (R2) are already Vietnamese and are not covered here.
function wrapper({ children }: { children: ReactNode }) {
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	return (
		<QueryClientProvider client={queryClient}>
			<MemoryRouter>{children}</MemoryRouter>
		</QueryClientProvider>
	);
}

describe('useDatasetPipeline', () => {
	it('test_pipeline_proceed_and_back_labels_are_vietnamese', () => {
		const { result } = renderHook(() => useDatasetPipeline(undefined, 'step-profiling'), { wrapper });

		expect(result.current.proceedButtonText).toBe('Tiếp tục tới Ánh xạ lược đồ');
		expect(result.current.backButtonText).toBe('Quay lại nguồn gốc dữ liệu');
	});
});
