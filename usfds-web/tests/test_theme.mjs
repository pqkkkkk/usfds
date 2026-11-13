import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, '..');

test('light mode CSS variables and theme token contract', () => {
	const indexCss = fs.readFileSync(path.join(webRoot, 'src', 'index.css'), 'utf8');
	const tailwindConfig = fs.readFileSync(path.join(webRoot, 'tailwind.config.js'), 'utf8');
	const useThemeSource = fs.readFileSync(path.join(webRoot, 'src', 'hooks', 'useTheme.tsx'), 'utf8');

	// 1. Verify :root and html[data-theme="light"] blocks exist in index.css
	assert.match(indexCss, /:root\s*\{/);
	assert.match(indexCss, /html\[data-theme="light"\]\s*\{/);

	// 2. Verify RGB channel variables for dark surfaces and slate scale exist in both modes
	const requiredVars = [
		'--tw-dark-950',
		'--tw-dark-900',
		'--tw-dark-850',
		'--tw-dark-800',
		'--tw-dark-700',
		'--tw-slate-100',
		'--tw-slate-200',
		'--tw-slate-400',
		'--tw-slate-700',
		'--tw-slate-800',
		'--tw-brand-400',
		'--tw-emerald-400',
		'--tw-amber-400',
		'--tw-rose-400',
	];

	for (const cssVar of requiredVars) {
		const occurrences = indexCss.split(cssVar).length - 1;
		assert.ok(
			occurrences >= 2,
			`Expected ${cssVar} to be defined in both :root and html[data-theme="light"]`
		);
	}

	// 3. Verify tailwind.config.js maps dark and slate colors to RGB CSS variables with <alpha-value>
	assert.match(tailwindConfig, /950:\s*'rgb\(var\(--tw-dark-950\)\s*\/\s*<alpha-value>\)'/);
	assert.match(tailwindConfig, /100:\s*'rgb\(var\(--tw-slate-100\)\s*\/\s*<alpha-value>\)'/);

	// 4. Verify useTheme supports strictly 'dark' | 'light' with 'dark' default and localStorage key
	assert.match(useThemeSource, /export type ThemeMode = 'dark' \| 'light';/);
	assert.match(useThemeSource, /export const THEME_STORAGE_KEY = 'usfds_theme';/);
});

