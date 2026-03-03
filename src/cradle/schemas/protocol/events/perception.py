from enum import Enum
from typing import Any, List, Optional
from cradle.schemas.domain.multimodal import ContentBlock

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .base import BaseEvent


class Modality(str, Enum):
    """
    感知模态枚举 (Sensor Modality)。
    
    定义系统支持的基础感官类型。
    """
    AUDIO = "audio"       # 听觉 (Speech, Sound)
    VISUAL = "visual"     # 视觉 (Image, Video, Screen)
    TEXT = "text"         # 纯文本 (Text Input, Transcript)
    MULTIMODAL = "multimodal"  # 混合模态 (Mixed)

class MultiModalPayload(BaseModel):
    """
    多模态标准载荷 (Standard Payload Schema)。
    
    系统内传递的所有感知数据的统一容器。
    取代了旧版本中散乱的字典结构，确保所有数据都即包含内容(`content`)也包含元数据。
    
    Attributes:
        content (List[ContentBlock]): 核心内容列表。可以是文本、图片、音频片段的组合。
        raw (Any): 原始数据保留。用于调试或回溯（例如原始的 OneBot 消息对象）。
        user_id (int | None): 来源用户标识。
        group_id (int | None): 来源群组标识（如有）。
    """
    content: List[ContentBlock] = Field(..., description="标准多模态内容列表")
    raw: Any = Field(default=None, description="原始数据 (可选, 用于调试)")
    user_id: int | None = Field(default=None, description="发送者 ID")
    group_id: int | None = Field(default=None, description="群组 ID")
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class PerceptionEvent(BaseEvent):
    """
    感知输入事件 (Input Event)。

    代表从传感器 (Sensor/Vessel) 接收到的原始或初步处理过的数据。
    强制使用 `MultiModalPayload` 作为载荷，确保类型安全。
    
    Attributes:
        modality (Modality): 数据的感知模态类型。
        payload (MultiModalPayload): 标准化的多模态数据载荷。
        duration (float): 持续时长 (秒)。主要用于音频片段或视频片段的时间跨度。
        metadata (dict): 额外的技术元数据 (如采样率、分辨率、置信度等)。
    """
    modality: Modality = Field(..., description="数据的感知模态")
    payload: MultiModalPayload = Field(..., description="标准多模态载荷")
    duration: float = Field(0.0, description="持续时长 (秒), 主要用于音频片段或视频片段")
    metadata: dict = Field(default_factory=dict,
                           description="额外的元数据 (如采样率、分辨率、置信度等)")

    @field_validator("duration", mode="before")
    @classmethod
    def _normalize_duration(cls, value: Any) -> float:
        if value is None:
            return 0.0
        duration = float(value)
        return duration if duration >= 0 else 0.0

    @field_validator("metadata", mode="before")
    @classmethod
    def _normalize_metadata(cls, value: Any) -> dict:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return {"value": value}


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
    audio_event: Optional[AudioInputEvent] = Field(
        None, description="该时间段内听到的声音")
    visual_event: Optional[VisualInputEvent] = Field(
        None, description="该时间段内看到的画面 (通常是一帧或多帧)")
    context: dict = Field(default_factory=dict, description="当下的上下文环境")
