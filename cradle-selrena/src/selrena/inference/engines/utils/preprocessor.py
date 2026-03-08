from typing import Any, Dict, List


class MultimodalPreprocessor:
    @staticmethod
    def sanitize_for_text_core(messages: List[Any]) -> List[Any]:
        # remove any non-text blocks when sending to pure text-only models
        sanitized: List[Any] = []
        for m in messages:
            if isinstance(m, dict) and m.get("type") != "text":
                continue
            sanitized.append(m)
        return sanitized

    @staticmethod
    def to_llm_payload(messages: List[Any]) -> List[Dict[str, Any]]:
        return [m if isinstance(m, dict) else {"text": str(m)} for m in messages]

    @staticmethod
    def validate_ingress_payload(payload: Any) -> (str, bool, bool):
        """Return (text, has_visual, is_valid).

        The soul only cares about whether there is any usable text or visual data.
        """
        text = ""
        has_visual = False
        is_valid = False

        if isinstance(payload, dict):
            # ExternalMultiModalPayload or similar
            content = payload.get("content")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # concatenate any text blocks
                pieces: list[str] = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        pieces.append(str(block.get("text", "")))
                    elif isinstance(block, str):
                        pieces.append(block)
                text = " ".join(pieces)
            # detect simple visual signal
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "image_url":
                        has_visual = True
            is_valid = bool(text or has_visual)
        else:
            text = str(payload) if payload is not None else ""
            is_valid = bool(text)
            # naive visual detection: url pattern
            if "http" in text or "base64" in text:
                has_visual = True

        return text, has_visual, is_valid

    @staticmethod
    def extract_pure_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                elif isinstance(block, str):
                    parts.append(block)
            return " ".join(parts)
        return str(content)

    @staticmethod
    def normalize_messages(messages: Any) -> List[Any]:
        """Ensure every history item is a ChatMessage-like dict object."""
        if not messages:
            return []
        normalized: list[Any] = []
        for msg in messages:
            if isinstance(msg, dict):
                # expect keys 'role' and 'content'
                normalized.append(msg)
            else:
                # fallback to string conversion
                normalized.append({"role": "user", "content": str(msg)})
        return normalized

    @staticmethod
    def has_visual_content(message: Any) -> bool:
        """Quick check whether the message contains an image_url block."""
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "image_url":
                        return True
        return False
