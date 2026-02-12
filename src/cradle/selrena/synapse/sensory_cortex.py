import time
import re
import asyncio
from typing import List, Any
from cradle.utils.logger import logger
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.schemas.protocol.events import BaseEvent

class SensoryCortex:
    """
    边缘层 (Layer 2): 感知关联皮层
    负责 '注意力过滤' (Attention Filter) 和 '多模态对齐'。
    只有被判定为 '相关' (Relevant) 的信息才会进入意识流 (Mind)。
    """
    def __init__(self):
        self.bus = global_event_bus
        self.last_wake_time = 0
        self.wake_timeout = 30.0
        self.is_awake = False
        
        self.wake_keywords_zh = [
            "月见","小月","赛琳娜", "色瑞娜", "瑟瑞娜", "塞琳娜", "赛琳",
            "赛瑞娜", "萨琳娜", "你好"
        ]
        self.wake_keywords_en = [
            "selrena", "serena", "salrena", "serina", "selina", "celina",
            "hello", "hi", "hey"
        ]
        
        logger.info("感知皮层 (SensoryCortex) 初始化: 正在建立注意力机制...")

    async def initialize(self):
        self.bus.subscribe("perception.audio.transcription", self.on_audio_transcription)
        # [NEW] 订阅脊髓层的唤醒状态信号，保持自身状态同步 (消除 EventBus 无受体警告)
        self.bus.subscribe("state.arousal", self.on_arousal_state)
        
    async def cleanup(self):
        self.bus.unsubscribe_receiver(self)
    
    async def on_arousal_state(self, event: BaseEvent):
        """接收来自脊髓层的唤醒状态更新"""
        # 这一步目前主要是为了同步状态日志，逻辑上 Cortex 的唤醒判定与 Reflex 可能是稍有冗余的
        # 但在完整架构中 Cortex 应该参考 Reflex 维护的 '生物体全局唤醒度'
        # 简单起见，这里仅做日志或静默处理以消耗事件
        pass

    def _match_keywords(self, text: str, zh_list: List[str], en_list: List[str]) -> bool:
        text_clean = text.lower()
        if any(kw in text_clean for kw in zh_list):
            return True
        for kw in en_list:
             if re.search(r'\b' + re.escape(kw) + r'\b', text_clean):
                return True
        return False

    async def on_audio_transcription(self, event: Any):
        payload = event.payload if hasattr(event, "payload") else {}
        if isinstance(payload, dict):
            text = payload.get("text", "")
        elif hasattr(payload, "text"):
            text = payload.text
        elif isinstance(payload, str):
            text = payload
        else:
            text = str(payload)
            
        if not text:
            return

        current_time = time.time()
        has_wake_word = self._match_keywords(text, self.wake_keywords_zh, self.wake_keywords_en)
        
        # 只有听到唤醒词，或者已经在唤醒状态下，才处理
        should_process = False
        
        if has_wake_word:
             self.last_wake_time = current_time
             self.is_awake = True
             should_process = True
             # logger.debug("[Cortex] 捕捉到唤醒词，注意力集中。")
        elif (current_time - self.last_wake_time) < self.wake_timeout:
             self.is_awake = True
             should_process = True
             # 收到有效对话时刷新超时? (Keep Alive)
             # 通常只有你也说话了才刷新，或者一直保持? 
             # 简单起见，只要用户在说话就刷新
             self.last_wake_time = current_time
        else:
             self.is_awake = False
             
        if should_process:
            # 转发给 Mind (Conscious Stream)
            # 标记为 'input.user_message' 供 SoulIntellect 使用
            logger.debug(f"[Cortex] >>> 意识流: {text}")
            await self.bus.publish(BaseEvent(
                name="input.user_message", # 这将触发 SoulIntellect
                payload={"text": text, "timestamp": current_time, "source": "audio"},
                source="SensoryCortex"
            ))
        else:
            logger.info(f"[Cortex] 已忽略背景对话: {text}")
