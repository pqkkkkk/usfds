import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/hooks/useTheme';
import { server } from '@/test/server';
import { DocsDashboardPage } from './DocsDashboardPage';
import { parsePlanMarkdown } from '../../viteDocsPlugin';

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
\`\`\`
## 5. Investigation — [module 5](modules/investigation-and-graph.md)
\`\`\`mermaid
erDiagram
ERD_NODE ||--o{ case : contains
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

	it('navigates_all_dashboard_sections', async () => {
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Plans/ }));
		expect(screen.getByText('Chọn một plan để bắt đầu review.')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /Issues/ }));
		expect(screen.getByPlaceholderText(/Tìm theo ISS-NNN/)).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: 'Kiến trúc' }));
		expect(await screen.findByText('Runtime diagram')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /Đặc tả/ }));
		expect(await screen.findByText('1. System context')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /Task Board/ }));
		expect(screen.getByText('Tổng số Tasks (BOARD.md)')).toBeInTheDocument();
	});

	it('keeps_unsaved_edits_and_reports_save_failure', async () => {
		const first = parsePlanMarkdown('# Plan: First\n\n## Notes\nFirst', 'user_management_rbac', '.plan/user_management_rbac.md', '');
		const second = parsePlanMarkdown('# Plan: Second\n\n## Notes\nSecond', 'other_plan', '.plan/other_plan.md', '');
		server.use(http.get('/__docs_api/overview', () => HttpResponse.json({
			success: true,
			data: { ...overview, plans: [first, second], board: { ...overview.board, activeTaskRows: [['[`user_management_rbac`](user_management_rbac.md)'], ['[`other_plan`](other_plan.md)']] } },
		})));
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Plans/ }));
		fireEvent.click(screen.getByRole('button', { name: 'Sửa Markdown' }));
		fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bản nháp plan' } });
		fireEvent.click(screen.getByRole('button', { name: /other_plan/ }));
		expect(confirm).toHaveBeenCalled();
		expect(screen.getByRole('textbox')).toHaveValue('Bản nháp plan');
		confirm.mockRestore();
	});

	it('opens_linked_architecture_source_and_diagram', async () => {
		const plan = parsePlanMarkdown(`# Plan: Architecture review
