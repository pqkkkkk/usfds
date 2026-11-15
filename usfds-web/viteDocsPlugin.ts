import fs from 'node:fs';
import path from 'node:path';
import type { Plugin } from 'vite';
import type { IncomingMessage, ServerResponse } from 'node:http';

export interface ParsedAcceptanceTest {
	milestone: string;
	test: string;
	given: string;
	when: string;
	then: string;
	covers: string;
}

export interface ParsedPlanFileEntry {
	action: string;
	file: string;
	milestone: string;
	note: string;
}

export interface ParsedConflictCheck {
	id: string;
	check: string;
	answer: string;
}

export interface ParsedChecklistItem {
	lineNumber: number;
	checked: boolean;
	tag: string;
	text: string;
	indent: number;
}

export interface ParsedMilestoneGroup {
	id: string;
	title: string;
	lineNumber: number;
	checked: boolean;
	items: ParsedChecklistItem[];
}

export interface ParsedHotspot {
	raw: string;
	codeRefs: string[];
	milestone: string;
	description: string;
}

export interface SchemaValidationResult {
	status: 'valid' | 'warning' | 'legacy';
	missingSections: string[];
	missingHeaderFields: string[];
	messages: string[];
}

export interface ParsedPlan {
	slug: string;
	filePath: string;
	title: string;
	taskId: string;
	issues: string[];
	spec: string;
	conflictVerdict: string;
	status: string;
	scopeVerdict: string;
	goal: string;
	sections: Record<string, string>;
	filesTable: ParsedPlanFileEntry[];
	conflictsTable: ParsedConflictCheck[];
	acceptanceTests: ParsedAcceptanceTest[];
	milestones: ParsedMilestoneGroup[];
	checkpointLogs: string[];
	hotspots: ParsedHotspot[];
	openQuestions: string[];
	validation: SchemaValidationResult;
	updatedAt: string;
	raw: string;
}

export interface ParsedIssue {
	id: string;
	title: string;
	type: string;
	area: string[];
	priority: string;
	status: string;
	planRef: string;
	datedFile: string;
	datedFileStatus: string;
	bodyMarkdown: string;
	bullets: { label: string; content: string }[];
	codeRefs: string[];
	syncWarning?: string;
}

function readBody(req: IncomingMessage): Promise<string> {
	return new Promise((resolve, reject) => {
		let data = '';
		req.on('data', (chunk) => {
			data += chunk;
		});
		req.on('end', () => resolve(data));
		req.on('error', reject);
	});
}

function sendJson(res: ServerResponse, status: number, payload: unknown): void {
	res.statusCode = status;
	res.setHeader('Content-Type', 'application/json; charset=utf-8');
	res.end(JSON.stringify(payload));
}

function parseMarkdownTable(markdown: string): string[][] {
	const lines = markdown
		.split(/\r?\n/)
		.map((l) => l.trim())
		.filter((l) => l.startsWith('|') && l.endsWith('|'));
	if (lines.length < 2) {
		return [];
	}
	const rows: string[][] = [];
	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		// Skip separator line like |---|---|
		if (/^\|[\s\-:|]+\|$/.test(line)) {
			continue;
		}
		const cells = line
			.slice(1, -1)
			.split('|')
			.map((c) => c.trim());
		rows.push(cells);
	}
	return rows;
}

