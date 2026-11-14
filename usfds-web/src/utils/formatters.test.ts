import { describe, expect, it } from 'vitest';
import { formatBytes, formatPercent, truncate } from './formatters';

// Example pure-util test: no providers, no network.
describe('formatters', () => {
	it('formats bytes with binary units', () => {
		expect(formatBytes(undefined)).toBe('0 B');
		expect(formatBytes(1536)).toBe('1.5 KB');
		expect(formatBytes(5 * 1024 * 1024, 0)).toBe('5 MB');
	});

	it('formats ratios as percentages', () => {
		expect(formatPercent(0.1234)).toBe('12.3%');
		expect(formatPercent(undefined)).toBe('0%');
	});

	it('truncates long text with an ellipsis', () => {
		expect(truncate('short', 10)).toBe('short');
		expect(truncate('abcdefghij', 4)).toBe('abcd...');
	});
});
