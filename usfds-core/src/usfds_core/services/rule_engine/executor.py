import math
import time
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from usfds_core.domain.entities.enums import RuleAction
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.domain.schemas.rule_schemas import (
    RuleBacktestResult,
    RuleBacktestSampleHit,
    RuleExecutionContext,
    RuleExecutionResult,
)


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
                return cls._safe_compare(a, b, ">")
            case ">=":
                return cls._safe_compare(a, b, ">=")
            case "<":
                # JsonLogic supports between: {"<": [0, {"var": "x"}, 10]} => 0 < x < 10
                if len(evaluated_args) == 3:
                    c = evaluated_args[2]
                    return cls._safe_compare(a, b, "<") and cls._safe_compare(b, c, "<")
                return cls._safe_compare(a, b, "<")
            case "<=":
                if len(evaluated_args) == 3:
                    c = evaluated_args[2]
                    return cls._safe_compare(a, b, "<=") and cls._safe_compare(b, c, "<=")
                return cls._safe_compare(a, b, "<=")
            case "in":
                # Check item in list or substring in string: {"in": [val, list_or_str]}
                if b is None or a is None:
                    return False
                try:
                    return a in b
                except TypeError:
                    return False
            case "regex":
                # Extended operator: {"regex": [pattern, {"var": "field"}]}
                if a is None or b is None:
                    return False
                return bool(re.search(str(a), str(b)))
            case _:
                raise NotImplementedError(f"Unsupported JsonLogic operator: '{operator}'")

    @classmethod
    def _safe_compare(cls, a: Any, b: Any, op: str) -> bool:
        if a is None or b is None:
            return False
        if isinstance(a, float) and math.isnan(a):
            return False
        if isinstance(b, float) and math.isnan(b):
            return False
        try:
            if isinstance(a, (int, float)) and isinstance(b, str):
                b = float(b)
            elif isinstance(a, str) and isinstance(b, (int, float)):
                a = float(a)
            match op:
                case ">":
                    return bool(a > b)
                case ">=":
                    return bool(a >= b)
                case "<":
                    return bool(a < b)
                case "<=":
                    return bool(a <= b)
                case _:
                    return False
        except (TypeError, ValueError):
            return False

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
        Allows access via flat RAW column keys or nested paths, e.g.:
          - {"var": "tx_amount"} (flat RAW schema column)
          - {"var": "raw.tx_amount"} / {"var": "raw_features.tx_amount"}
          - {"var": "enriched.tx_freq_last_1h"} / {"var": "enriched_features.tx_freq_last_1h"}
          - {"var": "mapped.amount"} / {"var": "mapped_features.amount"} (backward-compatible alias)
        """
        raw_feats = context.raw_features or context.mapped_features or {}
        mapped_feats = context.mapped_features or context.raw_features or {}
        enriched_feats = context.enriched_features or {}

        payload: Dict[str, Any] = {
            "transaction_id": context.transaction_id,
            "raw_features": raw_feats,
            "raw": raw_feats,
            "mapped_features": mapped_feats,
            "mapped": mapped_feats,
            "enriched_features": enriched_feats,
            "enriched": enriched_feats,
        }

        # Flat fallback keys so rules can write {"var": "tx_amount"} directly
        for k, v in raw_feats.items():
            if k not in payload:
                payload[k] = v
        for k, v in mapped_feats.items():
            if k not in payload:
                payload[k] = v
        for k, v in enriched_feats.items():
            if k not in payload:
                payload[k] = v

        return payload

    @classmethod
    def _extract_matched_clauses(cls, condition: Any, payload: Dict[str, Any]) -> List[str]:
        """Walks a JsonLogic AST and returns human-readable strings for leaf comparison clauses that evaluate to True."""
        matched: List[str] = []

        def _walk(node: Any) -> None:
            if not isinstance(node, dict) or not node:
                return
            op, args = next(iter(node.items()))
            if op in ("and", "or"):
                arg_list = args if isinstance(args, list) else [args]
                for sub in arg_list:
                    _walk(sub)
                return
            if op == "!" and isinstance(args, dict) and "in" in args:
                # Special handling for not_in: {"!": {"in": [{"var": "field"}, [...]]}}
                try:
                    if bool(JsonLogicEvaluator.evaluate(node, payload)):
                        in_args = args["in"]
                        if isinstance(in_args, list) and len(in_args) >= 2:
                            var_name = in_args[0].get("var") if isinstance(in_args[0], dict) else str(in_args[0])
                            matched.append(f"{var_name} not_in {in_args[1]}")
                except Exception:
                    pass
                return
            if op == "!":
                arg_list = args if isinstance(args, list) else [args]
                for sub in arg_list:
                    _walk(sub)
                return

            # Leaf comparison clause
            try:
                if bool(JsonLogicEvaluator.evaluate(node, payload)):
                    arg_list = args if isinstance(args, list) else [args]
                    if len(arg_list) >= 2:
                        left, right = arg_list[0], arg_list[1]
                        if op == "regex":
                            field_name = right.get("var") if isinstance(right, dict) else str(right)
                            matched.append(f"{field_name} regex /{left}/")
                        else:
                            field_name = left.get("var") if isinstance(left, dict) else str(left)
                            matched.append(f"{field_name} {op} {right}")
            except Exception:
                pass

        _walk(condition)
        return matched

    def backtest_dataframe(
        self,
        df: pd.DataFrame,
        condition: Dict[str, Any],
        action: RuleAction = RuleAction.REVIEW,
        dataset_artifact_id: str = "",
        rule_id: Optional[str] = None,
        rule_version_id: Optional[str] = None,
        version_number: int = 1,
        rule_code: str = "AD_HOC",
        rule_name: str = "Ad-hoc Rule",
        target_column: Optional[str] = None,
        amount_column: Optional[str] = None,
        id_column: Optional[str] = None,
        timestamp_column: Optional[str] = None,
        user_column: Optional[str] = None,
        max_samples: int = 50,
    ) -> RuleBacktestResult:
        """Evaluates a JsonLogic condition across a historical DataFrame (SUC-12 Dry-Run / Backtest)."""
        start_time = time.perf_counter()
        cols = [str(c) for c in df.columns]
        col_set = set(cols)

        # Auto-resolve canonical column names if not explicitly provided
        resolved_target = target_column if (target_column and target_column in col_set) else None
        if not resolved_target:
            for cand in ("is_fraud", "label", "fraud_label", "target", "class", "Class", "Fraud"):
                if cand in col_set:
                    resolved_target = cand
                    break

        resolved_amount = amount_column if (amount_column and amount_column in col_set) else None
        if not resolved_amount:
            for cand in ("amount", "tx_amount", "transaction_amount", "amt", "Amount"):
                if cand in col_set:
                    resolved_amount = cand
                    break

        resolved_id = id_column if (id_column and id_column in col_set) else None
        if not resolved_id:
            for cand in ("event_id", "transaction_id", "tx_id", "id"):
                if cand in col_set:
                    resolved_id = cand
                    break

        resolved_ts = timestamp_column if (timestamp_column and timestamp_column in col_set) else None
        if not resolved_ts:
            for cand in ("timestamp", "tx_time", "event_timestamp", "time", "created_at"):
                if cand in col_set:
                    resolved_ts = cand
                    break

        resolved_user = user_column if (user_column and user_column in col_set) else None
        if not resolved_user:
            for cand in ("user_id", "account_id", "card_id", "customer_id", "entity_id"):
                if cand in col_set:
                    resolved_user = cand
                    break

        has_ground_truth = resolved_target is not None
        total_transactions = len(df)
        total_hits = 0
        tp = 0
        fp = 0
        tn = 0
        fn = 0
        fraud_amount_caught = 0.0
        sample_hits: List[RuleBacktestSampleHit] = []

        records = df.to_dict(orient="records")
        for idx, row in enumerate(records):
            # Sanitize NaN values to None for clean JSON serialization and evaluation
            clean_row: Dict[str, Any] = {}
            for k, v in row.items():
                if isinstance(v, float) and math.isnan(v):
                    clean_row[str(k)] = None
                elif hasattr(v, "item"):
                    clean_row[str(k)] = v.item()
                else:
                    clean_row[str(k)] = v

            tx_id = str(clean_row.get(resolved_id) if resolved_id and clean_row.get(resolved_id) is not None else f"TX-{idx + 1:06d}")
            payload: Dict[str, Any] = {
                **clean_row,
                "transaction_id": tx_id,
                "raw": clean_row,
                "raw_features": clean_row,
                "mapped": clean_row,
                "mapped_features": clean_row,
                "enriched": clean_row,
                "enriched_features": clean_row,
            }

            try:
                is_triggered = bool(JsonLogicEvaluator.evaluate(condition, payload))
            except Exception:
                is_triggered = False

            gt_val: Optional[int] = None
            if has_ground_truth and resolved_target:
                raw_gt = clean_row.get(resolved_target)
                if raw_gt is not None:
                    try:
                        gt_val = 1 if int(float(raw_gt)) == 1 or raw_gt is True else 0
                    except (ValueError, TypeError):
                        gt_val = 1 if str(raw_gt).strip().lower() in ("1", "true", "fraud", "yes") else 0

            amt_val = 0.0
            if resolved_amount and clean_row.get(resolved_amount) is not None:
                try:
                    amt_val = float(clean_row[resolved_amount])
                except (ValueError, TypeError):
                    amt_val = 0.0

            if is_triggered:
                total_hits += 1
                if gt_val == 1:
                    tp += 1
                    fraud_amount_caught += amt_val
                elif gt_val == 0:
                    fp += 1
                else:
                    fraud_amount_caught += amt_val

                if len(sample_hits) < max_samples:
                    matched_clauses = self._extract_matched_clauses(condition, payload)
                    if not matched_clauses:
                        matched_clauses = [f"{rule_code} triggered"]
                    ts_str = str(clean_row.get(resolved_ts) or "—") if resolved_ts else "—"
                    user_str = str(clean_row.get(resolved_user) or "—") if resolved_user else "—"
                    sample_hits.append(
                        RuleBacktestSampleHit(
                            event_id=tx_id,
                            timestamp=ts_str,
                            amount=round(amt_val, 2),
                            user_id=user_str,
                            ground_truth=gt_val,
                            matched_clauses=matched_clauses,
                            features=clean_row,
                        )
                    )
            else:
                if gt_val == 1:
                    fn += 1
                elif gt_val == 0:
                    tn += 1

        execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        avg_execution_time_ms = round(execution_time_ms / max(1, total_transactions), 4)
        hit_rate = round(total_hits / total_transactions, 6) if total_transactions > 0 else 0.0
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        fpr = round(fp / (fp + tn), 6) if (fp + tn) > 0 else 0.0

        return RuleBacktestResult(
            rule_id=rule_id,
            rule_version_id=rule_version_id,
            version_number=version_number,
            rule_code=rule_code,
            rule_name=rule_name,
            action=action,
            dataset_artifact_id=dataset_artifact_id,
            total_transactions=total_transactions,
            total_hits=total_hits,
            hit_rate=hit_rate,
            has_ground_truth=has_ground_truth,
            target_column=resolved_target,
            tp=tp,
            fp=fp,
            tn=tn,
            fn=fn,
            precision=precision,
            recall=recall,
            fpr=fpr,
            fraud_amount_caught=round(fraud_amount_caught, 2),
            execution_time_ms=execution_time_ms,
            avg_execution_time_ms=avg_execution_time_ms,
            sample_hits=sample_hits,
        )
