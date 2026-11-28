import { describe, expect, it } from 'vitest';
import { parsePlanMarkdown } from '../../viteDocsPlugin';
import { getPlanArchitectureLinks } from './planArchitectureLinks';

function plan(raw: string) {
	return parsePlanMarkdown(raw, 'test', '.plan/test.md', '');
}

describe('plan architecture links', () => {
	it('distinguishes_declared_architecture_references_from_suggestions', () => {
		const result = getPlanArchitectureLinks(plan(`# Test
## 1. Context
Xem \`docs/arch/modules/data-and-features.md\`.
## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | \`usfds-web/src/components/modules/investigation/CaseQueueView.tsx\` | M1 | — |`));
		expect(result.declared).toContainEqual(expect.objectContaining({ path: 'docs/arch/modules/data-and-features.md' }));
		expect(result.suggested).toContainEqual(expect.objectContaining({
			path: 'docs/arch/modules/investigation-and-graph.md',
			evidence: expect.stringContaining('CaseQueueView.tsx'),
			diagramId: 'erd-investigation',
		}));
	});

	it('does_not_confuse_conflict_ids_and_shared_contracts', () => {
		const result = getPlanArchitectureLinks(plan(`# Test
## 4. Dependencies
| # | Check | Answer |
|---|---|---|
| C1 | Modified files owned? | Yes |
| C4 | Public contract? | No |
## 4.5 System Invariant
| Shared Contracts (\`C1–C5\`) | Không | Không đổi |
| Shared Contract C4 | Có | Thay đổi nhãn |
| INV-009 | Có | Kiểm tra |`));
		expect(result.declared.filter((link) => /^C\d$/.test(link.label)).map((link) => link.label)).toEqual(['C4']);
		expect(result.declared).toContainEqual(expect.objectContaining({ label: 'INV-009' }));
	});

	it('does_not_treat_a_conflict_disclaimer_as_a_shared_contract_reference', () => {
		const result = getPlanArchitectureLinks(plan('# Test\nC1–C5 trong bảng xung đột không phải shared contracts.'));
		expect(result.declared).toEqual([]);
	});

	it('handles_legacy_missing_and_unknown_architecture_references', () => {
		const result = getPlanArchitectureLinks(plan('# Legacy\n\nNo file table here.'));
		expect(result).toEqual({ declared: [], suggested: [] });
	});

	it('expands explicit invariant ranges and rejects paths outside architecture docs', () => {
		const result = getPlanArchitectureLinks(plan(`# Test
## 4.5 Impact
| INV-001..003 | Có | Review |
| INV-004 | Không | N/A |
\`docs/arch/../../README.md\``));
		expect(result.declared.filter((link) => link.invariantId).map((link) => link.label)).toEqual(['INV-001', 'INV-002', 'INV-003']);
		expect(result.declared.find((link) => link.error)).toBeDefined();
	});

	it('expands impact table invariant lists and shared contract ranges', () => {
		const result = getPlanArchitectureLinks(plan(`# Test
## 4.5 Impact
| C1–C5, INV-009,010,013, INV-005..007,016 | Có | Review |`));
		expect(result.declared.filter((link) => /^C\d$/.test(link.label)).map((link) => link.label)).toEqual(['C1', 'C2', 'C3', 'C4', 'C5']);
		expect(result.declared.filter((link) => link.invariantId).map((link) => link.label).sort()).toEqual(['INV-005', 'INV-006', 'INV-007', 'INV-009', 'INV-010', 'INV-013', 'INV-016']);
	});

	it('suggests_modules_for_known_backend_service_paths', () => {
		const result = getPlanArchitectureLinks(plan(`# Test
## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | \`usfds-core/src/usfds_core/services/warehouse/project_warehouse.py\` | M1 | — |
| modify | \`usfds-core/src/usfds_core/services/preprocessing/service.py\` | M1 | — |
| modify | \`usfds-core/src/usfds_core/services/rule_engine/service.py\` | M1 | — |`));
		expect(result.suggested.map((link) => link.path)).toEqual([
			'docs/arch/modules/insight-and-warehouse.md',
			'docs/arch/modules/data-and-features.md',
			'docs/arch/modules/detection-and-rules.md',
		]);
	});
});
