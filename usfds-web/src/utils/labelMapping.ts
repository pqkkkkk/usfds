export type LabelBinaryValue = 0 | 1;
export type LabelDraftAssignment = LabelBinaryValue | '';

export interface LabelMappingEntry {
	raw: string;
	target: LabelDraftAssignment;
	isManual?: boolean;
}

export const DEFAULT_POSITIVE_LABEL_TOKENS: readonly string[] = [
	'1',
	'1.0',
	'true',
	'yes',
	'y',
	't',
	'fraud',
	'fraudulent',
	'positive',
	'pos',
	'spam',
	'bad',
	'anomaly',
	'chargeback',
	'gian lận',
];

export const DEFAULT_NEGATIVE_LABEL_TOKENS: readonly string[] = [
	'0',
	'0.0',
	'false',
	'no',
	'n',
	'f',
	'legit',
	'legitimate',
	'normal',
	'negative',
	'neg',
	'ok',
	'good',
	'benign',
	'non-fraud',
	'non_fraud',
	'nonfraud',
	'not_fraud',
	'hợp lệ',
];

const POSITIVE_TOKEN_SET = new Set(DEFAULT_POSITIVE_LABEL_TOKENS);
const NEGATIVE_TOKEN_SET = new Set(DEFAULT_NEGATIVE_LABEL_TOKENS);

/**
 * Auto-suggests canonical binary targets (0 or 1) for raw label distinct values
 * using Frontend default tokens (case-insensitive after trim). Unknown values stay ''.
 */
export function suggestLabelValueMapping(
	distinctValues: string[]
): Record<string, LabelDraftAssignment> {
	const draft: Record<string, LabelDraftAssignment> = {};
	for (const rawValue of distinctValues) {
		const trimmed = String(rawValue).trim();
		if (!trimmed) {
			continue;
		}
		const lower = trimmed.toLowerCase();
		if (POSITIVE_TOKEN_SET.has(lower)) {
			draft[trimmed] = 1;
		} else if (NEGATIVE_TOKEN_SET.has(lower)) {
			draft[trimmed] = 0;
		} else {
			draft[trimmed] = '';
		}
	}
	return draft;
}

/**
 * Builds ordered UI entries from raw distinct values and optional previously saved mapping.
 */
export function buildLabelMappingEntries(
	distinctValues: string[],
	savedMapping?: Record<string, number> | null
): LabelMappingEntry[] {
	if (distinctValues.length > 0) {
		const suggested = suggestLabelValueMapping(distinctValues);
		return Object.keys(suggested).map((raw) => {
			const saved = savedMapping?.[raw];
			const target: LabelDraftAssignment =
				saved === 0 || saved === 1 ? saved : suggested[raw];
			return { raw, target, isManual: false };
		});
	}

	if (savedMapping && Object.keys(savedMapping).length > 0) {
		return Object.entries(savedMapping)
			.filter(([raw, val]) => raw.trim().length > 0 && (val === 0 || val === 1))
			.map(([raw, val]) => ({
				raw: raw.trim(),
				target: val as LabelBinaryValue,
				isManual: true,
			}));
	}

	return [];
}

/**
 * Validates and compiles UI mapping entries into a backend-ready Record<string, 0 | 1>.
 */
export function finalizeLabelValueMapping(entries: LabelMappingEntry[]): {
	mapping?: Record<string, LabelBinaryValue>;
	unassignedCount: number;
	hasInvalidKey: boolean;
	isComplete: boolean;
} {
	if (entries.length === 0) {
		return {
			mapping: undefined,
			unassignedCount: 0,
			hasInvalidKey: false,
			isComplete: true,
		};
	}

	const seen = new Set<string>();
	let unassignedCount = 0;
	let hasInvalidKey = false;
	const mapping: Record<string, LabelBinaryValue> = {};

	for (const entry of entries) {
		const key = entry.raw.trim();
		if (!key || seen.has(key)) {
			hasInvalidKey = true;
			continue;
		}
		seen.add(key);
		if (entry.target !== 0 && entry.target !== 1) {
			unassignedCount += 1;
			continue;
		}
		mapping[key] = entry.target;
	}

	const isComplete = !hasInvalidKey && unassignedCount === 0;
	return {
		mapping: isComplete ? mapping : undefined,
		unassignedCount,
		hasInvalidKey,
		isComplete,
	};
}
