import { describe, expect, it } from 'vitest';
import { formatBytes, formatDate, formatNumber, formatPercent, truncate } from './formatters';

// Example pure-util test: no providers, no network.
describe('formatters', () => {
	// Covers ISS-005 (R4): numbers use vi-VN, missing dates show Vietnamese placeholder.
	it('test_format_number_uses_vi_vn_separator', () => {
		expect(formatNumber(1234567)).toBe('1.234.567');
	});

	it('test_format_date_missing_value_is_vietnamese', () => {
		expect(formatDate(undefined)).toBe('Không có');
	});

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
