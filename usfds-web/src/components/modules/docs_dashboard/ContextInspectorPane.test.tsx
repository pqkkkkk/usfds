import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { expect, it, vi } from 'vitest';
import { server } from '@/test/server';
import { ContextInspectorPane } from './ContextInspectorPane';

it('keeps_unsaved_edits_and_reports_save_failure', async () => {
	server.use(
		http.get('/__docs_api/file', () => HttpResponse.json({
			success: true,
			data: { path: 'docs/arch/README.md', absPath: '/repo/docs/arch/README.md', content: '# Original', totalLines: 1, highlightStart: null, highlightEnd: null, sliceStart: 1, sliceEnd: 1, snippet: '# Original' },
		})),
		http.put('/__docs_api/file', () => HttpResponse.json({ success: false, error: 'Lưu thất bại' }, { status: 500 })),
	);
	const onClose = vi.fn();
	const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
	render(<ContextInspectorPane target={{ type: 'file', fileRef: 'docs/arch/README.md' }} issues={[]} onClose={onClose} onSelectIssue={vi.fn()} onSelectFileRef={vi.fn()} onSelectPlan={vi.fn()} onRefreshOverview={vi.fn().mockResolvedValue(undefined)} />);
	fireEvent.click(await screen.findByRole('button', { name: 'Sửa file' }));
	fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bản nháp tài liệu' } });
	fireEvent.click(screen.getByRole('button', { name: 'Lưu vào đĩa' }));
	expect(await screen.findByRole('alert')).toHaveTextContent('Lưu thất bại');
	fireEvent.click(screen.getByRole('button', { name: 'Đóng bảng ngữ cảnh' }));
	expect(confirm).toHaveBeenCalled();
	expect(onClose).not.toHaveBeenCalled();
	expect(screen.getByRole('textbox')).toHaveValue('Bản nháp tài liệu');
	confirm.mockRestore();
});

it('does_not_replace_a_new_target_when_an_older_save_finishes', async () => {
	let finishSave: ((response: Response) => void) | undefined;
	server.use(
		http.get('/__docs_api/file', ({ request }) => {
			const path = new URL(request.url).searchParams.get('path') ?? '';
			return HttpResponse.json({ success: true, data: { path, absPath: `/repo/${path}`, content: `# ${path}`, totalLines: 1, highlightStart: null, highlightEnd: null, sliceStart: 1, sliceEnd: 1, snippet: `# ${path}` } });
		}),
		http.put('/__docs_api/file', () => new Promise<Response>((resolve) => { finishSave = resolve; })),
	);
	const props = { issues: [], onClose: vi.fn(), onSelectIssue: vi.fn(), onSelectFileRef: vi.fn(), onSelectPlan: vi.fn(), onRefreshOverview: vi.fn().mockResolvedValue(undefined) };
	const { container, rerender } = render(<ContextInspectorPane target={{ type: 'file', fileRef: 'docs/arch/a.md' }} {...props} />);
	fireEvent.click(await screen.findByRole('button', { name: 'Sửa file' }));
	fireEvent.change(screen.getByRole('textbox'), { target: { value: 'A draft' } });
	fireEvent.click(screen.getByRole('button', { name: 'Lưu vào đĩa' }));
	await waitFor(() => expect(finishSave).toBeDefined());
	expect(screen.getByRole('textbox')).toBeDisabled();
	rerender(<ContextInspectorPane target={{ type: 'file', fileRef: 'docs/arch/b.md' }} {...props} />);
	await waitFor(() => expect(container.querySelector('[data-doc-heading]')).toHaveTextContent('docs/arch/b.md'));
	await act(async () => { finishSave?.(HttpResponse.json({ success: true })); });
	expect(container.querySelector('[data-doc-heading]')).toHaveTextContent('docs/arch/b.md');
	expect(screen.queryByText('A draft')).not.toBeInTheDocument();
});

