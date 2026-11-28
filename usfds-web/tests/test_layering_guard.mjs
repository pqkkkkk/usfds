import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, '..');
const SCANNED_DIRS = [
	path.join(webRoot, 'src', 'components'),
	path.join(webRoot, 'src', 'pages'),
];

// INV-014 / ISS-032: Frozen shrink-only allowlist of legacy UI files importing src/api/* directly.
// New or refactored components/pages must fetch through src/hooks/* instead of importing src/api/*.
// Never add entries here; remove entries as legacy files are migrated to hooks.
const COMPONENT_API_IMPORT_ALLOWLIST = new Set([
	'src/components/modules/InsightReportModule.tsx',
	'src/components/modules/auth/ProfileModal.tsx',
	'src/components/modules/detection/DetectionJobWizardView.tsx',
	'src/components/modules/detection/DetectionJobsHubView.tsx',
	'src/components/modules/detection/DetectionResultExplorerView.tsx',
	'src/components/modules/investigation/CaseQueueView.tsx',
	'src/components/modules/investigation/CaseWorkbenchView.tsx',
	'src/components/modules/investigation/PoliciesView.tsx',
	'src/components/modules/model/ActivateModelModal.tsx',
	'src/components/modules/model/ImportCustomModelModal.tsx',
	'src/components/modules/model/ModelHubView.tsx',
	'src/components/modules/model/TrainingRunDetailView.tsx',
	'src/components/modules/model/TrainingWizardView.tsx',
	'src/components/modules/reports/ComplianceReportCenterTab.tsx',
	'src/components/modules/rule/RuleCatalogView.tsx',
	'src/components/modules/rule/RuleDryRunWorkspace.tsx',
	'src/components/modules/rule/RuleVersionHistoryModal.tsx',
	'src/components/modules/rule/RuleWorkspace.tsx',
	'src/pages/AdminUsersPage.tsx',
]);

// Internal dev docs viewer is excluded from product layering allowlist.
const EXCLUDED_PATH_PREFIXES = [
	'src/components/modules/docs_dashboard/',
	'src/pages/DocsDashboardPage.tsx',
];

function walkSourceFiles(dir) {
	const results = [];
	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		const fullPath = path.join(dir, entry.name);
		if (entry.isDirectory()) {
			results.push(...walkSourceFiles(fullPath));
		} else if (/\.(ts|tsx)$/.test(entry.name) && !/\.test\.(ts|tsx)$/.test(entry.name)) {
			results.push(fullPath);
		}
	}
	return results.sort();
}

function stripComments(source) {
	return source
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/^\s*\/\/.*$/gm, '');
}

function isInlineTypeOnlyClause(clause) {
	const trimmed = clause.trim();
	if (/^type\b/.test(trimmed)) {
		return true;
	}
	const namedOnly = trimmed.match(/^\{([\s\S]*)\}$/);
	if (!namedOnly) {
		return false;
	}
	const specifiers = namedOnly[1]
		.split(',')
		.map((part) => part.trim())
		.filter(Boolean);
	return specifiers.length > 0 && specifiers.every((spec) => /^type\s+/.test(spec));
}

const API_SPECIFIER = '(@\\/api(?:\\/[^\'"]*)?|(?:\\.\\.\\/)+api(?:\\/[^\'"]*)?)';
const STATIC_IMPORT_OR_REEXPORT_RE = new RegExp(
	`(?:^|\\n)\\s*(?:import|export)\\s+([\\w*$\\s{},]+)\\s+from\\s+['"]${API_SPECIFIER}['"]`,
	'g'
);
const SIDE_EFFECT_IMPORT_RE = new RegExp(
	`(?:^|\\n)\\s*import\\s+['"]${API_SPECIFIER}['"]`,
	'g'
);
const DYNAMIC_IMPORT_RE = new RegExp(
	`import\\(\\s*['"]${API_SPECIFIER}['"]\\s*\\)`,
	'g'
);

function importsApiClient(source) {
	const cleaned = stripComments(source);
	STATIC_IMPORT_OR_REEXPORT_RE.lastIndex = 0;
	let match;
	while ((match = STATIC_IMPORT_OR_REEXPORT_RE.exec(cleaned)) !== null) {
		if (!isInlineTypeOnlyClause(match[1])) {
			return true;
		}
	}
	SIDE_EFFECT_IMPORT_RE.lastIndex = 0;
	DYNAMIC_IMPORT_RE.lastIndex = 0;
	return SIDE_EFFECT_IMPORT_RE.test(cleaned) || DYNAMIC_IMPORT_RE.test(cleaned);
}

test('component API layering guard detector handles value imports, re-exports, and type-only imports', () => {
	assert.equal(importsApiClient("import { datasetApi } from '@/api/datasetApi';"), true);
	assert.equal(importsApiClient("import { ruleApi } from '../../../api/ruleApi';"), true);
	assert.equal(importsApiClient("import { type ApiResponse, datasetApi } from '@/api';"), true);
	assert.equal(importsApiClient("export { datasetApi } from '@/api/datasetApi';"), true);
	assert.equal(importsApiClient("const m = await import('@/api');"), true);
	assert.equal(
		importsApiClient("import React from 'react';\nimport type { ApiResponse } from '@/api/client';"),
		false
	);
	assert.equal(
		importsApiClient("import { type ApiResponse, type ApiError } from '@/api/client';"),
		false
	);
	assert.equal(importsApiClient("// import { datasetApi } from '@/api/datasetApi';"), false);
});

test('component API layering guard (INV-014): new components/pages must use hooks instead of importing src/api/*', () => {
	const actualDirectApiImports = new Set();

	for (const dir of SCANNED_DIRS) {
		for (const filePath of walkSourceFiles(dir)) {
			const relPath = path.relative(webRoot, filePath).split(path.sep).join('/');
			if (EXCLUDED_PATH_PREFIXES.some((prefix) => relPath.startsWith(prefix))) {
				continue;
			}
			const source = fs.readFileSync(filePath, 'utf8');
			if (importsApiClient(source)) {
				actualDirectApiImports.add(relPath);
			}
		}
	}

	const newViolations = [...actualDirectApiImports]
		.filter((file) => !COMPONENT_API_IMPORT_ALLOWLIST.has(file))
		.sort();
	const staleEntries = [...COMPONENT_API_IMPORT_ALLOWLIST]
		.filter((file) => !actualDirectApiImports.has(file))
		.sort();

	assert.deepEqual(
		newViolations,
		[],
		`Direct src/api/* import in UI file(s) violates INV-014 (route data fetching through src/hooks/*):\n${newViolations.join('\n')}`
	);
	assert.deepEqual(
		staleEntries,
		[],
		`Remove migrated file(s) from COMPONENT_API_IMPORT_ALLOWLIST (shrink-only):\n${staleEntries.join('\n')}`
	);
});
