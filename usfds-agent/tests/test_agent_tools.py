from usfds_agent.tools import (
    explain_prediction,
    get_case_summary,
    get_user_baseline,
    search_related_cases,
)


def test_agent_tools_return_valid_schemas():
    # 1. get_case_summary for True Positive case 3298
    case = get_case_summary(3298)
    assert case["event_id"] == 3298
    assert case["y_prob"] >= 0.90
    assert case["risk_level"] == "CRITICAL"
    assert "amount" in case
    assert "country" in case

    # 2. explain_prediction (SHAP attribution)
    exp = explain_prediction(3298, top_k=3)
    assert exp["event_id"] == 3298
    assert len(exp["top_risk_factors"]) > 0
    assert "importance_score" in exp["top_risk_factors"][0]

    # 3. get_user_baseline
    user_id = case["user_id"]
    baseline = get_user_baseline(user_id, current_event_id=3298)
    assert baseline["user_id"] == user_id
    assert "avg_amount_history" in baseline
    assert "amount_deviation_ratio" in baseline

    # 4. search_related_cases
    related = search_related_cases(3298, limit=3)
    assert isinstance(related, list)
