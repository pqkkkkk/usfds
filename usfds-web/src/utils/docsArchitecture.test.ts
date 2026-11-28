import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ARCHITECTURE_DIAGRAMS, extractArchitectureDiagram } from './docsArchitecture';

describe('architecture source documents', () => {
	it('shows_core_architecture_diagrams_from_source', () => {
		for (const diagram of ARCHITECTURE_DIAGRAMS) {
			const markdown = readFileSync(resolve(process.cwd(), '..', diagram.path), 'utf8');
			expect(extractArchitectureDiagram(markdown, diagram), diagram.id).toMatch(/^(flowchart|erDiagram)/);
		}
	});

	it('reports_missing_or_ambiguous_diagram', () => {
		const diagram = ARCHITECTURE_DIAGRAMS[0];
		expect(() => extractArchitectureDiagram('# Document', diagram)).toThrow(/không tìm thấy/i);
		const section = `## ${diagram.heading}\n\`\`\`mermaid\nflowchart LR\nA --> B\n\`\`\``;
		expect(() => extractArchitectureDiagram(`${section}\n${section}`, diagram)).toThrow(/không duy nhất/i);
		expect(() => extractArchitectureDiagram(`${section}\n\`\`\`mermaid\nflowchart LR\nB --> C\n\`\`\``, diagram)).toThrow(/không duy nhất/i);
	});
});
