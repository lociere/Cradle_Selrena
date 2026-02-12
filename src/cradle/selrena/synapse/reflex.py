import time
import re
import asyncio
from typing import List, Any
from cradle.utils.logger import logger
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.schemas.protocol.events import ReflexSignal, ReflexType, BaseEvent

class ReflexController:
    """
    脊髓层 (Layer 1): 负责快速反射、生存本能与唤醒机制。
    不经过深度思考，直接拦截或触发行为。
    
    ReflexController 监听原始感知信号，维护生物体的唤醒状态 (Arousal Level)。
    """
    def __init__(self):
        self.bus = global_event_bus
        self.last_wake_time = 0
        self.wake_timeout = 30.0  # 30秒无交互自动休眠
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
        
        logger.info("脊髓反射中枢 (ReflexController) 初始化...")

    async def initialize(self):
        # 订阅原始听觉输入
        self.bus.subscribe("perception.audio.transcription", self.on_audio_transcription)
        
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

    async def on_audio_transcription(self, event: Any):
        # 兼容 Event 对象或 Pydantic 对象
        payload = event.payload if hasattr(event, "payload") else {}
        if isinstance(payload, dict):
            text = payload.get("text", "")
        elif hasattr(payload, "text"): # specific object
            text = payload.text
        elif isinstance(payload, str):
            text = payload
        else:
            text = str(payload)
            
        if not text:
            return

        text = text.lower()

        # 1. 紧急停止反射 (Immediate Halt)
        if any(w in text for w in self.stop_keywords):
             logger.warning(f"[Reflex] ⏹️ 收到停止指令: {text}")
             # 发出脊髓信号，Mouth 应该订阅这个信号并立即停止
             signal = ReflexSignal(reflex_type=ReflexType.MUTE, source="Reflex")
             
             await self.bus.publish(signal) 


        # 2. 生存安全反射 (Shutdown)
        if self._match_keywords(text, self.exit_keywords_zh, self.exit_keywords_en):
             logger.critical(f"[Reflex] 🛑 收到关机指令: {text}")
             await self.bus.publish(BaseEvent(name="system.shutdown", payload={"reason": "voice_command"}, source="Reflex"))
             return
             
        # 3. 唤醒机制 (Arousal System)
        current_time = time.time()
        has_wake_word = self._match_keywords(text, self.wake_keywords_zh, self.wake_keywords_en)
        
        if has_wake_word:
             self.last_wake_time = current_time
             if not self.is_awake:
                 self.is_awake = True
                 logger.info(f"[Reflex] ⚡ 唤醒检测: {text} -> 意识上线")
                 # 可以发一个“我醒了”的反馈给 UI
        
        # 计算是否超时
        if (current_time - self.last_wake_time) < self.wake_timeout:
             self.is_awake = True
        else:
             if self.is_awake:
                 logger.info("[Reflex] 💤 注意力超时 -> 意识休眠")
             self.is_awake = False
             
        # 4. 发布意识状态 (供 Association Layer 过滤)
        # 我们发布一个新的 topic，或者仅仅作为一个 Global State 供查询。
        # 更好的方式是发布一个带状态的事件
        await self.bus.publish(BaseEvent(name="state.arousal", payload={"is_awake": self.is_awake}, source="Reflex"))
