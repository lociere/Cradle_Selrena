# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from datetime import datetime

from typing import Literal, Union

from pydantic import BaseModel, Field

from selrena._internal.schemas.multimodal import ContentBlock


class Message(BaseModel):
    """通用对话消息结构。"""

    role: Literal["system", "user", "assistant"] = Field(
        ..., description="消息角色（OpenAI 格式）"
    )
    content: Union[str, list[ContentBlock]] = Field(
        ..., description="消息内容（文本或多模态块）"
    )
    timestamp: float = Field(
        default_factory=lambda: datetime.now().timestamp(),
        description="消息创建时间，Unix 时间戳",
    )
    metadata: dict = Field(
        default_factory=dict, description="额外元数据（如来源、token 等）"
    )


class ChatHistory(BaseModel):
    """有序对话消息的容器。"""

    messages: list[Message] = Field(
        default_factory=list, description="消息的有序列表"
    )

    def add_message(self, role: str, content: Union[str, list[ContentBlock]]):
        self.messages.append(Message(role=role, content=content))
