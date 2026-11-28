import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/server';
import { docsDashboardApi, type ParsedPlan } from '@/api/docsDashboardApi';
import {
	appendQuestionToPlanMarkdown,
	parsePlanMarkdown,
} from '../../../../viteDocsPlugin';
import { PlanReviewView } from './PlanReviewView';

const mockInitialize = vi.fn();
const mockRender = vi.fn();

vi.mock('mermaid', () => ({
	default: {
		initialize: (...args: unknown[]) => mockInitialize(...args),
		render: (...args: unknown[]) => mockRender(...args),
	},
}));

const SAMPLE_V2_PLAN = `# Plan: Test Feature Plan

> **Task ID:** \`test_feature\` · **Issues:** ISS-101 · **Spec:** \`docs/features/test/suc-spec.md\`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Draft

## 1. Context (facts)
- Existing behavior at \`usfds-core/src/example.py:12\`.

## 2. Goal, scope verdict & non-goals
- **Goal:** Deliver feature X cleanly.
- **Scope:** OK
- **Non-goals / omitted:** None.
- **Assumptions:** SQLite dev env.

## 2.5 Design & Approach (user reviews this section)
### Diagram(s)
\`\`\`mermaid
flowchart LR
    A["Input"] --> B["Output"]
\`\`\`

### Key decisions & contracts
| Area | Decision / Contract | Rationale / Notes |
|---|---|---|
| API / RBAC | \`GET /api/v1/items\` | Protected |

### Edge cases, concurrency & failure handling
- Timeout handled cleanly.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | \`usfds-web/src/App.tsx\` | M1 | append-only |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | \`test_item_list_returns_200\` (\`usfds-server/tests/test_items.py\`) | Seeded item | GET items | Returns 200 | ISS-101 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
- [ ] **M1 — Core & Server** (\`usfds-server\`): API endpoint ready
  - [ ] [tests] Write test from §5
  - [ ] [verify] \`./scripts/test.sh server\`

Checkpoint log (the agent appends one line per finished milestone):
- —

## 7. Review hotspots (filled in after implementation)
- \`usfds-server/src/router.py:42\`: Check auth scope (M1)

## 8. Open questions
- —

## 9. Manual E2E verification (post-merge)
- [ ] Verify flow against real PostgreSQL
- [x] Verify S3 upload works
`;

function renderPlanView(plan: ParsedPlan, wideLayout?: boolean) {
	const onPlanUpdated = vi.fn();
	const onRefreshOverview = vi.fn().mockResolvedValue(undefined);
	const result = render(
		<PlanReviewView
			plan={plan}
			wideLayout={wideLayout}
			onSelectIssue={vi.fn()}
			onSelectFileRef={vi.fn()}
			onSelectPlan={vi.fn()}
			onPlanUpdated={onPlanUpdated}
			onRefreshOverview={onRefreshOverview}
		/>
	);
	return { ...result, onPlanUpdated, onRefreshOverview };
}

