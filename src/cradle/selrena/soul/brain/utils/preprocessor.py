from typing import Any, Dict, List, Optional, Tuple, Union

from cradle.schemas.domain.chat import Message
from cradle.schemas.domain.multimodal import (
    AudioContent,
    ContentBlock,
    ImageContent,
    TextContent,
    VideoContent,
)
from cradle.utils.logger import logger

class MultimodalPreprocessor:
    """
    多模态数据预处理工具 (Multimodal Preprocessor).
    
    用于标准化、清洗和验证进入系统的感知数据。
    
    主要功能:
    1. Ingress Normalization: 将外部载荷转换为标准的 `Message` 对象。
    2. Data Cleaning: 清除 CQ 码、隐私敏感 URL 等噪声。
    3. Modality Extraction: 分离文本与多模态组件。
    4. Validation: 确保消息有效性，防止空消息进入核心流程。
    """

    @classmethod
    def normalize_ingress(cls, payload: Dict[str, Any]) -> Optional[Message]:
        """
        [Standardization]
        将原始载荷 (OneBot/Napcat Dict) 转换为标准 Message 对象。
        会自动尝试解析 content 字段为 List[ContentBlock]。
        """
        try:
            # Create a shallow copy to avoid modifying the original payload
            data = payload.copy()

            # 1. 基础字段映射
            # [Fix] Pydantic Message schema requires 'role' field.
            # If payload comes from Refex/Edge (ingress), it might not have 'role' set explicitly.
            # We assume it is 'user' if not present, but we must ensure it's in the data dict passed to Message(**data).
            if "role" not in data:
                data["role"] = "user"

            content = data.get("content", "")
            
            # 2. 如果 content 是列表，尝试清洗其中的 TextContent
            if isinstance(content, list):
                cleaned_content = []
                for item in content:
                    if isinstance(item, dict):
                        # 处理纯文本块的特殊清洗
                        if item.get("type") == "text":
                            # Copy the item dict
                            new_item = item.copy()
                            raw_text = new_item.get("text", "")
                            # [Optimization] Use simplified cleaner
                            cleaned_text = cls.cleanup_cq_codes(raw_text)
                            if cleaned_text:
                                new_item["text"] = cleaned_text
                                cleaned_content.append(new_item)
                        else:
                            cleaned_content.append(item)
                    # 处理 Pydantic 对象
                    elif isinstance(item, TextContent):
                        # Create a copy or new object
                        new_item = item.model_copy()
                        new_item.text = cls.cleanup_cq_codes(new_item.text)
                        if new_item.text:
                            cleaned_content.append(new_item)
                    else:
                        cleaned_content.append(item)
                
                # 更新清洗后的 content
                data["content"] = cleaned_content
            
            # 3. 如果 content 是字符串，直接清洗
            elif isinstance(content, str):
                data["content"] = cls.cleanup_cq_codes(content)

            # 4. 构建 Message 对象 (Pydantic 会自动验证结构)
            # 如果 content 为空且没有有效组件，可能在后续会被过滤，但此处仅做标准化
            return Message(**data)
            
        except Exception as e:
            logger.error(f"[Preprocessor] 消息标准化失败: {e} | Payload: {payload}")
            return None

    @staticmethod
    def cleanup_cq_codes(text: str) -> str:
        """
        [DEPRECATED] Removes noise from text.
        Logic for CQ codes has been moved to Vessel/Napcat modules.
        This now only performs basic whitespace cleanup.
        """
        if not text:
            return ""
            
        return text.strip()

    @staticmethod
    def _cleanup_multimedia_urls(text: str) -> str:
        """[DEPRECATED] Internal method."""
        return text

    @classmethod
    def validate_ingress_payload(cls, payload: Dict[str, Any]) -> Tuple[str, bool, bool]:
        """
        [Ingress Validation]
        验证并提取关键信息，供 Soul 快速决策。
        
        Returns:
            (pure_text, has_visual, is_valid)
        """
        # 1. 尝试标准化 (获取清洗后的数据)
        message = cls.normalize_ingress(payload)
        if not message:
            return "", False, False
            
        # 2. 提取信息
        pure_text = cls.extract_pure_text(message)
        has_visual = cls.has_visual_content(message)
        
        # 3. 综合判断
        is_valid = bool(pure_text or has_visual)
        
        return pure_text, has_visual, is_valid

    @staticmethod
    def extract_pure_text(message: Union[Message, Dict, str, List]) -> str:
        """
        [Text Extraction]
        从任意消息格式中提取纯文本。
        """
        content = ""
        if isinstance(message, Message):
            content = message.content
        elif isinstance(message, dict):
            content = message.get("content", "")
        elif isinstance(message, str):
            content = message
        elif isinstance(message, list):
            content = message
            
        if isinstance(content, str):
            return MultimodalPreprocessor.cleanup_cq_codes(content)
            
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, TextContent):
                    texts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                # 还可以扩展支持其他类型转文本
            
            full_text = " ".join(texts)
            return MultimodalPreprocessor.cleanup_cq_codes(full_text)
            
        return ""

    @staticmethod
    def has_visual_content(message: Message) -> bool:
        """
        [Modality Check]
        检查消息是否包含视觉组件 (Image/Video)。
        """
        content = message.content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, (ImageContent, VideoContent)):
                    return True
                # 兼容 Dict 形式 (如果在 Message 实例化前检查)
                if isinstance(block, dict):
                    t = block.get("type")
                    if t in ["image", "image_url", "video", "video_url"]:
                        return True
        return False

    @classmethod
    def normalize_messages(cls, messages: List[Union[Message, Dict[str, Any]]]) -> List[Message]:
        """
        [Batch Standardization]
        Strictly validate a list of messages.
        """
        normalized: List[Message] = []
        for msg in messages:
            if isinstance(msg, Message):
                normalized.append(msg)
            elif isinstance(msg, dict):
                # Reuse the ingress normalization logic if possible, or simple Pydantic validation
                try:
                    normalized.append(Message(**msg))
                except Exception:
                    # In strict mode, drop invalid messages
                    continue
        return normalized

    @staticmethod
    def to_llm_payload(messages: List[Union[Message, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        [Export Layer]
        Convert Message objects to dicts for LLM API consumption.
        """
        payload: List[Dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, Message):
                payload.append(msg.model_dump(include={"role", "content"}))
            elif isinstance(msg, dict):
                payload.append(msg)
        return payload

    @classmethod
    def sanitize_for_text_core(cls, messages: List[Message], vision_summary: Optional[str] = None) -> List[Message]:
        """
        [Dimensionality Reduction]
        Flatten multimodal content into pure text for text-only cores.
        """
        sanitized: List[Message] = []
        summary_text = (vision_summary or "").strip()
        last_visual_user_idx = -1

        # 1. Identify where to inject vision summary
        for idx, msg in enumerate(messages):
            if msg.role == "user" and cls.has_visual_content(msg):
                last_visual_user_idx = idx

        # 2. Process messages
        for idx, msg in enumerate(messages):
            new_msg = msg.model_copy()
            
            # Extract pure text
            final_text = cls.extract_pure_text(new_msg)
            has_image = cls.has_visual_content(new_msg)

            # Placeholder logic
            if has_image and not final_text:
                final_text = "（用户发送了一张图片）"

            # Inject Summary
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
    
    @classmethod
    def has_vision_payload_batch(cls, messages: List[Message]) -> bool:
        """[Batch Check] 检查消息列表中是否包含视觉内容"""
        if not messages:
            return False
        for msg in reversed(messages):
            if cls.has_visual_content(msg):
                return True
        return False

    @staticmethod
    def extract_last_vision_msg(messages: List[Message]) -> List[Message]:
        """提取最后一条包含视觉内容的用户消息"""
        if not messages:
            return []
            
        for msg in reversed(messages):
            if msg.role == "user" and MultimodalPreprocessor.has_visual_content(msg):
                return [msg]
        
        # Fallback to last user message if no vision found
        for msg in reversed(messages):
            if msg.role == "user":
                return [msg]
                
        return []
