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
	schemaVersion: 'v2' | 'v1' | 'legacy';
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
	designApproachMarkdown: string;
	mermaidBlocks: string[];
	sections: Record<string, string>;
	filesTable: ParsedPlanFileEntry[];
	conflictsTable: ParsedConflictCheck[];
	acceptanceTests: ParsedAcceptanceTest[];
	milestones: ParsedMilestoneGroup[];
	checkpointLogs: string[];
	hotspots: ParsedHotspot[];
	openQuestions: string[];
	manualE2eItems: ParsedChecklistItem[];
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

export interface DocsFileMeta {
	path: string;
	name: string;
	category: string;
	updatedAt: string;
}

export interface DocsOverviewResponse {
	repoRoot: string;
	board: {
		raw: string;
		phase0Rows: string[][];
		activeTaskRows: string[][];
	};
	plans: ParsedPlan[];
	issues: ParsedIssue[];
	issueLinterWarnings: string[];
	docsFiles: DocsFileMeta[];
}

export interface FileSnippetResponse {
	path: string;
	absPath: string;
	content: string;
	totalLines: number;
	highlightStart: number | null;
	highlightEnd: number | null;
	sliceStart: number;
	sliceEnd: number;
	snippet: string;
}

export const docsDashboardApi = {
	async getOverview(): Promise<DocsOverviewResponse> {
		const res = await fetch('/__docs_api/overview');
		const json = await res.json();
		if (!json.success) {
			throw new Error(json.error || 'Không thể tải dữ liệu tài liệu.');
		}
		return json.data;
	},

	async getFile(targetPath: string): Promise<FileSnippetResponse> {
		const res = await fetch(`/__docs_api/file?path=${encodeURIComponent(targetPath)}`);
		const json = await res.json();
		if (!json.success) {
			throw new Error(json.error || `Không thể đọc file: ${targetPath}`);
		}
		return json.data;
	},

	async saveFile(targetPath: string, content: string): Promise<void> {
		const res = await fetch('/__docs_api/file', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ path: targetPath, content }),
		});
		const json = await res.json();
		if (!json.success) {
			throw new Error(json.error || 'Không thể lưu file.');
		}
	},

	async togglePlanCheckbox(
		slug: string,
		lineNumber: number,
		checked: boolean
	): Promise<ParsedPlan> {
		const res = await fetch('/__docs_api/plan/action', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				slug,
				action: 'toggle_checkbox',
				lineNumber,
				checked,
			}),
		});
		const json = await res.json();
		if (!json.success) {
			throw new Error(json.error || 'Không thể cập nhật tiến độ.');
		}
		return json.data;
	},

	async updatePlanStatus(slug: string, status: string): Promise<ParsedPlan> {
		const res = await fetch('/__docs_api/plan/action', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				slug,
				action: 'update_status',
				status,
			}),
		});
		const json = await res.json();
		if (!json.success) {
			throw new Error(json.error || 'Không thể cập nhật trạng thái Plan.');
		}
		return json.data;
	},

	async appendPlanQuestion(slug: string, question: string): Promise<ParsedPlan> {
		const res = await fetch('/__docs_api/plan/action', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				slug,
				action: 'append_question',
				question,
			}),
		});
		const json = await res.json();
		if (!json.success) {
			throw new Error(json.error || 'Không thể thêm câu hỏi vào Plan.');
		}
		return json.data;
	},

	async updateIssueStatus(id: string, status: string): Promise<void> {
		const res = await fetch('/__docs_api/issue/status', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ id, status }),
		});
		const json = await res.json();
		if (!json.success) {
			throw new Error(json.error || 'Không thể cập nhật trạng thái Issue.');
		}
	},
};
