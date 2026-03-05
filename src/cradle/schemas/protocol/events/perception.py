from enum import Enum
from typing import Any, List, Literal, Optional, TypeAlias
from cradle.schemas.domain.multimodal import ContentBlock

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

class InternalMultiModalPayload(BaseModel):
    """月见本体内部载荷：仅承载语义内容，不携带外部渠道上下文。"""

    content: List[ContentBlock] = Field(..., description="标准多模态内容列表")
    is_external_source: Literal[False] = Field(default=False, description="内部来源固定为 False")
    name: str | None = Field(default=None, description="发送者展示名称 (可选)")
    metadata: dict = Field(default_factory=dict, description="内部模块扩展元数据")
    raw: Any = Field(default=None, description="原始数据保留 (可选, 用于调试)")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _validate_internal_payload(self) -> "InternalMultiModalPayload":
        return self


class ExternalMultiModalPayload(BaseModel):
    """外部高噪声来源载荷：显式携带路由与外部历史桥接信息。"""

    content: List[ContentBlock] = Field(..., description="标准多模态内容列表")
    vessel_id: str = Field(..., description="来源 Vessel 标识 (如 napcat)")
    source_type: str = Field(..., description="来源分支类型 (如 group/private/task)")
    source_id: str = Field(..., description="来源分支对象 ID")
    is_strong_wake: bool = Field(default=False, description="是否强唤醒信号 (用于 Reflex 状态机)")
    is_external_source: Literal[True] = Field(default=True, description="外部来源固定为 True")
    name: str | None = Field(default=None, description="发送者展示名称 (如群名片/昵称)")
    metadata: dict = Field(default_factory=dict, description="Vessel 专用业务元数据")
    external_history: Any = Field(default=None, description="外部注入的会话历史上下文")
    raw: Any = Field(default=None, description="原始数据保留 (可选, 用于调试)")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _validate_external_payload(self) -> "ExternalMultiModalPayload":
        if not self.vessel_id or not self.source_type or not self.source_id:
            raise ValueError("ExternalMultiModalPayload 需要完整路由字段。")
        return self


PerceptionPayload: TypeAlias = ExternalMultiModalPayload | InternalMultiModalPayload


class PerceptionEvent(BaseEvent):
    """
    感知输入事件 (Input Event)。

    代表从传感器 (Sensor/Vessel) 接收到的原始或初步处理过的数据。
    强制使用 `PerceptionPayload`（内部/外部双模型）作为载荷，确保类型安全。
    
    Attributes:
        modality (Modality): 数据的感知模态类型。
        payload (PerceptionPayload): 标准化的多模态数据载荷。
        duration (float): 持续时长 (秒)。主要用于音频片段或视频片段的时间跨度。
        metadata (dict): 额外的技术元数据 (如采样率、分辨率、置信度等)。
    """
    modality: Modality = Field(..., description="数据的感知模态")
    payload: PerceptionPayload = Field(..., description="标准多模态载荷")
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
