import time
import re
from typing import Any, Dict, List, Tuple
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.domain.schemas.rule_schemas import RuleExecutionContext, RuleExecutionResult


class JsonLogicEvaluator:
    """
    Core engine to evaluate JsonLogic expressions against runtime data payloads.
    Pure-Python, zero external dependency implementation matching official JsonLogic spec.
    """

    @classmethod
    def evaluate(cls, logic: Any, data: Dict[str, Any]) -> Any:
        # Primitives return as-is
        if not isinstance(logic, dict):
            return logic

        # Empty dict or non-operator
        if not logic:
            return logic

        operator, args = next(iter(logic.items()))

        # 1. Variable extraction: {"var": "mapped.amount"} or {"var": ["path", default_value]}
        if operator == "var":
            return cls._get_var(args, data)

        # Ensure args is list for operator execution
        if not isinstance(args, list):
            args = [args]

        # 2. Short-circuit logic operators (AND, OR)
        if operator == "and":
            last_result: Any = True
            for arg in args:
                val = cls.evaluate(arg, data)
                if not cls._truthy(val):
                    return val
                last_result = val
            return last_result

        if operator == "or":
            last_result: Any = False
            for arg in args:
                val = cls.evaluate(arg, data)
                if cls._truthy(val):
                    return val
                last_result = val
            return last_result

        if operator == "!":
            return not cls._truthy(cls.evaluate(args[0], data))

        if operator == "!!":
            return cls._truthy(cls.evaluate(args[0], data))

        # Evaluate arguments for comparisons & operations
        evaluated_args = [cls.evaluate(arg, data) for arg in args]
        a = evaluated_args[0] if len(evaluated_args) > 0 else None
        b = evaluated_args[1] if len(evaluated_args) > 1 else None

        match operator:
            case "==":
                return str(a) == str(b) if isinstance(a, (int, float, str)) and isinstance(b, (int, float, str)) else a == b
            case "===":
                return a == b
            case "!=":
                return str(a) != str(b) if isinstance(a, (int, float, str)) and isinstance(b, (int, float, str)) else a != b
            case "!==":
                return a != b
            case ">":
                return a > b if a is not None and b is not None else False
            case ">=":
                return a >= b if a is not None and b is not None else False
            case "<":
                # JsonLogic supports between: {"<": [0, {"var": "x"}, 10]} => 0 < x < 10
                if len(evaluated_args) == 3:
                    c = evaluated_args[2]
                    return a < b < c if a is not None and b is not None and c is not None else False
                return a < b if a is not None and b is not None else False
            case "<=":
                if len(evaluated_args) == 3:
                    c = evaluated_args[2]
                    return a <= b <= c if a is not None and b is not None and c is not None else False
                return a <= b if a is not None and b is not None else False
            case "in":
                # Check item in list or substring in string: {"in": [val, list_or_str]}
                if b is None or a is None:
                    return False
                return a in b
            case "regex":
                # Extended operator: {"regex": [pattern, {"var": "field"}]}
                if a is None or b is None:
                    return False
                return bool(re.search(str(a), str(b)))
            case _:
                raise NotImplementedError(f"Unsupported JsonLogic operator: '{operator}'")

    @classmethod
    def _truthy(cls, val: Any) -> bool:
        if val is None or val is False or val == 0 or val == "" or val == []:
            return False
        return True

    @classmethod
    def _get_var(cls, path_spec: Any, data: Dict[str, Any]) -> Any:
        path = path_spec
        default = None
        if isinstance(path_spec, list):
            path = path_spec[0]
            if len(path_spec) > 1:
                default = path_spec[1]

        if not path or not isinstance(path, str):
            return default if path is None else data

        current: Any = data
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current


class RuleExecutor:
    """
    Executes business rules against transaction context using JsonLogic.
    Supports single rule evaluation and batch rules evaluation with execution timing.
    """

    def __init__(self):
        pass

    def evaluate_rule(
        self,
        rule: Rule,
        rule_version: RuleVersion,
        context: RuleExecutionContext,
    ) -> RuleExecutionResult:
        """
        Evaluate a single rule version against a transaction context.
        """
        start_time = time.perf_counter()

        payload = self._build_payload(context)
        is_triggered = bool(JsonLogicEvaluator.evaluate(rule_version.condition, payload))

        execution_time_ms = (time.perf_counter() - start_time) * 1000.0

        trigger_reason = (
            f"Rule '{rule.rule_code}' triggered"
            if is_triggered
            else f"Rule '{rule.rule_code}' condition not satisfied"
        )

        return RuleExecutionResult(
            rule_id=str(rule.rule_id),
            rule_version_id=str(rule_version.rule_version_id),
            version_number=rule_version.version_number,
            rule_code=rule.rule_code,
            rule_name=rule.name,
            is_triggered=is_triggered,
            action=rule_version.action,
            trigger_reason=trigger_reason,
            execution_time_ms=execution_time_ms,
        )

    def evaluate_rules(
        self,
        rules_and_versions: List[Tuple[Rule, RuleVersion]],
        context: RuleExecutionContext,
    ) -> List[RuleExecutionResult]:
        """
        Evaluate multiple rules against a single transaction context.
        """
        results: List[RuleExecutionResult] = []
        for rule, version in rules_and_versions:
            result = self.evaluate_rule(rule, version, context)
            results.append(result)
        return results

    def _build_payload(self, context: RuleExecutionContext) -> Dict[str, Any]:
        """
        Builds a structured dictionary payload from RuleExecutionContext.
        Allows access via nested paths, e.g.:
          - {"var": "mapped_features.amount"}
          - {"var": "mapped.amount"}
          - {"var": "amount"} (flat fallback)
        """
        payload: Dict[str, Any] = {
            "transaction_id": context.transaction_id,
            "mapped_features": context.mapped_features or {},
            "enriched_features": context.enriched_features or {},
            # Shorthand aliases
            "mapped": context.mapped_features or {},
            "enriched": context.enriched_features or {},
        }

        # Flat fallback keys so rules can also write {"var": "amount"} directly
        if context.mapped_features:
            for k, v in context.mapped_features.items():
                if k not in payload:
                    payload[k] = v
        if context.enriched_features:
            for k, v in context.enriched_features.items():
                if k not in payload:
                    payload[k] = v

        return payload