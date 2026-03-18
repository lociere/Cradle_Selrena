"""
文件名称：kernel_ingress_contracts.py
所属层级：核心层-协议契约
核心作用：定义内核入站消息的强类型契约，避免 AI 层直接处理裸 dict。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KernelMessageEnvelope(BaseModel):
    """内核入站消息统一信封。"""

    type: str
    trace_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class PerceptionModalityItemModel(BaseModel):
    """多模态单项输入。"""

    modality: str
    text: str | None = None
    uri: str | None = None
    mime_type: str | None = None
    description_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelInputPayloadModel(BaseModel):
    """标准模型输入。"""

    items: list[PerceptionModalityItemModel] = Field(default_factory=list)


class PerceptionMessagePayloadModel(BaseModel):
    """感知消息载荷。"""

    input: ModelInputPayloadModel = Field(default_factory=ModelInputPayloadModel)
    scene_id: str = "default"
    familiarity: int = 0


class LifeHeartbeatPayloadModel(BaseModel):
    """生命心跳载荷。"""

    attention_mode: str = "ambient"


class AgentPlanPayloadModel(BaseModel):
    """任务规划载荷。"""

    user_goal: str = ""
    scene_id: str = "default"


class KernelLongTermMemoryRecord(BaseModel):
    """内核注入的长期记忆记录。"""

    content: str
    memory_type: str
    weight: float = 1.0
    tags: list[str] = Field(default_factory=list)
    scene_id: str = ""
    memory_id: str
    timestamp: str


class MemoryInitPayloadModel(BaseModel):
    """长期记忆初始化载荷。"""

    memories: list[KernelLongTermMemoryRecord] = Field(default_factory=list)


class KernelKnowledgeRecord(BaseModel):
    """内核注入的知识库记录。"""

    entry_id: str
    scope: str
    content: str
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    priority: int = 1
    source: str = "manual"
    updated_at: str = ""


class KnowledgeRetrievalConfigModel(BaseModel):
    """知识检索配置。"""

    persona_top_k: int = 12
    general_top_k: int = 4
    min_score: float = 0.15
    keyword_weight: float = 1.0
    tag_weight: float = 0.7
    priority_weight: float = 0.2


class KnowledgeBaseInitPayloadModel(BaseModel):
    """知识库初始化主载荷。"""

    version: str = "2.0"
    retrieval: KnowledgeRetrievalConfigModel = Field(default_factory=KnowledgeRetrievalConfigModel)
    entries: list[KernelKnowledgeRecord] = Field(default_factory=list)


class KnowledgeInitPayloadModel(BaseModel):
    """知识库初始化载荷。"""

    knowledge_base: KnowledgeBaseInitPayloadModel
