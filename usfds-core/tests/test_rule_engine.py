import unittest
from uuid import uuid4

from usfds_core.domain.entities.enums import RuleAction, RuleStatus
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.domain.schemas.rule_schemas import RuleExecutionContext, RuleExecutionResult
from usfds_core.services.rule_engine.executor import JsonLogicEvaluator, RuleExecutor
from usfds_core.services.rule_engine.manager import RuleManager


class TestJsonLogicEvaluator(unittest.TestCase):
    """Unit tests covering the JsonLogicEvaluator engine."""

    def test_var_extraction(self):
        data = {
            "amount": 100,
            "user": {"profile": {"age": 25, "country": "VN"}},
            "tags": ["vip", "mobile"],
        }
        self.assertEqual(JsonLogicEvaluator.evaluate({"var": "amount"}, data), 100)
        self.assertEqual(JsonLogicEvaluator.evaluate({"var": "user.profile.age"}, data), 25)
        self.assertEqual(JsonLogicEvaluator.evaluate({"var": "user.profile.country"}, data), "VN")
        self.assertIsNone(JsonLogicEvaluator.evaluate({"var": "user.non_existing"}, data))
        # Default value fallback
        self.assertEqual(JsonLogicEvaluator.evaluate({"var": ["missing", 999]}, data), 999)

    def test_comparisons(self):
        data = {"amount": 500, "code": "ABC"}
        self.assertTrue(JsonLogicEvaluator.evaluate({">": [{"var": "amount"}, 100]}, data))
        self.assertFalse(JsonLogicEvaluator.evaluate({">": [{"var": "amount"}, 1000]}, data))
        self.assertTrue(JsonLogicEvaluator.evaluate({">=": [{"var": "amount"}, 500]}, data))
        self.assertTrue(JsonLogicEvaluator.evaluate({"<": [{"var": "amount"}, 600]}, data))
        self.assertTrue(JsonLogicEvaluator.evaluate({"<=": [{"var": "amount"}, 500]}, data))
        self.assertTrue(JsonLogicEvaluator.evaluate({"==": [{"var": "code"}, "ABC"]}, data))
        self.assertTrue(JsonLogicEvaluator.evaluate({"!=": [{"var": "code"}, "XYZ"]}, data))

    def test_between_comparison(self):
        data = {"amount": 250}
        # 100 < amount < 300
        self.assertTrue(JsonLogicEvaluator.evaluate({"<": [100, {"var": "amount"}, 300]}, data))
        self.assertFalse(JsonLogicEvaluator.evaluate({"<": [300, {"var": "amount"}, 500]}, data))

    def test_logical_operators(self):
        data = {"amount": 1000, "channel": "ONLINE", "is_flagged": False}
        # AND
        rule_and = {
            "and": [
                {">": [{"var": "amount"}, 500]},
                {"==": [{"var": "channel"}, "ONLINE"]},
            ]
        }
        self.assertTrue(JsonLogicEvaluator.evaluate(rule_and, data))

        # OR
        rule_or = {
            "or": [
                {"==": [{"var": "channel"}, "POS"]},
                {">": [{"var": "amount"}, 500]},
            ]
        }
        self.assertTrue(JsonLogicEvaluator.evaluate(rule_or, data))

        # NOT (!)
        self.assertTrue(JsonLogicEvaluator.evaluate({"!": {"var": "is_flagged"}}, data))

    def test_in_operator(self):
        data = {"channel": "ONLINE", "email": "fraudster@tempmail.com"}
        self.assertTrue(JsonLogicEvaluator.evaluate({"in": [{"var": "channel"}, ["ONLINE", "MOBILE"]]}, data))
        self.assertFalse(JsonLogicEvaluator.evaluate({"in": [{"var": "channel"}, ["ATM", "POS"]]}, data))
        # Substring in string
        self.assertTrue(JsonLogicEvaluator.evaluate({"in": ["tempmail.com", {"var": "email"}]}, data))

    def test_regex_operator(self):
        data = {"bin": "411111", "email": "test@gmail.com"}
        # Visa BIN pattern
        self.assertTrue(JsonLogicEvaluator.evaluate({"regex": ["^4[0-9]{5}", {"var": "bin"}]}, data))
        self.assertFalse(JsonLogicEvaluator.evaluate({"regex": ["^5[1-5][0-9]{4}", {"var": "bin"}]}, data))


