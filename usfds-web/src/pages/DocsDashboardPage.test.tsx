import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/hooks/useTheme';
import { server } from '@/test/server';
import { DocsDashboardPage } from './DocsDashboardPage';

vi.mock('mermaid', () => ({
	default: {
		initialize: vi.fn(),
		render: vi.fn(async (_id: string, code: string) => ({
			svg: `<svg><text>${code.includes('TRAINING_NODE') ? 'Training diagram' : code.includes('ERD_NODE') ? 'ERD diagram' : 'Runtime diagram'}</text></svg>`,
		})),
	},
}));

const runtimeDocument = `# Context
## 1. System context
\`\`\`mermaid
flowchart LR
RUNTIME_NODE --> Server
\`\`\`
## 2. Packages & dependency direction
\`\`\`mermaid
flowchart LR
Web --> Core
\`\`\`
## 4. Client–server–worker runtime & remote compute
\`\`\`mermaid
flowchart LR
Server --> Worker
\`\`\``;
const flowsDocument = `# Flows
## 1. Flow A — Training (data prep → features → model registry)
\`\`\`mermaid
flowchart LR
TRAINING_NODE --> Model
\`\`\`
## 2. Flow B — Inference → Investigation → Insight
\`\`\`mermaid
flowchart LR
Inference --> Insight
\`\`\``;
const erdDocument = `# ERD
## 2. Data, system metadata & features — [module 2](modules/data-and-features.md)
\`\`\`mermaid
erDiagram
ERD_NODE ||--o{ dataset : contains
\`\`\``;

const overview = {
	repoRoot: '/repo',
	board: { raw: '', phase0Rows: [], activeTaskRows: [] },
	plans: [],
	issues: [],
	issueLinterWarnings: [],
	docsFiles: [{ path: 'docs/arch/README.md', name: 'README.md', category: 'arch', updatedAt: '' }],
};

function renderDashboard() {
	return render(
		<MemoryRouter>
			<ThemeProvider>
				<DocsDashboardPage />
			</ThemeProvider>
		</MemoryRouter>
	);
}

function fileResponse(path: string, content: string) {
	return HttpResponse.json({
		success: true,
		data: { path, absPath: `/repo/${path}`, content, totalLines: 1, highlightStart: null, highlightEnd: null, sliceStart: 1, sliceEnd: 1, snippet: content },
	});
}

describe('Docs dashboard architecture review', () => {
	beforeEach(() => {
		server.use(
			http.get('/__docs_api/overview', () => HttpResponse.json({ success: true, data: overview })),
			http.get('/__docs_api/file', ({ request }) => {
				const path = new URL(request.url).searchParams.get('path') ?? '';
				return fileResponse(path, path.includes('02-data') ? flowsDocument : path.includes('04-data') ? erdDocument : runtimeDocument);
			}),
		);
	});

	it('shows_core_architecture_diagrams_from_source', async () => {
		renderDashboard();
		fireEvent.click(screen.getByRole('button', { name: 'Kiến trúc' }));
		expect(await screen.findByText('Runtime diagram')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: 'Training' }));
		expect(await screen.findByText('Training diagram')).toBeInTheDocument();
		expect(screen.getByText('docs/arch/02-data-and-lifecycle-flows.md')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: 'Data & features' }));
		expect(await screen.findByText('ERD diagram')).toBeInTheDocument();
		expect(screen.getByText('docs/arch/04-data-model-erd.md')).toBeInTheDocument();
	});

	it('reports_missing_or_ambiguous_diagram', async () => {
		server.use(http.get('/__docs_api/file', ({ request }) => {
			const path = new URL(request.url).searchParams.get('path') ?? '';
			return fileResponse(path, '## 1. System context\nKhông có sơ đồ.');
		}));
		renderDashboard();
		fireEvent.click(screen.getByRole('button', { name: 'Kiến trúc' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(/không tìm thấy/i);
	});

	it('reports_ambiguous_diagram', async () => {
		server.use(http.get('/__docs_api/file', ({ request }) => {
			const path = new URL(request.url).searchParams.get('path') ?? '';
			return fileResponse(path, `${runtimeDocument}\n## 1. System context\n\`\`\`mermaid\nflowchart LR\nA --> B\n\`\`\``);
		}));
		renderDashboard();
		fireEvent.click(screen.getByRole('button', { name: 'Kiến trúc' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(/không duy nhất/i);
	});

	it('ignores_stale_diagram_response', async () => {
		let resolveFirst: ((value: Response) => void) | undefined;
		server.use(http.get('/__docs_api/file', ({ request }) => {
			const path = new URL(request.url).searchParams.get('path') ?? '';
			if (path.includes('01-context')) {
				return new Promise<Response>((resolve) => { resolveFirst = resolve; });
			}
			return fileResponse(path, flowsDocument);
		}));
		renderDashboard();
		fireEvent.click(screen.getByRole('button', { name: 'Kiến trúc' }));
		await waitFor(() => expect(resolveFirst).toBeDefined());
		fireEvent.click(screen.getByRole('button', { name: 'Training' }));
		expect(await screen.findByText('Training diagram')).toBeInTheDocument();
		await act(async () => {
			resolveFirst?.(fileResponse('docs/arch/01-context-and-runtime.md', runtimeDocument));
			await new Promise((resolve) => setTimeout(resolve, 0));
		});
		expect(screen.getByText('Training diagram')).toBeInTheDocument();
		expect(screen.queryByText('Runtime diagram')).not.toBeInTheDocument();
	});

	it('shows_file_load_error_and_allows_retry', async () => {
		let attempts = 0;
		server.use(http.get('/__docs_api/file', ({ request }) => {
			const path = new URL(request.url).searchParams.get('path') ?? '';
			attempts += 1;
			return attempts === 1
				? HttpResponse.json({ success: false, error: 'Không thể đọc tài liệu' }, { status: 500 })
				: fileResponse(path, runtimeDocument);
		}));
		renderDashboard();
		fireEvent.click(screen.getByRole('button', { name: 'Kiến trúc' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Không thể đọc tài liệu');
		fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
		expect(await screen.findByText('Runtime diagram')).toBeInTheDocument();
	});

	it('opens_the_selected_source_at_its_heading', async () => {
		const scrollIntoView = vi.fn();
		Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView });
		renderDashboard();
		fireEvent.click(screen.getByRole('button', { name: 'Kiến trúc' }));
		await screen.findByText('Runtime diagram');
		fireEvent.click(screen.getByRole('button', { name: 'docs/arch/01-context-and-runtime.md' }));
		const pane = await screen.findByRole('complementary');
		expect(await within(pane).findByText('1. System context')).toBeInTheDocument();
		await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
		expect(within(pane).queryByRole('alert')).not.toBeInTheDocument();
	});

	it('preserves_dashboard_sections_and_default_document', async () => {
		const paths: string[] = [];
		server.use(http.get('/__docs_api/file', ({ request }) => {
			const path = new URL(request.url).searchParams.get('path') ?? '';
			paths.push(path);
			return fileResponse(path, '# Kiến trúc');
		}));
		renderDashboard();
		expect(await screen.findByText('Tổng số Tasks (BOARD.md)')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /Plans/ }));
		expect(screen.getByText(/Danh sách Plans/)).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /Issues/ }));
		expect(screen.getByPlaceholderText(/Tìm theo ISS-NNN/)).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /Đặc tả/ }));
		await waitFor(() => expect(paths).toContain('docs/arch/README.md'));
	});
});