## 1. Context
\`docs/arch/modules/data-and-features.md\`
## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | \`usfds-web/src/components/modules/investigation/CaseQueueView.tsx\` | M1 | — |`,
		'user_management_rbac', '.plan/user_management_rbac.md', '');
		server.use(http.get('/__docs_api/overview', () => HttpResponse.json({
			success: true,
			data: { ...overview, plans: [plan], board: { ...overview.board, activeTaskRows: [['[`user_management_rbac`](user_management_rbac.md)']] } },
		})));
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Plans/ }));
		expect(screen.getByText('Đã khai báo')).toBeInTheDocument();
		expect(screen.getByText('Gợi ý')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: /docs\/arch\/modules\/data-and-features.md/ }));
		expect(await screen.findByTitle('docs/arch/modules/data-and-features.md')).toHaveTextContent('data-and-features.md');
		fireEvent.click(screen.getByRole('button', { name: 'Xem sơ đồ Investigation' }));
		expect(await screen.findByText('ERD diagram')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Investigation' })).toHaveAttribute('aria-current', 'true');
	});

	it('does_not_allow_editing_a_document_that_failed_to_load', async () => {
		server.use(http.get('/__docs_api/file', () => HttpResponse.json({ success: false, error: 'Tài liệu không đọc được' }, { status: 500 })));
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Đặc tả/ }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Tài liệu không đọc được');
		expect(screen.getByRole('button', { name: 'Chỉnh sửa .md' })).toBeDisabled();
		fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Tài liệu không đọc được');
	});

	it('retries_a_document_after_a_connection_failure', async () => {
		let attempts = 0;
		server.use(http.get('/__docs_api/file', ({ request }) => {
			attempts += 1;
			return attempts === 1 ? HttpResponse.error() : fileResponse(new URL(request.url).searchParams.get('path') ?? '', '# Tài liệu đã tải');
		}));
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Đặc tả/ }));
		expect(await screen.findByRole('alert')).toHaveTextContent(/Không thể tải tài liệu/);
		fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
		expect(await screen.findByText('Tài liệu đã tải')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Chỉnh sửa .md' })).toBeEnabled();
	});

	it('retains_dirty_document_when_selecting_the_same_file', async () => {
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Đặc tả/ }));
		fireEvent.click(await screen.findByRole('button', { name: 'Chỉnh sửa .md' }));
		fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bản nháp' } });
		fireEvent.click(screen.getByRole('button', { name: /arch\/README.md/ }));
		fireEvent.click(screen.getByRole('button', { name: /Task Board/ }));
		expect(confirm).toHaveBeenCalled();
		expect(screen.getByRole('textbox')).toHaveValue('Bản nháp');
		confirm.mockRestore();
	});

	it('keeps_an_older_save_from_changing_the_new_document', async () => {
		let finishSave: ((response: Response) => void) | undefined;
		server.use(
			http.get('/__docs_api/overview', () => HttpResponse.json({ success: true, data: { ...overview, docsFiles: [
				...overview.docsFiles, { path: 'docs/arch/other.md', name: 'other.md', category: 'arch', updatedAt: '' },
			] } })),
			http.put('/__docs_api/file', () => new Promise<Response>((resolve) => { finishSave = resolve; })),
		);
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Đặc tả/ }));
		fireEvent.click(await screen.findByRole('button', { name: 'Chỉnh sửa .md' }));
		fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bản nháp A' } });
		fireEvent.click(screen.getByRole('button', { name: 'Lưu tài liệu' }));
		await waitFor(() => expect(finishSave).toBeDefined());
		expect(screen.getByRole('textbox')).toBeDisabled();
		fireEvent.click(screen.getByRole('button', { name: /arch\/other.md/ }));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Chỉnh sửa .md' })).toBeDisabled());
		await act(async () => { finishSave?.(HttpResponse.json({ success: true })); });
		expect(screen.getByRole('button', { name: 'Chỉnh sửa .md' })).toBeEnabled();
		fireEvent.click(screen.getByRole('button', { name: 'Chỉnh sửa .md' }));
		fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bản nháp B' } });
		expect(screen.getByRole('textbox')).toHaveValue('Bản nháp B');
		confirm.mockReturnValue(false);
		fireEvent.click(screen.getByRole('button', { name: /Task Board/ }));
		expect(screen.getByRole('textbox')).toHaveValue('Bản nháp B');
		confirm.mockRestore();
	});

	it('reports_an_old_save_failure_without_locking_the_new_document', async () => {
		let finishSave: ((response: Response) => void) | undefined;
		server.use(
			http.get('/__docs_api/overview', () => HttpResponse.json({ success: true, data: { ...overview, docsFiles: [
				...overview.docsFiles, { path: 'docs/arch/other.md', name: 'other.md', category: 'arch', updatedAt: '' },
			] } })),
			http.put('/__docs_api/file', () => new Promise<Response>((resolve) => { finishSave = resolve; })),
		);
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Đặc tả/ }));
		fireEvent.click(await screen.findByRole('button', { name: 'Chỉnh sửa .md' }));
		fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bản nháp A' } });
		fireEvent.click(screen.getByRole('button', { name: 'Lưu tài liệu' }));
		await waitFor(() => expect(finishSave).toBeDefined());
		fireEvent.click(screen.getByRole('button', { name: /arch\/other.md/ }));
		await act(async () => { finishSave?.(HttpResponse.json({ success: false, error: 'Lưu A thất bại' }, { status: 500 })); });
		expect(await screen.findByText(/Lưu A thất bại/)).toBeInTheDocument();
		await waitFor(() => expect(screen.getByRole('button', { name: 'Chỉnh sửa .md' })).toBeEnabled());
		confirm.mockRestore();
	});

	it('serializes_plan_mutations_and_blocks_document_edits_while_saving', async () => {
		const parsed = parsePlanMarkdown('# Plan: First\n\n## Notes\nFirst', 'user_management_rbac', '.plan/user_management_rbac.md', '');
		const first = { ...parsed, status: 'Draft', validation: { ...parsed.validation, status: 'valid' as const } };
		const second = { ...first, slug: 'other_plan', filePath: '.plan/other_plan.md', title: 'Second' };
		let finishAction: ((response: Response) => void) | undefined;
		server.use(
			http.get('/__docs_api/overview', () => HttpResponse.json({ success: true, data: { ...overview, plans: [first, second], board: { ...overview.board, activeTaskRows: [['[`user_management_rbac`](user_management_rbac.md)'], ['[`other_plan`](other_plan.md)']] } } })),
			http.post('/__docs_api/plan/action', () => new Promise<Response>((resolve) => { finishAction = resolve; })),
		);
		renderDashboard();
		await screen.findByText('Tổng số Tasks (BOARD.md)');
		fireEvent.click(screen.getByRole('button', { name: /Plans/ }));
		fireEvent.click(screen.getByRole('button', { name: /Duyệt Plan/ }));
		await waitFor(() => expect(finishAction).toBeDefined());
		fireEvent.click(screen.getByRole('button', { name: /other_plan/ }));
		expect(screen.getByRole('button', { name: /Duyệt Plan/ })).toBeDisabled();
		fireEvent.click(screen.getByRole('button', { name: /Đặc tả/ }));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Chỉnh sửa .md' })).toBeDisabled());
		await act(async () => { finishAction?.(HttpResponse.json({ success: true, data: first })); });
		await waitFor(() => expect(screen.getByRole('button', { name: 'Chỉnh sửa .md' })).toBeEnabled());
	});
});
