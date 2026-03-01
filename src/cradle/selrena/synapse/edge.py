from typing import Any
from cradle.utils.logger import logger
from cradle.core.config_manager import global_config
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.string import clean_asr_transcript
from cradle.schemas.protocol.events import BaseEvent


class Edge:
    """
    边缘层 (Layer 2): 外层事务接入网关
    负责处理外围输入的标准化/规整与上行转发。
    不承担唤醒判定与意识流编排。
    """

    def __init__(self):
        self.bus = global_event_bus
        perception_cfg = global_config.get_system().perception
        accepted = getattr(perception_cfg, "accepted_modalities", ["text"])
        self.accepted_modalities = {m.lower() for m in accepted if isinstance(m, str)}
        if "text" not in self.accepted_modalities:
            self.accepted_modalities.add("text")
        self.vision_enabled = bool(perception_cfg.vision.enabled)
        logger.info("边缘层 (Edge) 初始化: 外层输入接入已就绪。")

    async def initialize(self):
        # 消费原始外层感知输入，统一后交给脊髓层。
        self.bus.subscribe("perception.audio.transcription", self.on_peripheral_transcription)
        self.bus.subscribe("perception.visual.snapshot", self.on_peripheral_visual)

    async def cleanup(self):
        self.bus.unsubscribe_receiver(self)

    def _modality_allowed(self, modality: str) -> bool:
        modality = modality.lower()
        if modality == "visual" and not self.vision_enabled:
            return False
        return modality in self.accepted_modalities

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

    async def _publish_ingress(self, text: str, payload: Any, modality: str, event_timestamp: float | None):
        normalized_text = clean_asr_transcript(text)
        if not normalized_text:
            return

        ingress_payload = {
            "text": normalized_text,
            "timestamp": payload.get("timestamp", event_timestamp) if isinstance(payload, dict) else event_timestamp,
            "source": payload.get("source", "audio") if isinstance(payload, dict) else "audio",
            "modality": modality,
        }
        if isinstance(payload, dict):
            if isinstance(payload.get("user_id"), int):
                ingress_payload["user_id"] = payload.get("user_id")
            if isinstance(payload.get("group_id"), int):
                ingress_payload["group_id"] = payload.get("group_id")
            if payload.get("raw") is not None:
                ingress_payload["raw"] = payload.get("raw")
            if payload.get("clean_text") is not None:
                ingress_payload["clean_text"] = payload.get("clean_text")

        logger.debug(f"[Edge] >>> Layer2上行({modality}): {normalized_text}")
        await self.bus.publish(BaseEvent(
            name="synapse.layer2.ingress",
            payload=ingress_payload,
            source="Edge"
        ))

    async def on_peripheral_transcription(self, event: Any):
        """处理外围输入并转为统一的 Layer2 上行格式。"""
        if not self._modality_allowed("text"):
            logger.debug("[Edge] text 模态未启用，已忽略 audio transcription。")
            return

        payload = event.payload if hasattr(event, "payload") else {}
        if isinstance(payload, dict):
            text = payload.get("text")
            if text is None and isinstance(payload.get("clean_text"), str):
                text = payload.get("clean_text")
        elif hasattr(payload, "text") and isinstance(payload.text, str):
            text = payload.text
        elif isinstance(payload, str):
            text = payload
        else:
            logger.debug(f"[Edge] 忽略不可识别输入类型: {type(payload).__name__}")
            return

        if not isinstance(text, str):
            logger.debug(f"[Edge] 忽略非文本输入字段: {type(text).__name__}")
            return

        text = text.strip()
        if not text:
            return

        await self._publish_ingress(
            text=text,
            payload=payload,
            modality="text",
            event_timestamp=getattr(event, "timestamp", None),
        )

    async def on_peripheral_visual(self, event: Any):
        """处理视觉输入；仅在配置允许视觉模态时放行。"""
        if not self._modality_allowed("visual"):
            logger.debug("[Edge] visual 模态未启用，已忽略视觉输入。")
            return

        payload = event.payload if hasattr(event, "payload") else {}
        visual_text = self._extract_visual_text(payload)
        if not isinstance(visual_text, str) or not visual_text.strip():
            logger.debug("[Edge] 视觉输入缺少可识别描述（text/ocr/caption/url），已忽略。")
            return

        await self._publish_ingress(
            text=visual_text,
            payload=payload,
            modality="visual",
            event_timestamp=getattr(event, "timestamp", None),
        )
