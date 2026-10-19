import type {
  RuleGroup,
  RuleClause,
  LogicalCombinator,
  ComparisonOperator,
  RuleAction,
  AvailableFeatureField,
} from '../types/rule';

// Available feature dictionary for fraud detection domain
export const AVAILABLE_FEATURE_FIELDS: AvailableFeatureField[] = [
  {
    key: 'amount',
    label: 'amount (Transaction Amount)',
    category: 'transaction',
    dataType: 'number',
    unit: 'USD',
    defaultOperator: '>',
    sampleValues: [500, 1000, 2000, 5000],
  },
  {
    key: 'is_new_device_24h',
    label: 'is_new_device_24h (First-seen Device)',
    category: 'device',
    dataType: 'boolean',
    defaultOperator: '==',
    sampleValues: [true, false],
  },
  {
    key: 'velocity_count_1h',
    label: 'velocity_count_1h (Transactions in 1h)',
    category: 'velocity',
    dataType: 'number',
    unit: 'swipes',
    defaultOperator: '>=',
    sampleValues: [3, 5, 10],
  },
  {
    key: 'merchant_risk_category',
    label: 'merchant_risk_category (MCC Risk)',
    category: 'merchant',
    dataType: 'array',
    defaultOperator: 'in',
    sampleValues: ['electronics', 'gift_card', 'crypto', 'jewelry', 'gambling'],
  },
  {
    key: 'device_trust_score',
    label: 'device_trust_score (Device Reputation)',
    category: 'device',
    dataType: 'number',
    unit: 'pts',
    defaultOperator: '<',
    sampleValues: [0.2, 0.4, 0.8],
  },
  {
    key: 'geo_distance_home',
    label: 'geo_distance_home (Distance from Home)',
    category: 'transaction',
    dataType: 'number',
    unit: 'km',
    defaultOperator: '>',
    sampleValues: [100, 500, 1000],
  },
  {
    key: 'trans_freq_7d',
    label: 'trans_freq_7d (7-Day Frequency Avg)',
    category: 'velocity',
    dataType: 'number',
    unit: 'txns',
    defaultOperator: '>',
    sampleValues: [15, 30, 50],
  },
  {
    key: 'velocity_sum_24h',
    label: 'velocity_sum_24h (24-Hour Total Spent)',
    category: 'velocity',
    dataType: 'number',
    unit: 'USD',
    defaultOperator: '>=',
    sampleValues: [3000, 5000, 10000],
  },
  {
    key: 'user_id',
    label: 'user_id (Hashed PAN / User Hash)',
    category: 'user',
    dataType: 'string',
    defaultOperator: '==',
  },
  {
    key: 'mcc_code',
    label: 'mcc_code (Merchant Category Code)',
    category: 'merchant',
    dataType: 'string',
    defaultOperator: '==',
    sampleValues: ['5732', '6051', '7995'],
  },
];

export function isRuleGroup(item: RuleClause | RuleGroup): item is RuleGroup {
  return 'combinator' in item && 'clauses' in item;
}

/**
 * Compiles UI RuleGroup into standard JsonLogic AST compatible with usfds-core JsonLogicEvaluator
 */
export function groupToJsonLogic(group: RuleGroup): Record<string, any> {
  if (!group.clauses || group.clauses.length === 0) {
    return { and: [] };
  }

  const compiledClauses = group.clauses.map((clause) => {
    if (isRuleGroup(clause)) {
      return groupToJsonLogic(clause);
    }
    return clauseToJsonLogic(clause);
  });

  if (group.combinator === 'ALL') {
    return { and: compiledClauses };
  } else if (group.combinator === 'ANY') {
    return { or: compiledClauses };
  } else {
    // NONE of (NOT (OR (...)))
    return { '!': { or: compiledClauses } };
  }
}

/**
 * Compiles a single RuleClause into JsonLogic operator format
 */
