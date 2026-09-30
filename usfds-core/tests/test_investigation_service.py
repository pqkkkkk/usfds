from pathlib import Path
import pytest
from usfds_core.services.investigation import InvestigationService

def test_investigation_service_real_artifacts():
    base_dir = Path(__file__).resolve().parent.parent.parent
    test_enriched_path = base_dir / "storage_output/datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f/test_enriched.parquet"
    eval_predictions_path = base_dir / "storage_output/models/b43d7c31-2cc4-4fb1-9369-cdb42d5abc01/runs/47b106ec-388b-44db-83d3-a8d7c7e711df/eval_predictions.parquet"
    test_processed_path = base_dir / "storage_output/datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/d9bb0c4f-0f7c-4d51-9fd3-cbbe9e7c18fd/test_processed.parquet"
    model_artifact_path = base_dir / "storage_output/models/b43d7c31-2cc4-4fb1-9369-cdb42d5abc01/runs/47b106ec-388b-44db-83d3-a8d7c7e711df/model.joblib"
    pipeline_artifact_path = base_dir / "storage_output/datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/d9bb0c4f-0f7c-4d51-9fd3-cbbe9e7c18fd/fitted_pipeline.joblib"

    if not test_enriched_path.exists():
        pytest.skip("Integration artifacts not found")

    service = InvestigationService(
        test_enriched_path=str(test_enriched_path),
        eval_predictions_path=str(eval_predictions_path),
        test_processed_path=str(test_processed_path),
        model_artifact_path=str(model_artifact_path),
        pipeline_artifact_path=str(pipeline_artifact_path),
    )

    # 1. get_case_summary
    case = service.get_case_summary(3298)
    assert case.event_id == 3298
    assert case.y_prob >= 0.90
    assert case.risk_level == "CRITICAL"
    print("\nCase summary retrieved:", case.event_id, case.amount, case.y_prob, case.risk_level)

    # 2. explain_prediction
    exp = service.explain_prediction(3298, top_k=3)
    assert exp.event_id == 3298
    assert len(exp.top_risk_factors) > 0
    top_factor = exp.top_risk_factors[0]
    assert top_factor.importance_score > 0
    assert "Shipping" in top_factor.display_name or "shipping" in top_factor.feature_name

    # 3. get_user_baseline
    user_base = service.get_user_baseline(case.user_id, current_event_id=case.event_id)
    assert user_base.user_id == case.user_id
    assert user_base.total_transactions_history >= 1

    # 4. search_related_cases
    related = service.search_related_cases(3298, limit=3)
    assert isinstance(related, list)
