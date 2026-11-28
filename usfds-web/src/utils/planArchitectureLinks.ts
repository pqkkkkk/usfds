import type { ParsedPlan } from '@/api/docsDashboardApi';
import { resolveDocumentLink } from './docsArchitecture';

export interface PlanArchitectureLink {
	label: string;
	path: string;
	evidence: string;
	diagramId?: string;
	invariantId?: string;
	error?: string;
}

const moduleRules = [
	{ pattern: /(?:\/components\/modules\/auth\/|\/services\/auth\/|\/routers\/auth[^/]*\.py)/, path: 'docs/arch/modules/auth-and-access.md', diagramId: 'erd-auth' },
	{ pattern: /(?:\/components\/modules\/data_management\/|\/components\/modules\/feature|\/services\/(?:data_management|features|preprocessing)\/|\/routers\/(?:dataset|feature)[^/]*\.py)/, path: 'docs/arch/modules/data-and-features.md', diagramId: 'erd-data' },
	{ pattern: /(?:\/components\/modules\/model\/|\/services\/training\/|\/routers\/training[^/]*\.py)/, path: 'docs/arch/modules/training-and-models.md', diagramId: 'erd-training' },
	{ pattern: /(?:\/components\/modules\/(?:detection|rule)\/|\/services\/(?:inference|rules?|rule_engine)\/|\/routers\/(?:detection|rule)[^/]*\.py)/, path: 'docs/arch/modules/detection-and-rules.md', diagramId: 'erd-detection' },
	{ pattern: /(?:\/components\/modules\/investigation\/|\/services\/investigation\/|\/routers\/investigation[^/]*\.py)/, path: 'docs/arch/modules/investigation-and-graph.md', diagramId: 'erd-investigation' },
	{ pattern: /(?:\/components\/modules\/reports\/|\/services\/(?:insight|report|insight_report|warehouse)\/|\/routers\/(?:insight|report)[^/]*\.py)/, path: 'docs/arch/modules/insight-and-warehouse.md' },
];

export function getPlanArchitectureLinks(plan: ParsedPlan): {
	declared: PlanArchitectureLink[];
	suggested: PlanArchitectureLink[];
} {
	const declared: PlanArchitectureLink[] = [];
	const suggested: PlanArchitectureLink[] = [];
	const addDeclared = (link: PlanArchitectureLink) => {
		if (!declared.some((item) => item.path === link.path && item.label === link.label)) declared.push(link);
	};
	let inFence = false;
	let inConflictSection = false;
	let inImpactSection = false;
	for (const source of plan.raw.replace(/<!--[\s\S]*?-->/g, '').split(/\r?\n/)) {
		const line = source.trim();
		if (/^```/.test(line)) { inFence = !inFence; continue; }
		if (inFence) continue;
		if (/^##\s/.test(line)) {
			inConflictSection = /^##\s+4\.(?!5)/.test(line);
			inImpactSection = /^##\s+4\.5(?:\s|\.|$)/.test(line);
		}
		const cells = line.startsWith('|') ? line.split('|').slice(1, -1).map((cell) => cell.trim().replace(/[*`]/g, '')) : [];
		const noImpact = inImpactSection && /^(?:no|không|n\/a|—)(?:\s|$)/i.test(cells[1] ?? '');
		for (const match of line.matchAll(/(?:\.\.\/)?docs\/arch\/[^\s`)\]|,;]+/g)) {
			const ref = match[0];
			try {
				const path = resolveDocumentLink(ref.startsWith('../') ? plan.filePath : 'root.md', ref);
				if (!path.startsWith('docs/arch/')) {
					addDeclared({ label: ref, path: ref, evidence: line, error: 'Đường dẫn nằm ngoài thư mục kiến trúc.' });
				} else {
					addDeclared({ label: path, path, evidence: line });
				}
			} catch (err) {
				addDeclared({ label: ref, path: ref, evidence: line, error: err instanceof Error ? err.message : String(err) });
			}
		}
		if (noImpact) continue;
		const invariantIds = new Set(Array.from(line.matchAll(/\bINV-\d{3}\b/g), (match) => match[0]));
		for (const match of line.matchAll(/\bINV-\d{3}(?:\s*(?:\.\.|[–-])\s*(?:INV-)?\d{3})?((?:\s*,\s*\d{3}\b)+)/g)) {
			for (const number of match[1].matchAll(/\d{3}/g)) invariantIds.add(`INV-${number[0]}`);
		}
		for (const match of line.matchAll(/\bINV-(\d{3})\s*(?:\.\.|[–-])\s*(?:INV-)?(\d{3})\b/g)) {
			for (let n = Number(match[1]); n <= Number(match[2]); n++) invariantIds.add(`INV-${String(n).padStart(3, '0')}`);
		}
		for (const id of invariantIds) {
			addDeclared({ label: id, path: 'docs/arch/03-system-invariants.md', invariantId: id, evidence: line });
		}
		const contractContext = /shared\s+contracts?|hợp đồng dùng chung/i.test(line)
			|| (inImpactSection && /\bC[1-5]\b/.test(cells[0] ?? ''));
		if (inConflictSection || /(?:conflict|xung đột)/i.test(line) || !contractContext) continue;
		const ids = new Set(Array.from(line.matchAll(/\bC[1-5]\b/g), (match) => match[0]));
		for (const match of line.matchAll(/\bC([1-5])\s*[–-]\s*C([1-5])\b/g)) {
			for (let n = Number(match[1]); n <= Number(match[2]); n++) ids.add(`C${n}`);
		}
		for (const id of Array.from(ids).sort()) {
			addDeclared({ label: id, path: 'docs/arch/02-data-and-lifecycle-flows.md#3-shared-contracts-c1c5', evidence: line });
		}
	}
	for (const file of plan.filesTable) {
		for (const rule of moduleRules) {
			if (rule.pattern.test(file.file) && !suggested.some((item) => item.path === rule.path)) {
				suggested.push({ label: rule.path, path: rule.path, evidence: file.file, diagramId: rule.diagramId });
			}
		}
	}
	return { declared, suggested };
}
