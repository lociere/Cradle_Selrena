from typing import Any, List

from cradle.core.config_manager import global_config
from cradle.core.lifecycle import global_lifecycle
from cradle.schemas.domain.multimodal import (AudioContent, ContentBlock,
                                              ImageContent, TextContent,
                                              VideoContent)
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger


class Edge:
    """
    边缘层 (Synapse Layer 2 - Edge Gateway)。
    
    作为系统的"感觉神经末梢"，负责：
    1. 接收来自 Vessel 的统一感知事件 `perception.message`。
    2. 按配置进行模态过滤与内容降级，保证 Soul 看到的是可消费语义。
    3. 将规范化后的载荷上行到 Reflex (`synapse.layer2.ingress`)。
    
    设计原则：
    - 无状态 (Stateless)：不维护对话上下文。
    - 快速响应 (Low Latency)：仅做协议规整，不做认知推理。
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
        
        注册通用感知事件监听器：
        - `perception.message`: 内部/外部双载荷的统一入口。
        """
        global_lifecycle.register(self)
        
        # 通用多模态消息统一入口
        self.bus.subscribe("perception.message", self.on_perception_message)

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

    async def on_perception_message(self, event: BaseEvent):
        """
        处理统一感知事件 `perception.message`。
        
        输入可为 Internal/External 感知载荷（对象或字典）。
        本层仅根据模态做轻量分流，并保持 payload 语义不被业务逻辑污染。
        """
        payload = event.payload
        if not payload:
            return
            
        # 从 payload 或 event 中提取 modality
        modality = getattr(event, 'modality', None)
        if not modality and isinstance(payload, dict):
            modality = payload.get('modality', 'text')
        elif not modality and hasattr(payload, 'modality'):
            modality = payload.modality
            
        # 统一转换为字符串 (兼容 Modality 枚举)
        if hasattr(modality, 'value'):
            modality = modality.value
            
        modality_str = str(modality).lower()
        
        # 路由到对应的内部处理器
        # [Design] 文本/音频/混合走通用语义上行；视觉走视觉上行
        if modality_str in ('text', 'audio', 'multimodal'):
            # 混合消息通常以文本语义为主，视觉块作为补充
            await self.on_peripheral_transcription(event)
        elif modality_str in ('visual', 'image', 'video'):
            await self.on_peripheral_visual(event)
        else:
            # 未知模态，默认作为文本处理
            logger.debug(f"[Edge] 未知模态 '{modality}'，作为文本处理")
            await self.on_peripheral_transcription(event)

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
        """发布 Layer2 标准上行事件。"""
        
        if not isinstance(payload, dict):
             return
             
        # [Strict] 仅接受标准 PerceptionPayload 字典
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

        # [Payload Reconstruction] 按协议分区构建字典
        # 仅保留显式传入键，避免默认占位字段污染上游语义。
        ingress_payload = {
            # --- 1. Core Content ---
            "modality": modality,
            "source": source,
            "content": content,
        }

        timestamp = payload.get("timestamp", event_timestamp)
        if timestamp is not None:
            ingress_payload["timestamp"] = timestamp

        # --- 2. Attention Protocol ---
        for key in ("vessel_id", "source_type", "source_id", "is_strong_wake", "is_external_source"):
            if key in payload:
                ingress_payload[key] = payload[key]

        # --- 3. Context Metadata ---
        for key in ("name", "metadata", "external_history"):
            if key in payload:
                ingress_payload[key] = payload[key]

        # --- 4. Debug ---
        if "raw" in payload:
            ingress_payload["raw"] = payload["raw"]

        logger.debug(f"[Edge] >>> Layer2上行: {summary}")
        await self.bus.publish(BaseEvent(
            name="synapse.layer2.ingress",
            payload=ingress_payload,
            source="Edge"
        ))

    async def on_peripheral_transcription(self, event: Any):
        """
        处理文本/语音语义输入事件。
        
        Logic:
            1. 将载荷对象规整为紧凑 dict（仅显式字段）。
            2. 校验 `content` 是否存在。
            3. 发布标准化 `synapse.layer2.ingress`。
        """
        # [Strict Mode] 仅处理标准 payload 字典或对象
        # 严格要求通过 'content' 字段传递信息
        payload = event.payload
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(exclude_unset=True, exclude_none=True)
            
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
        处理视觉语义输入事件。
        
        Logic:
            1. 检查视觉模态是否启用。
            2. 校验 `content` 是否存在。
            3. 发布标准化 `synapse.layer2.ingress`。
        """
        if not self._modality_allowed("visual"):
            return

        payload = event.payload
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(exclude_unset=True, exclude_none=True)
        
        # [Strict Mode] payload Must be dict and has content
        if not isinstance(payload, dict) or not payload.get("content"):
             return

        await self._publish_ingress(
            payload=payload,
            modality="visual",
            event_timestamp=getattr(event, "timestamp", None),
        )