function extractCodeRefs(text: string): string[] {
	const refs = new Set<string>();
	const regex = /`((?:usfds-[a-z0-9_-]+\/|docs\/|\.plan\/|\.claude\/|scripts\/|deploy\/|database\/|[a-zA-Z0-9_/-]+\.(?:py|ts|tsx|md|sh|yml|json))[^`\s]*)`/g;
	let match: RegExpExecArray | null = regex.exec(text);
	while (match !== null) {
		refs.add(match[1]);
		match = regex.exec(text);
	}
	return Array.from(refs);
}

function parsePlanFile(repoRoot: string, absPath: string): ParsedPlan {
	const raw = fs.readFileSync(absPath, 'utf-8');
	const stat = fs.statSync(absPath);
	const slug = path.basename(absPath, '.md');
	const relPath = path.relative(repoRoot, absPath).replace(/\\/g, '/');
	const lines = raw.split(/\r?\n/);

	let title = slug;
	for (const line of lines) {
		const m = line.match(/^#\s+(?:Plan:\s*)?(.+)$/);
		if (m) {
			title = m[1].trim();
			break;
		}
	}

	// Parse header blockquote lines (> **Task ID:** ...)
	const headerBlock = lines
		.slice(0, 15)
		.filter((l) => l.trim().startsWith('>'))
		.join(' ');

	const extractHeaderField = (label: string): string => {
		const pattern = new RegExp(`\\*\\*${label}:\\*\\*\\s*([^·\\n>]+)`, 'i');
		const m = headerBlock.match(pattern);
		return m ? m[1].trim().replace(/^`|`$/g, '') : '';
	};

	const taskId = extractHeaderField('Task ID') || slug;
	const issuesRaw = extractHeaderField('Issues');
	const issueMatches = issuesRaw.match(/ISS-\d+/g) || raw.slice(0, 500).match(/ISS-\d+/g) || [];
	const issues = Array.from(new Set(issueMatches));
	const spec = extractHeaderField('Spec');
	const conflictVerdict = extractHeaderField('Conflict verdict');
	const status = extractHeaderField('Status');

	// Split sections by ## heading
	const sections: Record<string, string> = {};
	let currentHeading = '__header__';
	let currentBuffer: string[] = [];

	for (const line of lines) {
		const hMatch = line.match(/^##\s+(.+)$/);
		if (hMatch) {
			sections[currentHeading] = currentBuffer.join('\n').trim();
			currentHeading = hMatch[1].trim();
			currentBuffer = [];
		} else {
			currentBuffer.push(line);
		}
	}
	sections[currentHeading] = currentBuffer.join('\n').trim();

	const findSection = (numPrefix: string, keyword: string): string => {
		for (const [k, v] of Object.entries(sections)) {
			if (k.startsWith(numPrefix) || k.toLowerCase().includes(keyword.toLowerCase())) {
				return v;
			}
		}
		return '';
	};

	const sec2 = findSection('2.', 'Goal');
	const goalMatch = sec2.match(/\*\*Goal:\*\*\s*(.+)/i);
	const scopeMatch = sec2.match(/\*\*Scope:\*\*\s*(.+)/i);
	const goal = goalMatch ? goalMatch[1].trim() : '';
	const scopeVerdict = scopeMatch ? scopeMatch[1].trim() : '';

	// Parse §3 Files table
	const sec3 = findSection('3.', 'Files');
	const filesRows = parseMarkdownTable(sec3);
	const filesTable: ParsedPlanFileEntry[] =
		filesRows.length > 1
			? filesRows.slice(1).map((r) => ({
					action: (r[0] || '').replace(/`/g, ''),
					file: (r[1] || '').replace(/`/g, ''),
					milestone: r[2] || '',
					note: r[3] || '',
				}))
			: [];

	// Parse §4 Dependencies & conflicts table
	const sec4 = findSection('4.', 'Dependencies');
	const conflictRows = parseMarkdownTable(sec4);
	const conflictsTable: ParsedConflictCheck[] =
		conflictRows.length > 1
			? conflictRows.slice(1).map((r) => ({
					id: r[0] || '',
					check: r[1] || '',
					answer: r[2] || '',
				}))
			: [];

	// Parse §5 Acceptance tests table
	const sec5 = findSection('5.', 'Acceptance tests');
	const testRows = parseMarkdownTable(sec5);
	const acceptanceTests: ParsedAcceptanceTest[] =
		testRows.length > 1
			? testRows.slice(1).map((r) => ({
					milestone: r[0] || '',
					test: r[1] || '',
					given: r[2] || '',
					when: r[3] || '',
					then: r[4] || '',
					covers: r[5] || '',
				}))
			: [];

	// Parse §6 Milestones & to-do with exact file line numbers for interactive checkbox toggling
	const milestones: ParsedMilestoneGroup[] = [];
	const checkpointLogs: string[] = [];
	let inSec6 = false;
	let inCheckpointLog = false;
	let currentGroup: ParsedMilestoneGroup | null = null;

	for (let idx = 0; idx < lines.length; idx++) {
		const line = lines[idx];
		const hMatch = line.match(/^##\s+(.+)$/);
		if (hMatch) {
			const hTitle = hMatch[1].trim();
			inSec6 = hTitle.startsWith('6.') || hTitle.toLowerCase().includes('milestones');
			inCheckpointLog = false;
			continue;
		}
		if (!inSec6) {
			continue;
		}
		if (/^Checkpoint log/i.test(line.trim())) {
			inCheckpointLog = true;
			continue;
		}
		if (inCheckpointLog) {
			const logMatch = line.match(/^\s*-\s+(.+)$/);
			if (logMatch) {
				checkpointLogs.push(logMatch[1].trim());
			}
			continue;
		}
		const cbMatch = line.match(/^(\s*)-\s+\[([ xX])\]\s+(.+)$/);
		if (cbMatch) {
			const indent = cbMatch[1].length;
			const checked = cbMatch[2].toLowerCase() === 'x';
			const text = cbMatch[3].trim();
			const mHeaderMatch = text.match(/^\*\*(M\d+)[^*]*\*\*(.*)$/);
			if (indent === 0 || mHeaderMatch) {
				const mId = mHeaderMatch ? mHeaderMatch[1] : `M${milestones.length + 1}`;
				currentGroup = {
					id: mId,
					title: text.replace(/\*\*/g, ''),
					lineNumber: idx + 1,
					checked,
					items: [],
				};
				milestones.push(currentGroup);
			} else {
				const tagMatch = text.match(/^\[([a-zA-Z0-9_-]+)\]\s*(.+)$/);
				const item: ParsedChecklistItem = {
					lineNumber: idx + 1,
					checked,
					tag: tagMatch ? tagMatch[1] : 'task',
					text: tagMatch ? tagMatch[2] : text,
					indent,
				};
				if (!currentGroup) {
					currentGroup = {
						id: 'M1',
						title: 'Milestones',
						lineNumber: idx + 1,
						checked: false,
						items: [],
					};
					milestones.push(currentGroup);
				}
				currentGroup.items.push(item);
			}
		}
	}

	// Parse §7 Review hotspots
	const sec7 = findSection('7.', 'Review hotspots');
	const hotspots: ParsedHotspot[] = [];
	for (const line of sec7.split(/\r?\n/)) {
		const m = line.match(/^\s*-\s+(.+)$/);
		if (m && m[1].trim() !== '—') {
			const itemText = m[1].trim();
			const codeRefs = extractCodeRefs(itemText);
			const mMatch = itemText.match(/\((M\d+)\)/);
			hotspots.push({
				raw: itemText,
				codeRefs,
				milestone: mMatch ? mMatch[1] : '',
				description: itemText,
			});
		}
	}

	// Parse §8 Open questions
	const sec8 = findSection('8.', 'Open questions');
	const openQuestions: string[] = [];
	for (const line of sec8.split(/\r?\n/)) {
		const m = line.match(/^\s*-\s+(.+)$/);
		if (m && m[1].trim() !== '—') {
			openQuestions.push(m[1].trim());
		}
	}

	// Schema Validation against template.md
	const requiredSections = [
		'1. Context',
		'2. Goal',
		'3. Files',
		'4. Dependencies',
		'5. Acceptance tests',
		'6. Milestones',
		'7. Review hotspots',
		'8. Open questions',
	];
	const sectionKeys = Object.keys(sections);
	const missingSections = requiredSections.filter(
		(reqSec) =>
			!sectionKeys.some((k) =>
				k.toLowerCase().startsWith(reqSec.split(' ')[0].toLowerCase())
			)
	);
	const missingHeaderFields: string[] = [];
	if (!extractHeaderField('Task ID')) {
		missingHeaderFields.push('Task ID');
	}
	if (!extractHeaderField('Issues')) {
		missingHeaderFields.push('Issues');
	}
	if (!conflictVerdict) {
		missingHeaderFields.push('Conflict verdict');
	}
	if (!status) {
		missingHeaderFields.push('Status');
	}

	let validationStatus: 'valid' | 'warning' | 'legacy' = 'valid';
	const messages: string[] = [];

	if (slug === 'BOARD' || slug === 'parallel_agent_setup') {
		validationStatus = 'valid';
	} else if (missingSections.length >= 5 && missingHeaderFields.length >= 3) {
		validationStatus = 'legacy';
		messages.push('Plan cũ (trước chuẩn template 26-11-14).');
	} else if (missingSections.length > 0 || missingHeaderFields.length > 0) {
		validationStatus = 'warning';
		if (missingHeaderFields.length > 0) {
			messages.push(`Thiếu trường header: ${missingHeaderFields.join(', ')}`);
		}
		if (missingSections.length > 0) {
			messages.push(`Thiếu mục: ${missingSections.join(', ')}`);
		}
	}

	return {
		slug,
		filePath: relPath,
		title,
		taskId,
		issues,
		spec,
		conflictVerdict,
		status: status || (validationStatus === 'legacy' ? 'Legacy' : 'Draft'),
		scopeVerdict: scopeVerdict || '—',
		goal,
		sections,
		filesTable,
		conflictsTable,
		acceptanceTests,
		milestones,
		checkpointLogs,
		hotspots,
		openQuestions,
		validation: {
			status: validationStatus,
			missingSections,
			missingHeaderFields,
			messages,
		},
		updatedAt: stat.mtime.toISOString(),
		raw,
	};
}

function parseIssues(repoRoot: string): {
	issues: ParsedIssue[];
	linterWarnings: string[];
} {
	const issuesDir = path.join(repoRoot, 'docs', 'issues');
	const readmePath = path.join(issuesDir, 'README.md');
	const linterWarnings: string[] = [];

	if (!fs.existsSync(readmePath)) {
		return { issues: [], linterWarnings: ['Không tìm thấy docs/issues/README.md'] };
	}

	const readmeRaw = fs.readFileSync(readmePath, 'utf-8');
	const indexRows = parseMarkdownTable(readmeRaw);

	// Parse all dated files MM-DD-YYYY.md
	const datedEntries = new Map<
		string,
		{
			datedFile: string;
			title: string;
			status: string;
			bodyMarkdown: string;
			bullets: { label: string; content: string }[];
			codeRefs: string[];
		}
	>();

	const files = fs
		.readdirSync(issuesDir)
		.filter((f) => f.endsWith('.md') && f !== 'README.md');

	for (const file of files) {
		const fullPath = path.join(issuesDir, file);
		const content = fs.readFileSync(fullPath, 'utf-8');
		const lines = content.split(/\r?\n/);

		let currentId = '';
		let currentTitle = '';
		let currentLines: string[] = [];

		const flushEntry = () => {
			if (!currentId) {
				return;
			}
			const bodyMarkdown = currentLines.join('\n').trim();
			const bullets: { label: string; content: string }[] = [];
			let statusVal = '';

			for (const bLine of currentLines) {
				const bMatch = bLine.match(/^\s*-\s+\*\*([^:*]+):\*\*\s*(.+)$/);
				if (bMatch) {
					const label = bMatch[1].trim();
					const val = bMatch[2].replace(/<!--.*?-->/g, '').trim();
					bullets.push({ label, content: val });
					if (label.toLowerCase() === 'status') {
						statusVal = val;
					}
				}
			}

			datedEntries.set(currentId, {
				datedFile: `docs/issues/${file}`,
				title: currentTitle,
				status: statusVal,
				bodyMarkdown,
				bullets,
				codeRefs: extractCodeRefs(bodyMarkdown),
			});
		};

		for (const line of lines) {
			const hMatch = line.match(/^##\s+(ISS-\d+):\s*(.+)$/);
			if (hMatch) {
				flushEntry();
				currentId = hMatch[1].trim();
				currentTitle = hMatch[2].trim();
				currentLines = [];
			} else if (currentId) {
				if (/^##\s+[^I]/.test(line) || line.trim() === '---') {
					continue;
				}
				currentLines.push(line);
			}
		}
		flushEntry();
	}

	const issues: ParsedIssue[] = [];
	const seenInReadme = new Set<string>();

	for (let i = 1; i < indexRows.length; i++) {
		const row = indexRows[i];
		if (row.length < 8) {
			continue;
		}
		const id = row[0].trim();
		seenInReadme.add(id);
		const title = row[1].trim();
		const type = row[2].trim();
		const area = row[3]
			.split(',')
			.map((a) => a.trim())
			.filter(Boolean);
		const priority = row[4].replace(/\*\*/g, '').trim();
		const status = row[5].replace(/<!--.*?-->/g, '').trim();
		const planCell = row[6].replace(/<!--.*?-->/g, '').trim();
		const fileCell = row[7].trim();

		const planLinkMatch = planCell.match(/\(([^)]+)\)/);
		const planSlugMatch = planCell.match(/\[([^\]]+)\]/);
		const planRef = planSlugMatch
			? planSlugMatch[1]
			: planLinkMatch
				? path.basename(planLinkMatch[1], '.md')
				: planCell === '—'
					? ''
					: planCell;

		const fileLinkMatch = fileCell.match(/\(([^)]+)\)/);
		const datedFileFromIndex = fileLinkMatch
			? `docs/issues/${fileLinkMatch[1]}`
			: '';

		const detail = datedEntries.get(id);
		let syncWarning: string | undefined;

		if (!detail) {
			syncWarning = `Có trong README.md nhưng không tìm thấy mục ## ${id} trong ${datedFileFromIndex}`;
			linterWarnings.push(`${id}: ${syncWarning}`);
		} else {
			const normIndexStatus = status.toLowerCase().split('(')[0].trim();
			const normDatedStatus = detail.status.toLowerCase().split('(')[0].split('—')[0].trim();
			if (
				normIndexStatus &&
				normDatedStatus &&
				!normDatedStatus.includes(normIndexStatus) &&
				!normIndexStatus.includes(normDatedStatus)
			) {
				syncWarning = `Lệch Status: README="${status}" vs File ngày="${detail.status}"`;
				linterWarnings.push(`${id}: ${syncWarning}`);
			}
		}

		issues.push({
			id,
			title: detail?.title || title,
			type,
			area,
			priority,
			status,
			planRef,
			datedFile: detail?.datedFile || datedFileFromIndex,
			datedFileStatus: detail?.status || '',
			bodyMarkdown: detail?.bodyMarkdown || '',
			bullets: detail?.bullets || [],
			codeRefs: detail?.codeRefs || [],
			syncWarning,
		});
	}

	for (const [id, detail] of datedEntries.entries()) {
		if (!seenInReadme.has(id)) {
			const warn = `${id} có trong ${detail.datedFile} nhưng chưa đăng ký trong docs/issues/README.md`;
			linterWarnings.push(warn);
			issues.push({
				id,
				title: detail.title,
				type: 'unknown',
				area: [],
				priority: 'P2',
				status: detail.status || 'Open',
				planRef: '',
				datedFile: detail.datedFile,
				datedFileStatus: detail.status,
				bodyMarkdown: detail.bodyMarkdown,
				bullets: detail.bullets,
				codeRefs: detail.codeRefs,
				syncWarning: warn,
			});
		}
	}

	return { issues, linterWarnings };
}

