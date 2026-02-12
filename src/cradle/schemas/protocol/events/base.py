from typing import Any
from pydantic import BaseModel, Field
import time
import uuid

class BaseEvent(BaseModel):
    """
    神经信号基类 (Protocol)
    
    系统中所有流转的信号（感知、反射、动作）都继承自此类。
    它定义了事件在 EventBus 中传输所需的最小公分母。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="事件唯一标识符 (UUID)")
    timestamp: float = Field(default_factory=time.time, description="事件产生的时间戳 (Unix Timestamp)")
    source: str = Field(default="unknown", description="信号源 (发送者名称, 如 'Ear', 'Reflex', 'Soul')")
    name: str = Field(..., description="事件路由键 (Routing Key), 用于 EventBus 订阅分发 (例如 'perception.audio')")
    payload: Any = Field(default=None, description="事件携带的数据载荷 (可以是字典、对象或基础类型)")

    class Config:
        arbitrary_types_allowed = True
