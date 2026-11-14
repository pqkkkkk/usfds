import type { ReactElement, ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';
import type { RenderOptions } from '@testing-library/react';
import { ProjectProvider } from '@/hooks/useProjects';
import { ThemeProvider } from '@/hooks/useTheme';

interface ProviderOptions extends Omit<RenderOptions, 'wrapper'> {
	initialEntries?: string[];
}

/**
 * Render a component inside the same providers as `main.tsx` + `App.tsx`,
 * with a fresh QueryClient (no retries) and an in-memory router.
 */
export function renderWithProviders(
	ui: ReactElement,
	{ initialEntries = ['/'], ...options }: ProviderOptions = {}
) {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false, gcTime: Infinity },
			mutations: { retry: false },
		},
	});

	function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>
				<MemoryRouter initialEntries={initialEntries}>
					<ThemeProvider>
						<ProjectProvider>{children}</ProjectProvider>
					</ThemeProvider>
				</MemoryRouter>
			</QueryClientProvider>
		);
	}

	return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}