export function clauseToJsonLogic(clause: RuleClause): Record<string, any> {
  const { field, operator, value } = clause;
  const varExpr = { var: field };

  let parsedVal: any = value;
  if (value === 'true') parsedVal = true;
  else if (value === 'false') parsedVal = false;
  else if (typeof value === 'string' && !isNaN(Number(value)) && value.trim() !== '') {
    parsedVal = Number(value);
  }

  switch (operator) {
    case 'in':
      // JsonLogic: {"in": [{"var": "field"}, ["a", "b"]]} or {"in": [val, list]}
      const listVal = Array.isArray(parsedVal)
        ? parsedVal
        : typeof parsedVal === 'string'
        ? parsedVal.split(',').map((s) => s.trim())
        : [parsedVal];
      return { in: [varExpr, listVal] };

    case 'not_in':
      const notListVal = Array.isArray(parsedVal)
        ? parsedVal
        : typeof parsedVal === 'string'
        ? parsedVal.split(',').map((s) => s.trim())
        : [parsedVal];
      return { '!': { in: [varExpr, notListVal] } };

    case 'regex':
      return { regex: [String(parsedVal), varExpr] };

    case '>':
    case '>=':
    case '<':
    case '<=':
    case '==':
    case '!=':
    default:
      return { [operator]: [varExpr, parsedVal] };
  }
}

/**
 * Formats RuleGroup into Stitch SUC-11 DSL format:
 * { "all": [ { "field": "amount", "op": ">", "value": 2000 }, { "any": [...] } ] }
 */
export function groupToStitchDsl(group: RuleGroup): Record<string, any> {
  const key = group.combinator === 'ALL' ? 'all' : group.combinator === 'ANY' ? 'any' : 'none';
  const compiled = group.clauses.map((item) => {
    if (isRuleGroup(item)) {
      return groupToStitchDsl(item);
    }
    return {
      field: item.field,
      op: item.operator,
      value: item.value,
    };
  });
  return { [key]: compiled };
}

/**
 * Parses existing JsonLogic AST back into UI RuleGroup structure
 */
export function jsonLogicToGroup(logic: any): RuleGroup {
  const defaultGroup: RuleGroup = {
    id: `grp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
    combinator: 'ALL',
    clauses: [],
  };

  if (!logic || typeof logic !== 'object') {
    return defaultGroup;
  }

  // Handle Stitch DSL format { "all": [...], "any": [...] }
  if (logic.all && Array.isArray(logic.all)) {
    return {
      id: `grp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      combinator: 'ALL',
      clauses: logic.all.map(parseClauseOrGroup),
    };
  }
  if (logic.any && Array.isArray(logic.any)) {
    return {
      id: `grp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      combinator: 'ANY',
      clauses: logic.any.map(parseClauseOrGroup),
    };
  }

  // Handle Standard JsonLogic { "and": [...] }, { "or": [...] }, { "!": ... }
  const op = Object.keys(logic)[0];
  const args = logic[op];

  if (op === 'and' && Array.isArray(args)) {
    return {
      id: `grp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      combinator: 'ALL',
      clauses: args.map(parseClauseOrGroup),
    };
  } else if (op === 'or' && Array.isArray(args)) {
    return {
      id: `grp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      combinator: 'ANY',
      clauses: args.map(parseClauseOrGroup),
    };
  } else if (op === '!' && args && typeof args === 'object' && args.or) {
    return {
      id: `grp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      combinator: 'NONE',
      clauses: args.or.map(parseClauseOrGroup),
    };
  } else {
    // Single top-level expression
    return {
      id: `grp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      combinator: 'ALL',
      clauses: [parseSingleExpression(op, args)],
    };
  }
}

function parseClauseOrGroup(item: any): RuleClause | RuleGroup {
  if (!item || typeof item !== 'object') {
    return createDefaultClause();
  }

  // If item is Stitch DSL sub-group
  if (item.all || item.any || item.none) {
    return jsonLogicToGroup(item);
  }

  // If item is Stitch DSL clause
  if ('field' in item && 'op' in item) {
    const meta = AVAILABLE_FEATURE_FIELDS.find((f) => f.key === item.field);
    return {
      id: `cls-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      field: item.field,
      operator: item.op,
      value: item.value,
      unit: meta?.unit,
    };
  }

  // Standard JsonLogic
  const op = Object.keys(item)[0];
  const args = item[op];

  if (op === 'and' || op === 'or' || op === '!') {
    return jsonLogicToGroup(item);
  }

  return parseSingleExpression(op, args);
}

