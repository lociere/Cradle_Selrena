from typing import Any, Dict, List, Union

from cradle.schemas.domain.chat import Message as ChatMessage
from cradle.schemas.domain.multimodal import ImageContent, TextContent


class PayloadSanitizer:
    """负责清洗和格式化载荷数据，尤其是针对多模态与纯文本不同模型接口的适配"""

    @staticmethod
    def normalize_messages(
        messages: List[Union[ChatMessage, Dict[str, Any]]],
    ) -> List[ChatMessage]:
        """
        [Standardization Layer]
        Strictly validate message structure.
        Only allows valid Message objects or fully compliant dicts.
        Ignores malformed data.
        """
        normalized: List[ChatMessage] = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                normalized.append(msg)
            elif isinstance(msg, dict):
                try:
                    # 尝试转换，Pydantic 会自动验证 content 是否符合 ContentBlock Union
                    normalized.append(ChatMessage(**msg))
                except Exception as e:
                    # 在严格模式下，丢弃无法解析的消息
                    continue
        return normalized

    @staticmethod
    def to_llm_payload(
        messages: List[Union[ChatMessage, Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        [Final Export Layer]
        Convert Message objects to dicts for LLM API consumption.
        """
        payload: List[Dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                payload.append(msg.model_dump(include={"role", "content"}))
            elif isinstance(msg, dict):
                payload.append(msg)
        return payload

    @staticmethod
    def sanitize_for_text_core(
        messages: List[ChatMessage],
        vision_summary: str | None = None,
    ) -> List[ChatMessage]:
        """
        [Dimensionality Reduction Layer]
        Flatten multimodal content into pure text for text-only cores.
        """
        sanitized: List[ChatMessage] = []
        summary_text = (vision_summary or "").strip()

        last_visual_user_idx = -1
        for idx, msg in enumerate(messages):
            if msg.role != "user":
                continue
            content = msg.content
            if isinstance(content, list):
                # Fix: content items are likely Pydantic models (ImageContent), not dicts
                has_image = False
                for item in content:
                    if isinstance(item, ImageContent):
                        has_image = True
                        break
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        has_image = True
                        break
                
                if has_image:
                    last_visual_user_idx = idx

        for idx, msg in enumerate(messages):
            new_msg = msg.model_copy()
            content = new_msg.content

            if isinstance(content, list):
                text_parts: List[str] = []
                has_image = False
                for item in content:
                    # [Standard] Handle ContentBlock Objects
                    if isinstance(item, TextContent):
                        text_parts.append(item.text)
                    elif isinstance(item, ImageContent):
                        has_image = True
                    # Handle other types if necessary (Audio/Video handled as non-text for now)

                final_text = " ".join(text_parts).strip()
                if has_image and not final_text:
                    final_text = "（用户发送了一张图片）"

                if idx == last_visual_user_idx and has_image and summary_text:
                    final_text = (
                        f"{final_text}\n"
                        "<visual_context>\n"
                        f"{summary_text}\n"
                        "</visual_context>\n"
                        "(System Note: The description above is from the vision module analyzing the user's image.)"
                    )

                new_msg.content = final_text

            sanitized.append(new_msg)

        return sanitized

    @staticmethod
    def extract_pure_text(content: Any) -> str:
        """从可能是多模态的 content 中提取纯文本用于纯文本场景"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                # 兼容 Pydantic Model (TextContent) 与 dict
                if isinstance(item, TextContent):
                    texts.append(item.text)
                elif isinstance(item, dict) and item.get("type") == "text":
                    text_val = item.get("text")
                    if isinstance(text_val, str):
                        texts.append(text_val)

            return " ".join(texts).strip()
        return ""

    @staticmethod
    def has_vision_payload(messages: List[ChatMessage]) -> bool:
        """检查是否包含需要视觉处理的图片模态数据"""
        if not messages:
            return False

        # 检查最新一条或所有消息（此处由原逻辑决定，通常是最后一条）
        for msg in reversed(messages):
            content = msg.content
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, ImageContent):
                        return True
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False

    @staticmethod
    def is_visual_request(messages: List[ChatMessage]) -> bool:
        """兼容路由层调用：判断请求中是否包含视觉模态"""
        return PayloadSanitizer.has_vision_payload(messages)

    @staticmethod
    def extract_last_vision_msg(messages: List[ChatMessage]) -> List[ChatMessage]:
        """提取最后一条包含视觉内容的用户消息；若不存在则返回最后一条用户消息"""
        if not messages:
            return []

        for msg in reversed(messages):
            if msg.role != "user":
                continue
            content = msg.content
            if isinstance(content, list):
                has_image = any(
                    isinstance(part, ImageContent) or
                    (isinstance(part, dict) and part.get("type") == "image_url")
                    for part in content
                )
                if has_image:
                    return [msg]

        for msg in reversed(messages):
            if msg.role == "user":
                return [msg]

        return []

