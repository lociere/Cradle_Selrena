from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from .base import BaseEvent

class Modality(str, Enum):
    """感知模态类型"""
    AUDIO = "audio"   # 听觉
    VISUAL = "visual" # 视觉
    TEXT = "text"     # 文字/纯文本

class PerceptionEvent(BaseEvent):
    """
    感知输入事件 (Input Event)
    
    代表从传感器 (Sensor) 接收到的原始或初步处理过的数据。
    流向: Body -> Nervous System (EventBus) -> Queue
    """
    modality: Modality = Field(..., description="数据的感知模态")
    duration: float = Field(0.0, description="持续时长 (秒), 主要用于音频片段或视频片段")
    metadata: dict = Field(default_factory=dict, description="额外的元数据 (如采样率、分辨率、置信度等)")

class AudioInputEvent(PerceptionEvent):
    """听觉输入事件 (包含原始音频流或识别后的文本)"""
    modality: Modality = Modality.AUDIO
    name: str = "perception.audio.input"
    
class VisualInputEvent(PerceptionEvent):
    """视觉输入事件 (包含屏幕截图、摄像头画面)"""
    modality: Modality = Modality.VISUAL
    name: str = "perception.visual.snapshot"

class SubjectiveInterval(BaseModel):
    """
    主观时刻 (Subjective Interval) - Layer 2 -> Layer 3
    
    这是多模态对齐后的核心数据结构。
    它代表了 Agent 在某一个时间窗口内“看到”和“听到”的综合体。
    边缘系统 (Association Layer) 负责将分散的 Audio 和 Visual 事件打包成这个对象。
    """
    start_time: float = Field(..., description="时间窗口开始")
    end_time: float = Field(..., description="时间窗口结束")
    audio_event: Optional[AudioInputEvent] = Field(None, description="该时间段内听到的声音")
    visual_event: Optional[VisualInputEvent] = Field(None, description="该时间段内看到的画面 (通常是一帧或多帧)")
    context: dict = Field(default_factory=dict, description="当下的上下文环境")
