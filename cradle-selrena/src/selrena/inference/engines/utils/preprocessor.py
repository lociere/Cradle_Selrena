from typing import List, Any


class MultimodalPreprocessor:
    """Placeholder used by tests; real implementation will live in inference layer."""

    @staticmethod
    def sanitize_for_text_core(messages: List[Any]) -> List[str]:
        # simply convert to strings
        return [str(m) for m in messages]

    @staticmethod
    def validate_ingress_payload(payload: Any):
        # mimic return values used by ai_service
        if isinstance(payload, dict):
            content = payload.get("content", "")
            has_visual = False
            is_valid = bool(content)
            return content, has_visual, is_valid
        return "", False, False
