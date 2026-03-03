from typing import Any, List

from cradle.core.config_manager import global_config
from cradle.core.lifecycle import global_lifecycle
from cradle.schemas.domain.multimodal import (AudioContent, ContentBlock,
                                              ImageContent, TextContent,
                                              VideoContent)
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger
from cradle.utils.string import clean_asr_transcript


class Edge:
    """
    边缘层 (Synapse Layer 2 - Edge Gateway)。
    
    作为系统的"感觉神经末梢"，负责：
    1. 接收来自外围设备 (Vessel) 的原始感知信号 (Audio Transcription, Visual Snapshot)。
    2. 执行初步过滤 (Modality Filtering) 和标准化 (Standardization)。
    3. 将清洗后的信号转发给脊髓层 (Reflex)，不进行深层认知处理。
    
    设计原则：
    - 无状态 (Stateless)：不维护对话上下文。
    - 快速响应 (Low Latency)：仅做格式转换，避免阻塞。
    """

    def __init__(self):
        self.bus = global_event_bus
        perception_cfg = global_config.get_system().perception
        accepted = getattr(perception_cfg, "accepted_modalities", ["text"])
        self.accepted_modalities = {m.lower()
                                    for m in accepted if isinstance(m, str)}
        if "text" not in self.accepted_modalities:
            self.accepted_modalities.add("text")
        self.vision_enabled = bool(perception_cfg.vision.enabled)
        # 即使 audio 总是默认支持，也将其显式加入可接受列表
        if not hasattr(perception_cfg, "accepted_modalities") or not perception_cfg.accepted_modalities:
             self.accepted_modalities.add("audio")
        logger.info(f"边缘层 (Edge) 初始化: 支持模态 {self.accepted_modalities}")

    async def initialize(self):
        """
        初始化边缘层网关。
        
        注册对基础感知事件的监听器：
        - `perception.audio.transcription`: 监听语音转录/文本输入。
        - `perception.visual.snapshot`: 监听视觉快照输入。
        """
        global_lifecycle.register(self)
        self.bus.subscribe("perception.audio.transcription",
                           self.on_peripheral_transcription)
        self.bus.subscribe("perception.visual.snapshot",
                           self.on_peripheral_visual)

    async def cleanup(self):
        self.bus.unsubscribe_receiver(self)

    def _modality_allowed(self, modality: str) -> bool:
         # [Upgrade] 细力度的模态检查
        modality = modality.lower()
        if modality == "visual" and not self.vision_enabled:
            return False
        return modality in self.accepted_modalities or modality == "text" # Text is always allowed

    def _downgrade_content(self, content: List[Any]) -> List[ContentBlock]:
        """
        [Content Adaptation]
        根据感知配置，对不支持的多模态内容进行降级处理。
        例如：如果视觉模态未启用，将图片降级为文本占位符。
        """
        processed = []

        is_visual_allowed = self.vision_enabled and ("visual" in self.accepted_modalities)
        is_audio_allowed = "audio" in self.accepted_modalities

        for item in content:
            block = item
            
            # Instantiation for type checking
            if isinstance(item, dict):
                 typ = item.get("type", "text")
                 try:
                    if typ == "image_url": block = ImageContent(**item)
                    elif typ == "audio_url": block = AudioContent(**item)
                    elif typ == "video_url": block = VideoContent(**item)
                    elif typ == "text": block = TextContent(**item)
                 except Exception:
                    continue

            # 1. Visual Downgrade
            if isinstance(block, (ImageContent, VideoContent)):
                 if not is_visual_allowed:
                      desc = "[图片]" if isinstance(block, ImageContent) else "[视频]"
                      processed.append(TextContent(text=f"(系统忽略了{desc})"))
                      continue

            # 2. Audio Downgrade
            elif isinstance(block, AudioContent):
                 if not is_audio_allowed:
                      processed.append(TextContent(text="(系统忽略了[音频])"))
                      continue

            # 3. Pass Valid Content
            processed.append(block)
            
        return processed

    def _extract_visual_text(self, payload: Any) -> str | None:
        if isinstance(payload, dict):
            for key in ("text", "ocr_text", "caption", "description", "title", "alt_text"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            for key in ("image_url", "url", "image_path", "path", "file"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return f"【视觉输入】{value.strip()}"

        return None

    async def _publish_ingress(self, payload: Any, modality: str, event_timestamp: float | None):
        """Standardized Layer 2 Ingress Publisher"""
        
        if not isinstance(payload, dict):
             return
             
        # [Strict] 仅接受标准 MultiModalPayload 字典
        raw_content = payload.get("content")
        if not raw_content:
            return
            
        # [Optimization] Apply Config-Aware Downgrade
        # 根据配置文件过滤 content
        content = self._downgrade_content(raw_content)
        if not content:
             logger.debug(f"[Edge] 内容因配置过滤而为空，忽略上行: {raw_content}")
             return

        source = payload.get("source", "audio")
        
        # 构建一个简单的摘要用于日志，不放入 payload
        summary = f"[{modality}] Includes {len(content)} blocks"

        ingress_payload = {
            "content": content,
            "timestamp": payload.get("timestamp", event_timestamp) if isinstance(payload, dict) else event_timestamp,
            "source": source,
            "modality": modality,
            # Pass-through specific IDs
            "user_id": payload.get("user_id"),
            "group_id": payload.get("group_id"),
            "raw": payload.get("raw")
        }

        logger.debug(f"[Edge] >>> Layer2上行: {summary}")
        await self.bus.publish(BaseEvent(
            name="synapse.layer2.ingress",
            payload=ingress_payload,
            source="Edge"
        ))

    async def on_peripheral_transcription(self, event: Any):
        """
        处理语音转录 (Transcription) 或文本输入事件。
        
        Logic:
            1. 校验负载格式 (必须为 `MultiModalPayload`)。
            2. 检查系统是否允许文本模态 (Default Allowed)。
            3. 将事件标准化为 `synapse.layer2.ingress` 上行事件。
        """
        # [Strict Mode] 仅处理标准 payload 字典或对象
        # 严格要求通过 'content' 字段传递信息
        payload = event.payload
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
            
        if not isinstance(payload, dict):
             return

        # 任何有效输入都至少应该有 content 列表
        content = payload.get("content")
        if not content:
             return

        if not self._modality_allowed("text"):
            # TODO: 深入检查 ContentBlock 类型
            pass 

        await self._publish_ingress(
            payload=payload,
            modality="text", # 基础模态标记
            event_timestamp=getattr(event, "timestamp", None),
        )

    async def on_peripheral_visual(self, event: Any):
        """
        处理视觉快照 (Visual Snapshot) 事件。
        
        Logic:
            1. 检查 'vision' 模态是否启用 (`config.perception.vision.enabled`)。
            2. 若禁用则直接丢弃，避免无谓的资源消耗。
            3. 校验并标准化为 `synapse.layer2.ingress` 上行事件。
        """
        if not self._modality_allowed("visual"):
            return

        payload = event.payload
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        
        # [Strict Mode] payload Must be dict and has content
        if not isinstance(payload, dict) or not payload.get("content"):
             return

        await self._publish_ingress(
            payload=payload,
            modality="visual",
            event_timestamp=getattr(event, "timestamp", None),
        )
