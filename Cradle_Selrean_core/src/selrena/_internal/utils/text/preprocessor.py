# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from typing import List, Any


class MultimodalPreprocessor:
    """Utility used by tests; production logic resides in inference layer."""

    @staticmethod
    def sanitize_for_text_core(messages: List[Any]) -> List[str]:
        # simply coerce to strings for now
        return [str(m) for m in messages]

    @staticmethod
    def validate_ingress_payload(payload: Any):
        # mimic return values used by ai_service tests
        if isinstance(payload, dict):
            content = payload.get("content", "")
            has_visual = False
            is_valid = bool(content)
            return content, has_visual, is_valid
        return "", False, False
