from datetime import datetime
from typing import Literal, Union
from cradle.schemas.domain.multimodal import ContentBlock

from pydantic import BaseModel, Field


class Message(BaseModel):
    """
    通用对话消息模型 (Message Schema)。
    
    这是系统内流转的核心数据结构，用于表示单条对话记录。
    它不仅用于 LLM 的输入输出，也用于模块间的消息传递。
    随着多模态能力的增强，推荐优先使用 `content: list[ContentBlock]` 格式以保持最大兼容性。
    
    Attributes:
        role (Literal["system", "user", "assistant"]): 消息发送者角色。遵循 OpenAI 聊天模型标准。
            - 'system': 系统指令/人设设定。
            - 'user': 用户输入。
            - 'assistant': 模型输出。
        content (Union[str, list[ContentBlock]]): 消息内容。
            - str: 简单的纯文本消息。
            - list[ContentBlock]: 多模态消息列表（包含文本、图片、音频等）。
        timestamp (float): 消息创建的时间戳（Unix Timestamp）。
        metadata (dict): 附加元数据字典。可用于存储 Token 消耗、来源标识、原始数据等调试信息。
    """
    role: Literal["system", "user",
                  "assistant"] = Field(..., description="消息角色 (OpenAI 格式)")
    # [Upgrade] 升级支持多模态内容 (str | List[ContentBlock])
    content: Union[str, list[ContentBlock]] = Field(..., description="消息内容 (支持纯文本或 OpenAI 多模态列表格式)")
    
    timestamp: float = Field(
        default_factory=lambda: datetime.now().timestamp(), description="消息生成时间戳")
    metadata: dict = Field(default_factory=dict,
                           description="额外元数据 (如 Token 消耗, 来源模块等)")


class ChatHistory(BaseModel):
    """
    对话上下文容器 (Context Container)。
    
    封装了一组有序的 `Message` 对象，代表当前的对话历史。
    通用于短期记忆 (Short-term Memory) 和上下文构建。
    
    Attributes:
        messages (list[Message]): 按时间顺序排列的消息列表。
    """
    messages: list[Message] = Field(
        default_factory=list, description="有序的消息列表")

    def add_message(self, role: str, content: str):
        """
        便捷方法：添加一条纯文本消息。
        
        Args:
            role (str): 角色 ('system', 'user', 'assistant')
            content (str): 文本内容
        """
        self.messages.append(Message(role=role, content=content))
