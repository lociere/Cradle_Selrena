"""
Napcat 专用数据模型 (Napcat-specific Schemas)。

定义 Napcat Vessel 层专用的结构化数据模型，用于：
1. Artifact 存储（协议细节归档）
2. 内部消息传递
"""

from typing import Any, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field
from cradle.schemas.domain.chat import Message
from cradle.schemas.domain.multimodal import ContentBlock


class NapcatArtifact(Message):
    """
    Napcat 协议归档模型 (Protocol Artifact)。
    
    继承自标准 `Message` schema，扩展 Napcat 专用的协议元数据。
    用于持久化存储原始消息的完整协议细节，供调试、回溯、引用解析使用。
    
    Attributes:
        role (Literal["user", "assistant"]): 消息角色（固定为 user 或 assistant）。
        content (Union[str, List[ContentBlock]]): 标准化后的语义内容（供 Soul 使用）。
        timestamp (float): 消息创建时间戳。
        
        # Napcat 专用协议字段
        msg_id (Optional[int]): Napcat 消息 ID（用于引用查找）。
        reply_to (Optional[int]): 被回复的消息 ID（如果有）。
        sender_name (Optional[str]): 发送者展示名称（群名片/昵称）。
        text (Optional[str]): 原始纯文本内容（未加工）。
        display_text (Optional[str]): 格式化后的展示文本（含身份前缀）。
        images (List[str]): 图片 URL 列表。
        routing_mode (str): 处理时的路由策略（split_tasks | single_multimodal）。
        original_images (Optional[List[str]]): 原始图片 URL（仅 single_multimodal 模式）。
    """
    
    # Napcat 专用协议元数据（扩展自 Message 基础字段）
    msg_id: Optional[int] = Field(None, description="Napcat 消息 ID")
    reply_to: Optional[int] = Field(None, description="被回复的消息 ID")
    sender_name: Optional[str] = Field(None, description="发送者展示名称")
    text: Optional[str] = Field(None, description="原始纯文本内容")
    display_text: Optional[str] = Field(None, description="格式化展示文本")
    images: List[str] = Field(default_factory=list, description="图片 URL 列表")
    routing_mode: str = Field(default="split_tasks", description="路由策略模式")
    original_images: Optional[List[str]] = Field(None, description="原始图片 URL（仅 single_multimodal 模式）")
    
    model_config = {"extra": "allow"}  # 允许额外字段，便于未来扩展


class NapcatMessageRecord(BaseModel):
    """
    Napcat 消息记录模型（内部使用）。
    
    用于在 Vessel 层内部传递完整的消息上下文，包含：
    - 标准化后的语义内容（content）
    - 原始协议数据（raw_event）
    - 处理后的元数据（metadata）
    
    与 NapcatArtifact 的区别：
    - NapcatArtifact: 持久化存储，继承 Message，供 Soul 可读
    - NapcatMessageRecord: 运行时传递，包含更多内部状态
    """
    
    # 标准字段
    role: str = Field(..., description="消息角色")
    content: Any = Field(..., description="内容（可能是 str 或 List[ContentBlock]）")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    
    # Napcat 协议字段
    msg_id: Optional[int] = Field(None, description="Napcat 消息 ID")
    reply_to: Optional[int] = Field(None, description="被回复的消息 ID")
    sender_name: Optional[str] = Field(None, description="发送者展示名称")
    group_id: Optional[int] = Field(None, description="群 ID（如果是群聊）")
    user_id: int = Field(..., description="用户 ID")
    
    # 原始数据保留
    raw_event: dict = Field(default_factory=dict, description="原始事件数据（用于调试）")
    
    # 处理状态
    is_wake: bool = Field(default=False, description="是否唤醒 AI")
    routing_mode: str = Field(default="split_tasks", description="使用的路由策略")
    
    model_config = {"extra": "allow"}