it('preserves_markdown_save_and_issue_status_actions', async () => {
	let saved: unknown;
	let status: unknown;
	server.use(
		http.get('/__docs_api/file', () => HttpResponse.json({ success: true, data: { path: 'docs/arch/a.md', absPath: '/repo/docs/arch/a.md', content: '# Original', totalLines: 1, highlightStart: null, highlightEnd: null, sliceStart: 1, sliceEnd: 1, snippet: '# Original' } })),
		http.put('/__docs_api/file', async ({ request }) => { saved = await request.json(); return HttpResponse.json({ success: true }); }),
		http.post('/__docs_api/issue/status', async ({ request }) => { status = await request.json(); return HttpResponse.json({ success: true }); }),
	);
	const issue = { id: 'ISS-101', title: 'Test', type: 'Bug', area: [], priority: 'P1', status: 'Open', planRef: '', datedFile: 'docs/issues/test.md', datedFileStatus: 'Open', bodyMarkdown: '', bullets: [], codeRefs: [] };
	const refresh = vi.fn().mockResolvedValue(undefined);
	const props = { issues: [issue], onClose: vi.fn(), onSelectIssue: vi.fn(), onSelectFileRef: vi.fn(), onSelectPlan: vi.fn(), onRefreshOverview: refresh };
	const { rerender } = render(<ContextInspectorPane target={{ type: 'file', fileRef: 'docs/arch/a.md' }} {...props} />);
	fireEvent.click(await screen.findByRole('button', { name: 'Sửa file' }));
	fireEvent.change(screen.getByRole('textbox'), { target: { value: '# Updated' } });
	fireEvent.click(screen.getByRole('button', { name: 'Lưu vào đĩa' }));
	await waitFor(() => expect(saved).toEqual({ path: 'docs/arch/a.md', content: '# Updated' }));
	expect(await screen.findByText('Updated')).toBeInTheDocument();
	rerender(<ContextInspectorPane target={{ type: 'issue', issueId: 'ISS-101' }} {...props} />);
	fireEvent.click(screen.getByRole('button', { name: 'Planned' }));
	await waitFor(() => expect(status).toEqual({ id: 'ISS-101', status: 'Planned' }));
	expect(refresh).toHaveBeenCalledTimes(2);
});

it('blocks_inspector_editing_while_a_dashboard_draft_exists', async () => {
	server.use(http.get('/__docs_api/file', () => HttpResponse.json({ success: true, data: { path: '.plan/test.md', absPath: '/repo/.plan/test.md', content: '# Plan', totalLines: 1, highlightStart: null, highlightEnd: null, sliceStart: 1, sliceEnd: 1, snippet: '# Plan' } })));
	render(<ContextInspectorPane target={{ type: 'file', fileRef: '.plan/test.md' }} issues={[]} externalEditLocked onClose={vi.fn()} onSelectIssue={vi.fn()} onSelectFileRef={vi.fn()} onSelectPlan={vi.fn()} onRefreshOverview={vi.fn().mockResolvedValue(undefined)} />);
	expect(await screen.findByRole('button', { name: 'Sửa file' })).toBeDisabled();
});

it('reloads_the_inspected_file_after_another_dashboard_write', async () => {
	let content = '# Before';
	server.use(http.get('/__docs_api/file', () => HttpResponse.json({ success: true, data: { path: '.plan/test.md', absPath: '/repo/.plan/test.md', content, totalLines: 1, highlightStart: null, highlightEnd: null, sliceStart: 1, sliceEnd: 1, snippet: content } })));
	const props = { target: { type: 'file' as const, fileRef: '.plan/test.md' }, issues: [], onClose: vi.fn(), onSelectIssue: vi.fn(), onSelectFileRef: vi.fn(), onSelectPlan: vi.fn(), onRefreshOverview: vi.fn().mockResolvedValue(undefined) };
	const { rerender } = render(<ContextInspectorPane {...props} refreshVersion={0} />);
	expect(await screen.findByText('Before')).toBeInTheDocument();
	content = '# After';
	rerender(<ContextInspectorPane {...props} refreshVersion={1} />);
	expect(await screen.findByText('After')).toBeInTheDocument();
	fireEvent.click(screen.getByRole('button', { name: 'Sửa file' }));
	expect(screen.getByRole('textbox')).toHaveValue('# After');
});
