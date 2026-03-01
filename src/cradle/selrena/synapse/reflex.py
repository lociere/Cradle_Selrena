import time
import re
from typing import List, Any
from cradle.utils.logger import logger
from cradle.core.config_manager import global_config
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.schemas.protocol.events import ReflexSignal, ReflexType, BaseEvent

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
        self.non_text_chain_timeout = float(getattr(perception_cfg, "non_text_chain_timeout_sec", self.wake_timeout))
        self.is_awake = False
        
        # 硬编码的生存本能关键词
        self.wake_keywords_zh = [
            "月见","赛琳娜", "色瑞娜", "瑟瑞娜", "塞琳娜", "赛琳",
            "赛瑞娜", "萨琳娜", "你好"
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
            logger.info(f"[Reflex] 使用宽松唤醒模式：唤醒后 {self.wake_timeout:.0f}s 内可免唤醒词。")

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
        if isinstance(payload, dict):
            text = payload.get("text")
            payload_modality = payload.get("modality")
            if isinstance(payload_modality, str) and payload_modality.strip():
                modality = payload_modality.strip().lower()
        elif hasattr(payload, "text") and isinstance(payload.text, str): # specific object
            text = payload.text
        elif isinstance(payload, str):
            text = payload
        else:
            logger.debug(f"[Reflex] 忽略不可识别 Layer2 输入: {type(payload).__name__}")
            return
            
        if not isinstance(text, str):
            logger.debug(f"[Reflex] 忽略非文本 Layer2 输入字段: {type(text).__name__}")
            return

        text = text.strip()
        if not text:
            return

        normalized_text = text
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
        has_wake_word = self._match_keywords(text_for_match, self.wake_keywords_zh, self.wake_keywords_en)
        previous_awake = self.is_awake
        
        if has_wake_word:
            self.last_wake_time = current_time
            self.non_text_chain_until = current_time + self.non_text_chain_timeout
            if not self.is_awake:
                logger.info(f"[Reflex] ⚡ 唤醒检测: {normalized_text} -> 意识上线")
        
        # 计算是否超时（严格模式下不使用宽限窗口）
        if self.strict_wake:
            self.is_awake = has_wake_word
        else:
            if has_wake_word or (current_time - self.last_wake_time) < self.wake_timeout:
                self.is_awake = True
            else:
                self.is_awake = False

        if previous_awake and not self.is_awake:
            if self.strict_wake:
                logger.info("[Reflex] 💤 严格模式：未检测到唤醒词 -> 意识休眠")
            else:
                logger.info("[Reflex] 💤 注意力超时 -> 意识休眠")
        elif (not previous_awake) and self.is_awake and has_wake_word:
            logger.debug("[Reflex] 唤醒状态已激活。")
             
        # 4. 发布全局唤醒状态（由皮质层消费）
        await self.bus.publish(BaseEvent(
            name="state.arousal",
            payload={
                "is_awake": self.is_awake,
                "has_wake_word": has_wake_word,
                "strict_wake_word": self.strict_wake,
                "wake_timeout_sec": self.wake_timeout,
            },
            source="Reflex"
        ))

        # 5. 脊髓层意识流编排：决定是否上行给 Soul
        within_non_text_chain = is_non_text and current_time <= self.non_text_chain_until
        allow_to_conscious = has_wake_word if self.strict_wake else self.is_awake
        if within_non_text_chain:
            allow_to_conscious = True

        if not allow_to_conscious:
            return

        if is_non_text:
            self.non_text_chain_until = current_time + self.non_text_chain_timeout
            logger.debug(f"[Reflex] 非文本连锁窗口续期至 {self.non_text_chain_until:.3f}")

        conscious_payload = {
            "text": normalized_text,
            "timestamp": current_time,
            "source": payload.get("source", "audio") if isinstance(payload, dict) else "audio",
            "modality": modality,
        }
        if isinstance(payload, dict):
            if isinstance(payload.get("user_id"), int):
                conscious_payload["user_id"] = payload.get("user_id")
            if isinstance(payload.get("group_id"), int):
                conscious_payload["group_id"] = payload.get("group_id")
            if payload.get("raw") is not None:
                conscious_payload["raw"] = payload.get("raw")

        logger.debug(f"[Reflex] >>> 意识流: {normalized_text}")

        await self.bus.publish(BaseEvent(
            name="input.user_message",
            payload=conscious_payload,
            source="Reflex"
        ))
