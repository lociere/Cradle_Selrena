# 该文件已格式化，内部备注/注释请使用中文说明
"""事件模式的导出。

为方便使用，此处从 protocol 包中导入常用事件类型。
"""

from selrena._internal.schemas.protocol.events.action import (
    SpeakAction,
    ChannelReplyAction,
    ActionEvent,
)
from pydantic import BaseModel


class MCPCommandAction(BaseModel):
    """裸 MCP 命令事件的负载模型。"""

    command: dict


__all__ = [
    "SpeakAction",
    "ChannelReplyAction",
    "ActionEvent",
    "MCPCommandAction",
]