class TestRuleExecutor(unittest.TestCase):
    """Unit tests for RuleExecutor evaluate_rule and evaluate_rules."""

    def setUp(self):
        self.executor = RuleExecutor()
        self.project_id = uuid4()
        self.rule = Rule(
            project_id=self.project_id,
            rule_code="R_ONLINE_HIGH_AMOUNT",
            name="High Amount Online Transaction",
            description="Trigger review for online transactions exceeding 50M",
            status=RuleStatus.ACTIVE,
        )
        self.version = RuleVersion(
            rule_id=self.rule.rule_id,
            version_number=1,
            condition={
                "and": [
                    {">": [{"var": "mapped.amount"}, 50000000]},
                    {"in": [{"var": "mapped.channel"}, ["ONLINE", "MOBILE"]]},
                ]
            },
            action=RuleAction.REJECT,
        )

    def test_single_rule_evaluation_triggered(self):
        ctx = RuleExecutionContext(
            transaction_id="TX_1001",
            mapped_features={"amount": 75000000, "channel": "ONLINE"},
            enriched_features={},
        )
        result: RuleExecutionResult = self.executor.evaluate_rule(self.rule, self.version, ctx)

        self.assertEqual(result.rule_id, str(self.rule.rule_id))
        self.assertEqual(result.rule_version_id, str(self.version.rule_version_id))
        self.assertEqual(result.version_number, 1)
        self.assertEqual(result.rule_code, "R_ONLINE_HIGH_AMOUNT")
        self.assertTrue(result.is_triggered)
        self.assertEqual(result.action, RuleAction.REJECT)
        self.assertIn("triggered", result.trigger_reason)
        self.assertGreater(result.execution_time_ms, 0.0)

    def test_single_rule_evaluation_not_triggered(self):
        ctx = RuleExecutionContext(
            transaction_id="TX_1002",
            mapped_features={"amount": 10000000, "channel": "ONLINE"},
            enriched_features={},
        )
        result = self.executor.evaluate_rule(self.rule, self.version, ctx)

        self.assertFalse(result.is_triggered)
        self.assertEqual(result.action, RuleAction.REJECT)
        self.assertIn("not satisfied", result.trigger_reason)

    def test_multiple_rules_evaluation(self):
        rule2 = Rule(
            project_id=self.project_id,
            rule_code="R_SUSPICIOUS_VELOCITY",
            name="Suspicious 1-Hour Velocity",
            description="Trigger alert if transactions in 1 hour > 5",
            status=RuleStatus.ACTIVE,
        )
        version2 = RuleVersion(
            rule_id=rule2.rule_id,
            version_number=1,
            condition={">": [{"var": "enriched.tx_count_1h"}, 5]},
            action=RuleAction.REVIEW,
        )

        ctx = RuleExecutionContext(
            transaction_id="TX_1003",
            mapped_features={"amount": 20000000, "channel": "ONLINE"},  # Rule 1 fails (amount < 50M)
            enriched_features={"tx_count_1h": 8},                      # Rule 2 passes (8 > 5)
        )

        pairs = [(self.rule, self.version), (rule2, version2)]
        results = self.executor.evaluate_rules(pairs, ctx)

        self.assertEqual(len(results), 2)
        # Rule 1
        self.assertFalse(results[0].is_triggered)
        self.assertEqual(results[0].rule_code, "R_ONLINE_HIGH_AMOUNT")
        # Rule 2
        self.assertTrue(results[1].is_triggered)
        self.assertEqual(results[1].rule_code, "R_SUSPICIOUS_VELOCITY")
        self.assertEqual(results[1].action, RuleAction.REVIEW)

    def test_context_flat_fallback(self):
        # Test rules that use flat keys {"var": "amount"} instead of {"var": "mapped.amount"}
        flat_rule = Rule(
            project_id=self.project_id,
            rule_code="R_FLAT_KEY",
            name="Flat Key Access",
            description="Access amount directly",
        )
        flat_version = RuleVersion(
            rule_id=flat_rule.rule_id,
            version_number=1,
            condition={">": [{"var": "amount"}, 500]},
            action=RuleAction.REVIEW,
        )
        ctx = RuleExecutionContext(
            transaction_id="TX_1004",
            mapped_features={"amount": 1000},
            enriched_features={},
        )
        res = self.executor.evaluate_rule(flat_rule, flat_version, ctx)
        self.assertTrue(res.is_triggered)

    def test_backtest_dataframe_with_ground_truth(self):
        import pandas as pd

        df = pd.DataFrame(
            [
                {"event_id": "TX-1", "timestamp": "2026-10-01 01:00:00", "user_id": "U1", "amount": 5000.0, "channel": "ONLINE", "is_fraud": 1},
                {"event_id": "TX-2", "timestamp": "2026-10-01 02:00:00", "user_id": "U2", "amount": 3000.0, "channel": "ONLINE", "is_fraud": 0},
                {"event_id": "TX-3", "timestamp": "2026-10-01 03:00:00", "user_id": "U3", "amount": 500.0, "channel": "POS", "is_fraud": 1},
                {"event_id": "TX-4", "timestamp": "2026-10-01 04:00:00", "user_id": "U4", "amount": 200.0, "channel": "ONLINE", "is_fraud": 0},
            ]
        )
        condition = {
            "and": [
                {">": [{"var": "amount"}, 2000]},
                {"==": [{"var": "channel"}, "ONLINE"]},
            ]
        }
        bt = self.executor.backtest_dataframe(
            df=df,
            condition=condition,
            action=RuleAction.REJECT,
            dataset_artifact_id="art-001",
            rule_code="R-TEST-BT",
            rule_name="Test Backtest Rule",
        )
        self.assertEqual(bt.total_transactions, 4)
        self.assertEqual(bt.total_hits, 2)
        self.assertAlmostEqual(bt.hit_rate, 0.5)
        self.assertTrue(bt.has_ground_truth)
        self.assertEqual(bt.tp, 1)
        self.assertEqual(bt.fp, 1)
        self.assertEqual(bt.tn, 1)
        self.assertEqual(bt.fn, 1)
        self.assertAlmostEqual(bt.precision, 0.5)
        self.assertAlmostEqual(bt.recall, 0.5)
        self.assertAlmostEqual(bt.fpr, 0.5)
        self.assertAlmostEqual(bt.fraud_amount_caught, 5000.0)
        self.assertEqual(len(bt.sample_hits), 2)
        self.assertEqual(bt.sample_hits[0].event_id, "TX-1")
        self.assertIn("amount > 2000", bt.sample_hits[0].matched_clauses)


if __name__ == "__main__":
    unittest.main()
