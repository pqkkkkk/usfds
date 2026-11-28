export interface ArchitectureDiagram {
	id: string;
	group: string;
	title: string;
	path: string;
	heading: string;
	related: { label: string; path: string }[];
}

const runtime = 'docs/arch/01-context-and-runtime.md';
const flows = 'docs/arch/02-data-and-lifecycle-flows.md';
const erd = 'docs/arch/04-data-model-erd.md';
const invariants = { label: 'Nguyên tắc và invariants', path: 'docs/arch/03-system-invariants.md' };
const contracts = { label: 'Shared contracts C1–C5', path: `${flows}#3-shared-contracts-c1c5` };

export const ARCHITECTURE_DIAGRAMS: ArchitectureDiagram[] = [
	{ id: 'context', group: 'Hệ thống', title: 'System context', path: runtime, heading: '1. System context', related: [invariants] },
	{ id: 'packages', group: 'Hệ thống', title: 'Packages & dependencies', path: runtime, heading: '2. Packages & dependency direction', related: [invariants] },
	{ id: 'runtime', group: 'Hệ thống', title: 'Client–server–worker', path: runtime, heading: '4. Client–server–worker runtime & remote compute', related: [invariants] },
	{ id: 'training', group: 'Luồng dữ liệu', title: 'Training', path: flows, heading: '1. Flow A — Training (data prep → features → model registry)', related: [contracts, invariants] },
	{ id: 'inference', group: 'Luồng dữ liệu', title: 'Inference → Investigation → Insight', path: flows, heading: '2. Flow B — Inference → Investigation → Insight', related: [contracts, invariants] },
	{ id: 'erd-auth', group: 'ERD theo module', title: 'Auth, RBAC & projects', path: erd, heading: '1. Auth, RBAC & projects — [module 1](modules/auth-and-access.md)', related: [invariants] },
	{ id: 'erd-data', group: 'ERD theo module', title: 'Data & features', path: erd, heading: '2. Data, system metadata & features — [module 2](modules/data-and-features.md)', related: [contracts] },
	{ id: 'erd-training', group: 'ERD theo module', title: 'Training & model registry', path: erd, heading: '3. Training & model registry — [module 3](modules/training-and-models.md)', related: [contracts] },
	{ id: 'erd-detection', group: 'ERD theo module', title: 'Detection & rules', path: erd, heading: '4. Detection & rules — [module 4](modules/detection-and-rules.md)', related: [contracts] },
	{ id: 'erd-investigation', group: 'ERD theo module', title: 'Investigation', path: erd, heading: '5. Investigation — [module 5](modules/investigation-and-graph.md)', related: [contracts] },
];

export function headingSlug(heading: string): string {
	return heading
		.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
		.replace(/[`*_]/g, '')
		.toLowerCase()
		.replace(/[^\p{L}\p{N}\s-]/gu, '')
		.replace(/\s/g, '-');
}

export function extractArchitectureDiagram(markdown: string, diagram: ArchitectureDiagram): string {
	const lines = markdown.split(/\r?\n/);
	const matches = lines.flatMap((line, index) => line === `## ${diagram.heading}` ? [index] : []);
	if (matches.length === 0) {
		throw new Error(`Không tìm thấy mục "${diagram.heading}" trong ${diagram.path}.`);
	}
	if (matches.length !== 1) {
		throw new Error(`Mục "${diagram.heading}" không duy nhất trong ${diagram.path}.`);
	}
	const start = matches[0] + 1;
	const nextSection = lines.findIndex((line, index) => index >= start && /^#{1,2}\s/.test(line));
	const section = lines.slice(start, nextSection === -1 ? undefined : nextSection).join('\n');
	const blocks = Array.from(section.matchAll(/^```mermaid\s*\n([\s\S]*?)^```\s*$/gm));
	if (blocks.length === 0) {
		throw new Error(`Không tìm thấy sơ đồ Mermaid trong mục "${diagram.heading}".`);
	}
	if (blocks.length !== 1) {
		throw new Error(`Sơ đồ Mermaid trong mục "${diagram.heading}" không duy nhất.`);
	}
	return blocks[0][1].trim();
}

export function resolveDocumentLink(sourcePath: string, href: string): string {
	const [path, fragment] = href.split('#', 2);
	const base = path ? `${sourcePath.slice(0, sourcePath.lastIndexOf('/') + 1)}${path}` : sourcePath;
	const parts: string[] = [];
	for (const part of base.split('/')) {
		if (!part || part === '.') continue;
		if (part === '..') {
			if (!parts.length) throw new Error('Đường dẫn tài liệu nằm ngoài repository.');
			parts.pop();
		} else {
			parts.push(part);
		}
	}
	return `${parts.join('/')}${fragment === undefined ? '' : `#${fragment}`}`;
}
