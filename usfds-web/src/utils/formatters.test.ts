import { describe, expect, it } from 'vitest';
import { formatModelVersion } from './formatters';

describe('formatModelVersion', () => {
	it('keeps leading v without duplicating it', () => {
		expect(formatModelVersion('v1')).toBe('v1');
		expect(formatModelVersion('v12')).toBe('v12');
	});

	it('prepends v for legacy semver strings', () => {
		expect(formatModelVersion('1.0.0')).toBe('v1.0.0');
	});

	it('falls back to v1 when empty or undefined', () => {
		expect(formatModelVersion(undefined)).toBe('v1');
		expect(formatModelVersion('')).toBe('v1');
	});
});