describe('parsePlanMarkdown & schema validation', () => {
	it('parses v2 Draft plan cleanly, separating §2 and §2.5 and tracking §9 line numbers', () => {
		const parsed = parsePlanMarkdown(
			SAMPLE_V2_PLAN,
			'test_feature',
			'.plan/test_feature.md',
			'2026-11-22T00:00:00.000Z'
		);

		expect(parsed.validation.status).toBe('valid');
		expect(parsed.validation.schemaVersion).toBe('v2');
		expect(parsed.validation.missingSections).toEqual([]);
		expect(parsed.goal).toBe('Deliver feature X cleanly.');
		expect(parsed.sections['2. Goal, scope verdict & non-goals']).toContain(
			'**Goal:** Deliver feature X cleanly.'
		);
		expect(parsed.sections['2. Goal, scope verdict & non-goals']).not.toContain(
			'flowchart LR'
		);
		expect(parsed.designApproachMarkdown).toContain('flowchart LR');
		expect(parsed.mermaidBlocks).toHaveLength(1);
		expect(parsed.mermaidBlocks[0]).toContain('A["Input"] --> B["Output"]');

		const lines = SAMPLE_V2_PLAN.split('\n');
		const e2eLine1 = lines.findIndex((l) => l.includes('real PostgreSQL')) + 1;
		const e2eLine2 = lines.findIndex((l) => l.includes('S3 upload works')) + 1;
		expect(parsed.manualE2eItems).toHaveLength(2);
		expect(parsed.manualE2eItems[0]).toMatchObject({
			lineNumber: e2eLine1,
			checked: false,
			tag: 'e2e',
			text: 'Verify flow against real PostgreSQL',
		});
		expect(parsed.manualE2eItems[1]).toMatchObject({
			lineNumber: e2eLine2,
			checked: true,
			tag: 'e2e',
			text: 'Verify S3 upload works',
		});
	});

	it('flags Draft plan missing §2.5 and §9 with warning', () => {
		const draftMissingV2 = SAMPLE_V2_PLAN.replace(
			/## 2\.5 Design & Approach[\s\S]*?(?=## 3\. Files)/,
			''
		).replace(/## 9\. Manual E2E[\s\S]*$/, '');

		const parsed = parsePlanMarkdown(
			draftMissingV2,
			'draft_missing_v2',
			'.plan/draft_missing_v2.md',
			'2026-11-22T00:00:00.000Z'
		);

		expect(parsed.validation.status).toBe('warning');
		expect(parsed.validation.schemaVersion).toBe('v2');
		expect(parsed.validation.missingSections).toEqual([
			'2.5 Design & Approach',
			'9. Manual E2E',
		]);
	});

	it('marks completed v1 Done plan (§1–§8) as valid schemaVersion v1', () => {
		const v1Done = SAMPLE_V2_PLAN.replace(
			'**Status:** Draft',
			'**Status:** Done (26-11-21)'
		)
			.replace(/## 2\.5 Design & Approach[\s\S]*?(?=## 3\. Files)/, '')
			.replace(/## 9\. Manual E2E[\s\S]*$/, '');

		const parsed = parsePlanMarkdown(
			v1Done,
			'v1_done_plan',
			'.plan/v1_done_plan.md',
			'2026-11-21T00:00:00.000Z'
		);

		expect(parsed.validation.status).toBe('valid');
		expect(parsed.validation.schemaVersion).toBe('v1');
		expect(parsed.validation.missingSections).toEqual([]);
	});

	it('detects legacy plan without v1/v2 sections or headers', () => {
		const legacy = `# Feature management plan\n\n## Status\n- To do\n`;
		const parsed = parsePlanMarkdown(
			legacy,
			'feature_management',
			'.plan/feature_management.md',
			'2026-11-17T00:00:00.000Z'
		);

		expect(parsed.validation.status).toBe('legacy');
		expect(parsed.validation.schemaVersion).toBe('legacy');
	});

	it('inserts open questions inside §8 before §9 instead of appending to EOF', () => {
		const afterFirst = appendQuestionToPlanMarkdown(
			SAMPLE_V2_PLAN,
			'First question?'
		);
		expect(afterFirst).toContain('## 8. Open questions\n- First question?\n\n## 9. Manual E2E');

		const afterSecond = appendQuestionToPlanMarkdown(
			afterFirst,
			'Second question?'
		);
		expect(afterSecond).toContain(
			'## 8. Open questions\n- First question?\n- Second question?\n\n## 9. Manual E2E'
		);
	});

	it('strips inline HTML comments from header status fields', () => {
		const withComment = SAMPLE_V2_PLAN.replace(
			'**Status:** Draft',
			'**Status:** Done (26-11-22) <!-- Approved (26-11-22) -->'
		);
		const parsed = parsePlanMarkdown(
			withComment,
			'commented_status',
			'.plan/commented_status.md',
			'2026-11-22T00:00:00.000Z'
		);
		expect(parsed.status).toBe('Done (26-11-22)');
		expect(parsed.status).not.toContain('<!--');
	});
});

describe('PlanReviewView & MermaidDiagram', () => {
	beforeEach(() => {
		mockInitialize.mockReset();
		mockRender.mockReset();
		mockRender.mockImplementation(async (_id: string, code: string) => {
			if (code.includes('INVALID_MERMAID')) {
				throw new Error('Syntax error in graph');
			}
			return {
				svg: '<svg data-testid="mock-mermaid-svg"><text>Rendered</text></svg>',
			};
		});
	});

	it('renders Review Mode & Agent Spec tabs without toggle-all button and collapses sections by default', () => {
		const plan = parsePlanMarkdown(
			SAMPLE_V2_PLAN,
			'test_feature',
			'.plan/test_feature.md',
			'2026-11-22T00:00:00.000Z'
		);
		renderPlanView(plan);

		expect(screen.getByRole('button', { name: /Review Mode/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Agent Spec/i })).toBeInTheDocument();
		expect(screen.queryByText(/Mở tất cả các mục/i)).not.toBeInTheDocument();
		expect(screen.getByText('Chuẩn Template v2 (§1–§9)')).toBeInTheDocument();

		// All sections collapsed initially
		expect(screen.queryByText('Deliver feature X cleanly.')).not.toBeInTheDocument();
		expect(screen.queryByTestId('mock-mermaid-svg')).not.toBeInTheDocument();
		expect(screen.queryByText('test_item_list_returns_200')).not.toBeInTheDocument();
	});

	it('expands §2.5 to render Mermaid SVG, toggles raw source, and switches cleanly to Agent Spec', async () => {
		const plan = parsePlanMarkdown(
			SAMPLE_V2_PLAN,
			'test_feature',
			'.plan/test_feature.md',
			'2026-11-22T00:00:00.000Z'
		);
		renderPlanView(plan);

		// Expand §2.5 Design & Approach
		fireEvent.click(
			screen.getByRole('button', { name: /§2\.5\. Thiết kế & Hướng tiếp cận/i })
		);

		expect(await screen.findByTestId('mock-mermaid-svg')).toBeInTheDocument();
		expect(mockInitialize).toHaveBeenCalledWith(
			expect.objectContaining({
				startOnLoad: false,
				securityLevel: 'strict',
				theme: 'dark',
			})
		);

		// Toggle source view
		fireEvent.click(screen.getByRole('button', { name: /Xem mã/i }));
		expect(screen.queryByTestId('mock-mermaid-svg')).not.toBeInTheDocument();
		expect(screen.getByText(/A\["Input"\] --> B\["Output"\]/)).toBeInTheDocument();

		// Switch back to diagram
		fireEvent.click(screen.getByRole('button', { name: /Xem sơ đồ/i }));
		expect(await screen.findByTestId('mock-mermaid-svg')).toBeInTheDocument();

		// Switch to Agent Spec tab
		fireEvent.click(screen.getByRole('button', { name: /Agent Spec/i }));
		expect(
			screen.getByRole('button', { name: /§1\. Hiện trạng & Nguyên nhân gốc/i })
		).toBeInTheDocument();
		expect(
			screen.getByRole('button', { name: /§3\. Danh sách Files tác động/i })
		).toBeInTheDocument();
		expect(
			screen.getByRole('button', { name: /§4\. Ma trận Phụ thuộc & Xung đột/i })
		).toBeInTheDocument();
		expect(
			screen.getByRole('button', { name: /§6\. Tiến độ Milestones & Checklist/i })
		).toBeInTheDocument();
	});

	it('preserves_mermaid_error_and_source', async () => {
		const badMermaidPlan = parsePlanMarkdown(
			SAMPLE_V2_PLAN.replace('A["Input"] --> B["Output"]', 'INVALID_MERMAID ???'),
			'bad_mermaid',
			'.plan/bad_mermaid.md',
			'2026-11-22T00:00:00.000Z'
		);
		renderPlanView(badMermaidPlan);

		fireEvent.click(
			screen.getByRole('button', { name: /§2\.5\. Thiết kế & Hướng tiếp cận/i })
		);

		expect(
			await screen.findByText(/Lỗi cú pháp Mermaid: Syntax error in graph/i)
		).toBeInTheDocument();
		expect(screen.getByText(/INVALID_MERMAID \?\?\?/)).toBeInTheDocument();
	});

	it('toggles §9 Manual E2E checkbox via docsDashboardApi.togglePlanCheckbox with exact line number', async () => {
		const plan = parsePlanMarkdown(
			SAMPLE_V2_PLAN,
			'test_feature',
			'.plan/test_feature.md',
			'2026-11-22T00:00:00.000Z'
		);
		const expectedLine = plan.manualE2eItems[0].lineNumber;
		const updatedPlan: ParsedPlan = {
			...plan,
			manualE2eItems: plan.manualE2eItems.map((item, idx) =>
				idx === 0 ? { ...item, checked: true } : item
			),
		};

		let capturedBody: Record<string, unknown> | null = null;
		server.use(
			http.post('/__docs_api/plan/action', async ({ request }) => {
				capturedBody = (await request.json()) as Record<string, unknown>;
				return HttpResponse.json({ success: true, data: updatedPlan });
			})
		);
		const toggleSpy = vi.spyOn(docsDashboardApi, 'togglePlanCheckbox');

		const { onPlanUpdated } = renderPlanView(plan);

		fireEvent.click(
			screen.getByRole('button', { name: /§9\. Kiểm thử E2E thủ công/i })
		);
		fireEvent.click(
			screen.getByRole('button', {
				name: `Đánh dấu E2E dòng ${expectedLine}`,
			})
		);

		await waitFor(() => {
			expect(toggleSpy).toHaveBeenCalledWith('test_feature', expectedLine, true);
			expect(onPlanUpdated).toHaveBeenCalledWith(updatedPlan);
		});
		expect(capturedBody).toEqual({
			slug: 'test_feature',
			action: 'toggle_checkbox',
			lineNumber: expectedLine,
			checked: true,
		});
		toggleSpy.mockRestore();
	});

	it('uses max-w-5xl by default and switches to max-w-6xl when wideLayout is true', () => {
		const plan = parsePlanMarkdown(
			SAMPLE_V2_PLAN,
			'test_feature',
			'.plan/test_feature.md',
			'2026-11-22T00:00:00.000Z'
		);

		const { container, rerender } = render(
			<PlanReviewView
				plan={plan}
				onSelectIssue={vi.fn()}
				onSelectFileRef={vi.fn()}
				onSelectPlan={vi.fn()}
				onPlanUpdated={vi.fn()}
				onRefreshOverview={vi.fn().mockResolvedValue(undefined)}
			/>
		);
		expect(container.querySelector('.max-w-5xl')).toBeInTheDocument();
		expect(container.querySelector('.max-w-6xl')).not.toBeInTheDocument();

		rerender(
			<PlanReviewView
				plan={plan}
				wideLayout={true}
				onSelectIssue={vi.fn()}
				onSelectFileRef={vi.fn()}
				onSelectPlan={vi.fn()}
				onPlanUpdated={vi.fn()}
				onRefreshOverview={vi.fn().mockResolvedValue(undefined)}
			/>
		);
		expect(container.querySelector('.max-w-6xl')).toBeInTheDocument();
		expect(container.querySelector('.max-w-5xl')).not.toBeInTheDocument();
	});
});
