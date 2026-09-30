"""Tool definitions for the USFDS AI Investigation Agent.
Exposes standard Python functions wrapping usfds_core.InvestigationService.
"""

from typing import Any, Dict, List, Optional
from usfds_agent.config import (
    EVAL_PREDICTIONS_PATH,
    MODEL_ARTIFACT_PATH,
    PIPELINE_ARTIFACT_PATH,
    TEST_ENRICHED_PATH,
    TEST_PROCESSED_PATH,
)
from usfds_core.services.investigation import InvestigationService

# Global service instance initialized with pipeline artifacts
_service: Optional[InvestigationService] = None


def get_investigation_service() -> InvestigationService:
    """Returns the singleton InvestigationService instance."""
    global _service
    if _service is None:
        _service = InvestigationService(
            test_enriched_path=str(TEST_ENRICHED_PATH),
            eval_predictions_path=str(EVAL_PREDICTIONS_PATH),
            test_processed_path=str(TEST_PROCESSED_PATH),
            model_artifact_path=str(MODEL_ARTIFACT_PATH),
            pipeline_artifact_path=str(PIPELINE_ARTIFACT_PATH),
        )
    return _service


def get_case_summary(event_id: int) -> Dict[str, Any]:
    """Lấy thông tin chi tiết của giao dịch và điểm số rủi ro do mô hình dự đoán.

    Args:
        event_id: Mã định danh duy nhất của giao dịch (ví dụ: 3298, 9394).

    Returns:
        dict: Chứa số tiền (amount), thông tin thẻ/kênh, điểm rủi ro y_prob (0.0 - 1.0),
              mức độ rủi ro (risk_level), và trạng thái bảo mật (3DS, AVS, CVV).
    """
    service = get_investigation_service()
    case = service.get_case_summary(event_id)
    return case.model_dump()


def explain_prediction(event_id: int, top_k: int = 5) -> Dict[str, Any]:
    """Tính toán giải thích mô hình (SHAP feature attribution) cho giao dịch được gắn cờ.

    Args:
        event_id: Mã định danh duy nhất của giao dịch.
        top_k: Số lượng đặc trưng tác động hàng đầu muốn trả về (mặc định: 5).

    Returns:
        dict: Danh sách top_risk_factors (các yếu tố làm tăng xác suất gian lận)
              và top_mitigating_factors (các yếu tố chứng minh giao dịch an toàn).
    """
    service = get_investigation_service()
    explanation = service.explain_prediction(event_id, top_k=top_k)
    return explanation.model_dump()


def get_user_baseline(user_id: int, current_event_id: Optional[int] = None) -> Dict[str, Any]:
    """Lấy hồ sơ lịch sử và phân tích độ lệch hành vi của chủ tài khoản.

    Args:
        user_id: Mã định danh của người dùng/chủ tài khoản.
        current_event_id: Mã giao dịch hiện tại để so sánh độ lệch với lịch sử.

    Returns:
        dict: Số tiền chi tiêu trung bình, số giao dịch đã qua, các danh mục quen thuộc,
              tỷ lệ số tiền giao dịch này so với trung bình (amount_deviation_ratio),
              và cảnh báo nếu giao dịch ở quốc gia hoặc danh mục mới lạ.
    """
    service = get_investigation_service()
    baseline = service.get_user_baseline(user_id, current_event_id=current_event_id)
    return baseline.model_dump()


def search_related_cases(event_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Tìm kiếm các giao dịch có tương quan để phân tích mạng lưới / đường dây gian lận (Link Analysis).

    Args:
        event_id: Mã định danh giao dịch mục tiêu.
        limit: Số lượng giao dịch tương quan tối đa cần lấy.

    Returns:
        list: Danh sách các giao dịch khác cùng chủ tài khoản hoặc cùng tuyến vận chuyển rủi ro cao.
    """
    service = get_investigation_service()
    related = service.search_related_cases(event_id, limit=limit)
    return [r.model_dump() for r in related]