function parseSingleExpression(op: string, args: any): RuleClause {
  let field = 'amount';
  let operator: ComparisonOperator = '==';
  let value: any = '';

  if (Array.isArray(args) && args.length >= 2) {
    // Usually [{"var": "field"}, value]
    if (args[0] && typeof args[0] === 'object' && 'var' in args[0]) {
      field = args[0].var;
      value = args[1];
    } else if (args[1] && typeof args[1] === 'object' && 'var' in args[1]) {
      field = args[1].var;
      value = args[0];
    }
  }

  if (['>', '>=', '<', '<=', '==', '!=', 'in', 'not_in', 'regex'].includes(op)) {
    operator = op as ComparisonOperator;
  }

  const meta = AVAILABLE_FEATURE_FIELDS.find((f) => f.key === field);
  return {
    id: `cls-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
    field,
    operator,
    value,
    unit: meta?.unit,
  };
}

export function createDefaultClause(): RuleClause {
  return {
    id: `cls-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
    field: 'amount',
    operator: '>',
    value: 2000,
    unit: 'USD',
  };
}

export function createDefaultGroup(combinator: LogicalCombinator = 'ANY'): RuleGroup {
  return {
    id: `grp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
    combinator,
    clauses: [
      {
        id: `cls-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
        field: 'is_new_device_24h',
        operator: '==',
        value: true,
      },
      {
        id: `cls-${Date.now() + 1}-${Math.random().toString(36).substr(2, 4)}`,
        field: 'velocity_count_1h',
        operator: '>=',
        value: 5,
        unit: 'swipes',
      },
    ],
  };
}

/**
 * Creates the initial default Stitch SUC-11 rule structure
 */
export function createStitchSampleRuleGroup(): RuleGroup {
  return {
    id: 'grp-root',
    combinator: 'ALL',
    clauses: [
      {
        id: 'cls-1',
        field: 'amount',
        operator: '>',
        value: 2000,
        unit: 'USD',
      },
      {
        id: 'grp-nested-1',
        combinator: 'ANY',
        clauses: [
          {
            id: 'cls-2-1',
            field: 'is_new_device_24h',
            operator: '==',
            value: true,
          },
          {
            id: 'cls-2-2',
            field: 'velocity_count_1h',
            operator: '>=',
            value: 5,
            unit: 'swipes',
          },
        ],
      },
      {
        id: 'cls-3',
        field: 'merchant_risk_category',
        operator: 'in',
        value: ['electronics', 'gift_card', 'crypto'],
      },
    ],
  };
}

/**
 * Generates dynamic Natural Language Interpretation matching Card 1 in Stitch
 */
export function groupToNaturalLanguage(group: RuleGroup, action: RuleAction): string {
  if (!group.clauses || group.clauses.length === 0) {
    return `Trigger ${action} when no conditions are defined (default pass).`;
  }

  const parts = group.clauses.map((item) => {
    if (isRuleGroup(item)) {
      const subJoiner = item.combinator === 'ALL' ? ' AND ' : ' OR ';
      const subParts = item.clauses.map((sub) => {
        if (isRuleGroup(sub)) return `(${groupToNaturalLanguage(sub, action)})`;
        return formatClauseText(sub);
      });
      return `(${subParts.join(subJoiner)})`;
    }
    return formatClauseText(item);
  });

  const joiner = group.combinator === 'ALL' ? ' AND ' : group.combinator === 'ANY' ? ' OR ' : ' AND NOT ';
  return `Trigger ${action} when ${parts.join(joiner)}.`;
}

function formatClauseText(clause: RuleClause): string {
  const { field, operator, value, unit } = clause;
  let formattedVal = value;
  if (Array.isArray(value)) {
    formattedVal = `[${value.join(', ')}]`;
  } else if (unit) {
    formattedVal = `${value} ${unit}`;
  }

  switch (operator) {
    case '>':
      return `${field} > ${formattedVal}`;
    case '>=':
      return `${field} >= ${formattedVal}`;
    case '<':
      return `${field} < ${formattedVal}`;
    case '<=':
      return `${field} <= ${formattedVal}`;
    case '==':
      return `${field} is ${formattedVal}`;
    case '!=':
      return `${field} != ${formattedVal}`;
    case 'in':
      return `${field} is in ${formattedVal}`;
    case 'not_in':
      return `${field} not in ${formattedVal}`;
    case 'regex':
      return `${field} matches regex /${formattedVal}/`;
    default:
      return `${field} ${operator} ${formattedVal}`;
  }
}

/**
 * Computes AST node count
 */
export function countAstNodes(group: RuleGroup): number {
  let count = 1; // group itself
  for (const item of group.clauses) {
    if (isRuleGroup(item)) {
      count += countAstNodes(item);
    } else {
      count += 1;
    }
  }
  return count;
}
