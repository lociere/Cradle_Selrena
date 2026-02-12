"""
音频播放器（Audio Player）

职责:
- 播放生成的音频内容。
"""

from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger
from cradle.schemas.protocol.events.action import SpeakAction
from cradle.schemas.protocol.events.reflex import ReflexSignal, ReflexType
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.core.config_manager import global_config
from .tts_client import EdgeTTSClient

class VirtualMouth:
    """
    虚拟之口 (Mouth): 唯一的表达器官
    
    职责:
    1. 监听 'action.presentation.speak' -> 执行 TTS 播放
    2. 监听 'signal.reflex' (MUTE/HALT) -> 立即停止播放
    """
    def __init__(self):
        self.bus = global_event_bus
        self.tts_client = None
        self.tts_engine = global_config.get_system().presentation.tts.engine
        
        # 1. 订阅表达动作 (来自 Soul/Mind)
        self.bus.subscribe("action.presentation.speak", self._on_speak_action)
        
        # 2. 订阅反射信号 (来自 Reflex/Spinal Cord)
        self.bus.subscribe("signal.reflex", self._on_reflex_signal)

        if self.tts_engine in {"edge-tts", "gpt-sovits"}:
            self.tts_client = EdgeTTSClient()
        else:
            logger.warning(f"[Mouth] 未启用 TTS 引擎: {self.tts_engine}")
        
        logger.info("表达器官 (Mouth) 已连接。")

    async def cleanup(self):
        self.bus.unsubscribe_receiver(self)
        self._stop_playback() # 确保关闭时静音
        logger.info("表达器官 (Mouth) 已断开连接。")

    async def _on_speak_action(self, event: BaseEvent):
        """处理说话指令"""
        # 此时 payload 可能是一个 dict (Pydantic Event)
        # 或者 event 本身就是 SpeakAction 对象 (如果在 EventBus 传递时保持了对象)
        # 我们的 Schema 定义 SpeakAction.text 是必须的
        
        text = ""
        if hasattr(event, "text"): # Direct SpeakAction object
            text = event.text
        elif isinstance(event.payload, dict):
            text = event.payload.get("text", "")
        else:
            text = str(event.payload)
            
        if not text:
            return
            
        print(f"\n>>> 月见(Selrena): {text}\n")
        if self.tts_client:
            audio_path = await self.tts_client.synthesize(text)
            if audio_path:
                self.tts_client.play(audio_path)
        
    async def _on_reflex_signal(self, event: BaseEvent):
        """处理反射信号 (打断)"""
        # 解析信号类型
        reflex_type = None
        if hasattr(event, "reflex_type"):
            reflex_type = event.reflex_type
        elif isinstance(event.payload, dict):
             reflex_type = event.payload.get("reflex_type")

        if reflex_type in [ReflexType.MUTE, ReflexType.HALT]:
            logger.info("[Mouth] ⚡ 脊髓反射触发: 立即闭嘴。")
            self._stop_playback()

    def _stop_playback(self):
        """停止当前正在播放的声音"""
        if self.tts_client:
            self.tts_client.stop()
