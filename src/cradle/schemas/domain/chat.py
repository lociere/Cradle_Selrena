from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

class Message(BaseModel):
    """
    基础对话消息模型 (Message Schema)
    
    用于在各层之间传递对话数据，也可用于存储历史记录。
    标准化了 LLM 输入输出的基本单元。
    """
    role: Literal["system", "user", "assistant"] = Field(..., description="消息角色 (OpenAI 格式)")
    content: str = Field(..., description="消息文本内容")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp(), description="消息生成时间戳")
    metadata: dict = Field(default_factory=dict, description="额外元数据 (如 Token 消耗, 来源模块等)")

class ChatHistory(BaseModel):
    """
    对话历史记录容器 (Context Container)
    
    封装了一组 Message 对象，提供便捷的操作方法。
    """
    messages: list[Message] = Field(default_factory=list, description="有序的消息列表")

    def add_message(self, role: str, content: str):
        """便捷添加一条消息"""
        self.messages.append(Message(role=role, content=content))

