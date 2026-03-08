"""事件模型定义（迁移自 cradle_selrena_core）"""

from typing import Optional
from pydantic import BaseModel


class BaseEvent(BaseModel):
    """基础事件模型"""
    source: str
    timestamp: Optional[float] = None


class SpeakAction(BaseEvent):
    """说话动作事件"""
    text: str
    emotion: Optional[str] = "neutral"


class AudioPlayEvent(BaseEvent):
    """音频播放事件"""
    audio_path: str
    volume: Optional[float] = 1.0


class ScreenCaptureEvent(BaseEvent):
    """屏幕截取事件"""
    region: Optional[str] = "full"  # full, window, region


class SystemEvent(BaseEvent):
    """系统事件"""
    event_type: str  # startup, shutdown, error, warning
    message: str
    data: Optional[dict] = None


# 导出所有事件类
__all__ = [
    "BaseEvent",
    "SpeakAction",
    "AudioPlayEvent",
    "ScreenCaptureEvent",
    "SystemEvent",
]
