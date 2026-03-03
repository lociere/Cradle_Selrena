import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


_EVENT_NAME_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


class BaseEvent(BaseModel):
    """
    基础事件协议 (Base Event Protocol)。
    
    这是 "神经系统" (EventBus) 中传递的所有信号的基类。
    类似于神经元传递的电信号包，它封装了元数据和负载。
    
    Attributes:
        id (str): 事件唯一标识符 (UUID v4)。
        trace_id (str): 分布式追踪 ID。用于串联一次完整的交互链路（例如：听到->思考->说话）。
        parent_id (str | None): 父事件 ID。用于构建因果链（Causal Chain）。
        timestamp (float): 事件产生的时间戳 (Unix epoch float)。
        source (str): 信号源标识 (如 'NapcatClient', 'SpeechRecognition')。
        name (str): 路由键 (Routing Key)。订阅者根据此键过滤感兴趣的事件 (Topic)。
        payload (Any): 数据负载。建议使用 Pydantic Model 或标准字典。
    """
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), description="事件唯一标识符 (UUID)")
    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="链路追踪 ID：同一业务链路内事件共享该值",
    )
    parent_id: str | None = Field(
        default=None,
        description="父事件 ID：用于构建事件因果关系",
    )
    timestamp: float = Field(default_factory=time.time,
                             description="事件产生的时间戳 (Unix Timestamp)")
    source: str = Field(default="unknown",
                        description="信号源 (发送者名称, 如 'Ear', 'Reflex', 'Soul')")
    name: str = Field(..., description="事件路由键 (Routing Key), 用于 EventBus 订阅分发 (例如 'perception.audio')")
    payload: Any = Field(default=None, description="事件携带的数据载荷 (可以是字典、对象或基础类型)")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    @field_validator("id", "trace_id", mode="before")
    @classmethod
    def _normalize_uuid_like(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise ValueError("事件标识不能为空。")
        return normalized

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, value: Any) -> str:
        normalized = str(value or "unknown").strip()
        return normalized or "unknown"

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_event_name(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise ValueError("事件名不能为空。")
        if normalized.startswith(".") or normalized.endswith("."):
            raise ValueError("事件名不能以 '.' 开头或结尾。")
        if ".." in normalized:
            raise ValueError("事件名不能包含连续的 '..'。")
        if any(ch not in _EVENT_NAME_ALLOWED_CHARS for ch in normalized):
            raise ValueError("事件名仅允许小写字母、数字及 ._- 字符。")
        return normalized

    @field_validator("timestamp", mode="before")
    @classmethod
    def _normalize_timestamp(cls, value: Any) -> float:
        try:
            ts = float(value)
        except Exception as exc:
            raise ValueError("timestamp 必须可转换为浮点数。") from exc
        if ts <= 0:
            raise ValueError("timestamp 必须大于 0。")
        return ts

    def child_event(
        self,
        *,
        name: str,
        source: str,
        payload: Any = None,
        **extra_fields: Any,
    ) -> "BaseEvent":
        """基于当前事件创建子事件，自动继承 ``trace_id`` 与 ``parent_id``。"""
        return BaseEvent(
            name=name,
            source=source,
            payload=payload,
            trace_id=self.trace_id,
            parent_id=self.id,
            **extra_fields,
        )

    def to_log_dict(self) -> dict[str, Any]:
        """返回稳定、可观测的日志字段。"""
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "timestamp": self.timestamp,
            "name": self.name,
            "source": self.source,
        }
