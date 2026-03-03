import re
import time
from typing import Any, List

from cradle.core.config_manager import global_config
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.schemas.protocol.events.reflex import ReflexSignal, ReflexType
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger


class Reflex:
    """
    脊髓层 (Layer 1): 负责快速反射、生存本能、唤醒机制与意识流编排。
    不经过深度思考，直接拦截或触发行为，并决定哪些输入可上行到意识层。
    """

    def __init__(self):
        self.bus = global_event_bus
        self.last_wake_time = 0
        self.non_text_chain_until = 0.0
        perception_cfg = global_config.get_system().perception
        self.strict_wake = bool(perception_cfg.strict_wake_word)
        self.wake_timeout = float(perception_cfg.wake_timeout_sec)
        self.non_text_chain_timeout = float(
            getattr(perception_cfg, "non_text_chain_timeout_sec", self.wake_timeout))
        self.is_awake = False

        # 硬编码的生存本能关键词
        self.wake_keywords_zh = [
            "月见", "赛琳娜", "色瑞娜", "瑟瑞娜", "塞琳娜", "赛琳",
            "赛瑞娜", "萨琳娜", "你好", "@月见"
        ]
        self.wake_keywords_en = [
            "selrena", "serena", "salrena", "serina", "selina", "celina",
            "hello", "hi", "hey"
        ]
        self.exit_keywords_zh = ["退出", "关闭", "休眠"]
        self.exit_keywords_en = ["shutdown", "exit", "sleep", "goodbye", "bye"]

        self.stop_keywords = ["别说了", "闭嘴", "停下", "stop", "shutup", "quiet"]

        if self.strict_wake:
            logger.info("[Reflex] 使用严格唤醒模式：仅唤醒词维持唤醒。")
        else:
            logger.info(
                f"[Reflex] 使用宽松唤醒模式：唤醒后 {self.wake_timeout:.0f}s 内可免唤醒词。")

        logger.info("脊髓反射中枢 (Reflex) 初始化...")

    async def initialize(self):
        # 订阅 Layer2 规整后的外围输入
        self.bus.subscribe("synapse.layer2.ingress", self.on_layer2_ingress)

    async def cleanup(self):
        self.bus.unsubscribe_receiver(self)

    def _match_keywords(self, text: str, zh_list: List[str], en_list: List[str]) -> bool:
        text_clean = text.lower()
        if any(kw in text_clean for kw in zh_list):
            return True
        for kw in en_list:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_clean):
                return True
        return False

    async def on_layer2_ingress(self, event: Any):
        # 兼容 Event 对象或 Pydantic 对象
        payload = event.payload if hasattr(event, "payload") else {}
        modality = "text"
        
        # [Standardization] 仅处理字典，必须包含 content
        if not isinstance(payload, dict):
             return

        # 尝试从 content 提取文本摘要，如果 text 字段为空
        content = payload.get("content", [])
        if not content:
             return
            
        text = ""
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                break # Just get first for summary
            # Pydantic model support
            if hasattr(block, "type") and block.type == "text":
                text = block.text
                break

        payload_modality = payload.get("modality")
        if isinstance(payload_modality, str) and payload_modality.strip():
            modality = payload_modality.strip().lower()

        normalized_text = text.strip()
        text_for_match = normalized_text.lower()
        is_non_text = modality != "text"

        # 1. 紧急停止反射 (Immediate Halt)
        if any(w in text_for_match for w in self.stop_keywords):
            logger.warning(f"[Reflex] ⏹️ 收到停止指令: {normalized_text}")
            # 发出脊髓信号，Mouth 应该订阅这个信号并立即停止
            signal = ReflexSignal(reflex_type=ReflexType.MUTE, source="Reflex")
            await self.bus.publish(signal)

        # 2. 生存安全反射 (Shutdown)
        if self._match_keywords(text_for_match, self.exit_keywords_zh, self.exit_keywords_en):
            logger.critical(f"[Reflex] 🛑 收到关机指令: {normalized_text}")
            await self.bus.publish(BaseEvent(name="system.shutdown", payload={"reason": "voice_command"}, source="Reflex"))
            return

        # 3. 唤醒机制 (Arousal System)
        current_time = time.time()
        has_wake_word_matched = self._match_keywords(
            text_for_match, self.wake_keywords_zh, self.wake_keywords_en
        )
        previous_awake_state = self.is_awake

        # [Logic Fix] 只要检测到唤醒词，无论当前是否唤醒，都重置最后唤醒时间
        if has_wake_word_matched:
            self.last_wake_time = current_time
            logger.info(f"[Reflex] ⚡ 唤醒词激活: {normalized_text}")
        
        # [Behavior Change] 即使没有唤醒词，只要还在唤醒窗口内且收到消息，
        # 应该视为“用户正在跟我说话”，从而续期唤醒时间。
        # 否则如果不带唤醒词的连续对话超过20秒（单方面陈述），她就会睡着。
        elif self.is_awake and not self.strict_wake:
             # 宽松模式下，收到任何有效输入都续期
             self.last_wake_time = current_time
             logger.debug(f"[Reflex] ⚡ 连续对话续期 ({self.wake_timeout}s)")

        # 计算当前唤醒状态
        if self.strict_wake:
            self.is_awake = has_wake_word_matched
        else:
            # 宽松模式：有唤醒词 OR 在超时窗口内
            time_since_wake = current_time - self.last_wake_time
            if time_since_wake < self.wake_timeout:
                self.is_awake = True
            else:
                self.is_awake = False
        
        # 状态变更日志
        if previous_awake_state and not self.is_awake:
             logger.info(f"[Reflex] 💤 注意力耗尽 (空闲 {current_time - self.last_wake_time:.1f}s > {self.wake_timeout}s) -> 意识休眠")
        elif not previous_awake_state and self.is_awake:
             logger.info("[Reflex] ⚡ 意识已上线")

        # 4. 发布全局唤醒状态（由皮质层消费）
        await self.bus.publish(BaseEvent(
            name="state.arousal",
            payload={
                "is_awake": self.is_awake,
                "has_wake_word": has_wake_word_matched,
                "strict_wake_word": self.strict_wake,
                "wake_timeout_sec": self.wake_timeout,
            },
            source="Reflex"
        ))

        # 5. 脊髓层意识流编排：决定是否上行给 Soul
        within_non_text_chain = is_non_text and current_time <= self.non_text_chain_until
        allow_to_conscious = has_wake_word_matched if self.strict_wake else self.is_awake
        if within_non_text_chain:
            allow_to_conscious = True

        if not allow_to_conscious:
            return

        if is_non_text:
            self.non_text_chain_until = current_time + self.non_text_chain_timeout
            logger.debug(
                f"[Reflex] 非文本连锁窗口续期至 {self.non_text_chain_until:.3f}")

        # [Standardization] 构建面向意识层 (Soul) 的标准载荷
        # 必须确保 content 存在，即便只有纯文本
        ingress_content = payload.get("content") or []
        if not ingress_content:
             return
             
        conscious_payload = {
            "content": ingress_content, # Pass-through
            "source": payload.get("source", "audio"),
            "modality": modality,
            "timestamp": current_time,
        }

        if isinstance(payload.get("user_id"), int):
            conscious_payload["user_id"] = payload.get("user_id")
        if isinstance(payload.get("group_id"), int):
            conscious_payload["group_id"] = payload.get("group_id")
        if payload.get("raw") is not None:
            conscious_payload["raw"] = payload.get("raw")

        logger.debug(f"[Reflex] >>> 意识流推送: {len(ingress_content)} blocks")

        await self.bus.publish(BaseEvent(
            name="input.user_message",
            payload=conscious_payload,
            source="Reflex"
        ))