function listMarkdownFilesRecursive(repoRoot: string, dirRel: string): {
	path: string;
	name: string;
	category: string;
	updatedAt: string;
}[] {
	const results: {
		path: string;
		name: string;
		category: string;
		updatedAt: string;
	}[] = [];
	const targetDir = path.join(repoRoot, dirRel);
	if (!fs.existsSync(targetDir)) {
		return results;
	}

	const walk = (currentDir: string) => {
		const entries = fs.readdirSync(currentDir, { withFileTypes: true });
		for (const entry of entries) {
			const full = path.join(currentDir, entry.name);
			if (entry.isDirectory()) {
				walk(full);
			} else if (entry.isFile() && entry.name.endsWith('.md')) {
				const rel = path.relative(repoRoot, full).replace(/\\/g, '/');
				const stat = fs.statSync(full);
				const parts = rel.split('/');
				const category = parts.length > 2 ? parts[1] : 'root';
				results.push({
					path: rel,
					name: entry.name,
					category,
					updatedAt: stat.mtime.toISOString(),
				});
			}
		}
	};
	walk(targetDir);
	return results;
}

export function usfdsDocsDashboardPlugin(): Plugin {
	const repoRoot = path.resolve(process.cwd(), '..');

	return {
		name: 'usfds-docs-dashboard-api',
		configureServer(server) {
			server.middlewares.use(async (req, res, next) => {
				if (!req.url || !req.url.startsWith('/__docs_api/')) {
					return next();
				}

				const urlObj = new URL(req.url, 'http://localhost');
				const pathname = urlObj.pathname;

				try {
					// 1. GET /__docs_api/overview
					if (req.method === 'GET' && pathname === '/__docs_api/overview') {
						const planDir = path.join(repoRoot, '.plan');
						const boardPath = path.join(planDir, 'BOARD.md');
						const boardRaw = fs.existsSync(boardPath)
							? fs.readFileSync(boardPath, 'utf-8')
							: '';

						// Parse BOARD.md tables
						const boardSections = boardRaw.split(/^##\s+/m);
						let phase0Rows: string[][] = [];
						let activeTaskRows: string[][] = [];
						for (const sec of boardSections) {
							if (sec.startsWith('Phase 0')) {
								phase0Rows = parseMarkdownTable(sec).slice(1);
							} else if (sec.startsWith('Tasks')) {
								activeTaskRows = parseMarkdownTable(sec).slice(1);
							}
						}

						const planFiles = fs.existsSync(planDir)
							? fs
									.readdirSync(planDir)
									.filter(
										(f) =>
											f.endsWith('.md') &&
											f !== 'BOARD.md'
									)
							: [];

						const plans = planFiles
							.map((f) => parsePlanFile(repoRoot, path.join(planDir, f)))
							.sort((a, b) => {
								// Put non-legacy active/draft plans first
								if (a.validation.status !== 'legacy' && b.validation.status === 'legacy') {
									return -1;
								}
								if (a.validation.status === 'legacy' && b.validation.status !== 'legacy') {
									return 1;
								}
								return b.updatedAt.localeCompare(a.updatedAt);
							});

						const { issues, linterWarnings } = parseIssues(repoRoot);
						const specFiles = listMarkdownFilesRecursive(repoRoot, 'docs');

						return sendJson(res, 200, {
							success: true,
							data: {
								repoRoot: repoRoot.replace(/\\/g, '/'),
								board: {
									raw: boardRaw,
									phase0Rows,
									activeTaskRows,
								},
								plans,
								issues,
								issueLinterWarnings: linterWarnings,
								docsFiles: specFiles,
							},
						});
					}

					// 2. GET /__docs_api/file?path=...&startLine=...&endLine=...
					if (req.method === 'GET' && pathname === '/__docs_api/file') {
						const rawTarget = urlObj.searchParams.get('path') || '';
						// Clean up file:/// or line suffixes if passed
						const cleaned = rawTarget
							.replace(/^file:\/\/\/[a-zA-Z]:\/.*?\/usfds\//, '')
							.replace(/^file:\/\/\/.*?\/usfds\//, '')
							.replace(/^\//, '');

						// Extract :line-line or #Lline-Lline if embedded
						let filePart = cleaned;
						let reqStart = Number(urlObj.searchParams.get('startLine') || 0);
						let reqEnd = Number(urlObj.searchParams.get('endLine') || 0);

						const hashMatch = filePart.match(/#L(\d+)(?:-L?(\d+))?$/);
						if (hashMatch) {
							filePart = filePart.slice(0, hashMatch.index);
							reqStart = Number(hashMatch[1]);
							reqEnd = Number(hashMatch[2] || hashMatch[1]);
						} else {
							const colonMatch = filePart.match(/:(\d+)(?:-(\d+))?(?:,\d+(?:-\d+)?)?$/);
							if (colonMatch) {
								filePart = filePart.slice(0, colonMatch.index);
								reqStart = Number(colonMatch[1]);
								reqEnd = Number(colonMatch[2] || colonMatch[1]);
							}
						}

						const resolved = path.resolve(repoRoot, filePart);
						if (!resolved.startsWith(repoRoot)) {
							return sendJson(res, 403, {
								success: false,
								error: 'Đường dẫn nằm ngoài phạm vi repository.',
							});
						}
						if (!fs.existsSync(resolved) || fs.statSync(resolved).isDirectory()) {
							return sendJson(res, 404, {
								success: false,
								error: `Không tìm thấy file: ${filePart}`,
							});
						}

						const content = fs.readFileSync(resolved, 'utf-8');
						const allLines = content.split(/\r?\n/);

						let snippetLines = allLines;
						let sliceStart = 1;
						let sliceEnd = allLines.length;

						if (reqStart > 0) {
							const pad = 10;
							sliceStart = Math.max(1, reqStart - pad);
							sliceEnd = Math.min(
								allLines.length,
								(reqEnd > 0 ? reqEnd : reqStart) + pad
							);
							snippetLines = allLines.slice(sliceStart - 1, sliceEnd);
						}

						return sendJson(res, 200, {
							success: true,
							data: {
								path: path.relative(repoRoot, resolved).replace(/\\/g, '/'),
								absPath: resolved.replace(/\\/g, '/'),
								content,
								totalLines: allLines.length,
								highlightStart: reqStart || null,
								highlightEnd: reqEnd || reqStart || null,
								sliceStart,
								sliceEnd,
								snippet: snippetLines.join('\n'),
							},
						});
					}

					// 3. PUT /__docs_api/file (Save edited markdown file)
					if (req.method === 'PUT' && pathname === '/__docs_api/file') {
						const body = JSON.parse(await readBody(req)) as {
							path: string;
							content: string;
						};
						const resolved = path.resolve(repoRoot, body.path);
						if (!resolved.startsWith(repoRoot) || !resolved.endsWith('.md')) {
							return sendJson(res, 403, {
								success: false,
								error: 'Chỉ cho phép lưu các file .md bên trong repository.',
							});
						}
						fs.writeFileSync(resolved, body.content, 'utf-8');
						return sendJson(res, 200, {
							success: true,
							data: { path: body.path },
						});
					}

					// 4. POST /__docs_api/plan/action (Toggle checkbox, update status, update verdict)
					if (req.method === 'POST' && pathname === '/__docs_api/plan/action') {
						const body = JSON.parse(await readBody(req)) as {
							slug: string;
							action: 'toggle_checkbox' | 'update_status' | 'append_question';
							lineNumber?: number;
							checked?: boolean;
							status?: string;
							question?: string;
						};
						const planPath = path.resolve(repoRoot, '.plan', `${body.slug}.md`);
						if (!planPath.startsWith(repoRoot) || !fs.existsSync(planPath)) {
							return sendJson(res, 404, {
								success: false,
								error: 'Không tìm thấy file plan.',
							});
						}

						let content = fs.readFileSync(planPath, 'utf-8');
						const lines = content.split(/\r?\n/);

						if (body.action === 'toggle_checkbox' && body.lineNumber) {
							const idx = body.lineNumber - 1;
							if (idx >= 0 && idx < lines.length) {
								lines[idx] = lines[idx].replace(
									/^(\s*-\s+\[)[ xX](\])/,
									`$1${body.checked ? 'x' : ' '}$2`
								);
								content = lines.join('\n');
								fs.writeFileSync(planPath, content, 'utf-8');
							}
						} else if (body.action === 'update_status' && body.status) {
							content = content.replace(
								/(\*\*Status:\*\*\s*)([^·\n>]+)/i,
								`$1${body.status}`
							);
							fs.writeFileSync(planPath, content, 'utf-8');
						} else if (body.action === 'append_question' && body.question) {
							const qLine = `- ${body.question.trim()}`;
							if (/##\s+8\.\s+Open questions[\s\S]*?\n-\s*—/.test(content)) {
								content = content.replace(
									/(##\s+8\.\s+Open questions\s*\r?\n)-\s*—/,
									`$1${qLine}`
								);
							} else {
								content = `${content.trimEnd()}\n${qLine}\n`;
							}
							fs.writeFileSync(planPath, content, 'utf-8');
						}

						const updatedPlan = parsePlanFile(repoRoot, planPath);
						return sendJson(res, 200, {
							success: true,
							data: updatedPlan,
						});
					}

					// 5. POST /__docs_api/issue/status (Update status in both README.md and MM-DD-YYYY.md)
					if (req.method === 'POST' && pathname === '/__docs_api/issue/status') {
						const body = JSON.parse(await readBody(req)) as {
							id: string;
							status: string;
						};
						const readmePath = path.join(repoRoot, 'docs', 'issues', 'README.md');
						if (fs.existsSync(readmePath)) {
							const readmeLines = fs.readFileSync(readmePath, 'utf-8').split(/\r?\n/);
							for (let i = 0; i < readmeLines.length; i++) {
								const line = readmeLines[i];
								if (line.startsWith(`| ${body.id} |`)) {
									const cells = line.split('|');
									if (cells.length >= 8) {
										cells[6] = ` ${body.status} `;
										readmeLines[i] = cells.join('|');
									}
								}
							}
							fs.writeFileSync(readmePath, readmeLines.join('\n'), 'utf-8');
						}

						const { issues } = parseIssues(repoRoot);
						const target = issues.find((iss) => iss.id === body.id);
						if (target && target.datedFile) {
							const datedPath = path.resolve(repoRoot, target.datedFile);
							if (fs.existsSync(datedPath)) {
								const datedLines = fs.readFileSync(datedPath, 'utf-8').split(/\r?\n/);
								let insideIssue = false;
								for (let i = 0; i < datedLines.length; i++) {
									if (datedLines[i].startsWith(`## ${body.id}:`)) {
										insideIssue = true;
										continue;
									}
									if (insideIssue && datedLines[i].startsWith('## ')) {
										break;
									}
									if (
										insideIssue &&
										/^\s*-\s+\*\*Status:\*\*/.test(datedLines[i])
									) {
										datedLines[i] = `- **Status:** ${body.status}`;
										break;
									}
								}
								fs.writeFileSync(datedPath, datedLines.join('\n'), 'utf-8');
							}
						}

						return sendJson(res, 200, {
							success: true,
							data: parseIssues(repoRoot),
						});
					}

					return sendJson(res, 404, {
						success: false,
						error: `Endpoint không tồn tại: ${pathname}`,
					});
				} catch (err) {
					const msg = err instanceof Error ? err.message : String(err);
					return sendJson(res, 500, {
						success: false,
						error: msg,
					});
				}
			});
		},
	};
}
