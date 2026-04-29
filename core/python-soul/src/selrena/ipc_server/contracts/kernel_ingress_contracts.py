"""
文件名称：kernel_ingress_contracts.py
所属层级：核心层-协议契约
核心作用：定义内核入站消息的强类型契约，避免 AI 层直接处理裸 dict。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class KernelMessageEnvelope(BaseModel):
    """内核入站消息统一信封。"""

    type: str
    trace_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class PerceptionModalitySemanticModel(BaseModel):
    """媒体语义信息（提示/预解析结果统一建模）。"""

    text: str
    source: str | None = None
    resolved: bool | None = None
    confidence: float | None = None


class PerceptionModalityItemModel(BaseModel):
    """单个多模态输入项。"""

    modality: str
    text: str | None = None
    uri: str | None = None
    mime_type: str | None = None
    semantic: PerceptionModalitySemanticModel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PerceptionEventContentModel(BaseModel):
    """感知事件核心内容模型。"""

    text: str | None = None
    modality: list[str] = Field(default_factory=list)
    items: list[PerceptionModalityItemModel] = Field(default_factory=list)


class PerceptionEventPayloadModel(BaseModel):
    """新版感知消息载荷。"""

    id: str
    sensoryType: str
    source: str
    timestamp: float
    familiarity: int = 0
    address_mode: Literal['direct', 'ambient'] = 'direct'
    content: PerceptionEventContentModel


class LifeHeartbeatPayloadModel(BaseModel):
    """生命心跳载荷。"""

    attention_mode: str = "ambient"


class AgentPlanPayloadModel(BaseModel):
    """任务规划载荷。"""

    user_goal: str = ""
    scene_id: str = "default"
    available_tools: list[dict] = Field(default_factory=list)


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
    """内核注入的知识库记录。

    scope:
      - persona  → PersonaInjector 编译消费
      - knowledge → KnowledgeBase 管理
    compile_group（仅 scope=persona 有效）：
      identity / style / example / trait /
      emotion:<type> / context:<mode> / safety
    """

    entry_id: str
    scope: str
    compile_group: str = ""
    content: str
    enabled: bool = True
    priority: int = 1


class KnowledgeRetrievalConfigModel(BaseModel):
    """知识检索配置（仅用于 scope=knowledge 条目）。"""

    mode: str = "full_injection"   # "full_injection" | "semantic_rag"
    top_k: int = 5
    min_score: float = 0.3
    semantic_weight: float = 0.6


class KnowledgeBaseInitPayloadModel(BaseModel):
    """知识库初始化主载荷。"""

    version: str = "4.0"
    retrieval: KnowledgeRetrievalConfigModel = Field(default_factory=KnowledgeRetrievalConfigModel)
    entries: list[KernelKnowledgeRecord] = Field(default_factory=list)


class KnowledgeInitPayloadModel(BaseModel):
    """知识库初始化载荷。"""

    knowledge_base: KnowledgeBaseInitPayloadModel


class AgentToolResultModel(BaseModel):
    """单个 MCP 工具的执行结果。"""

    tool_name: str
    status: str = "success"  # success | error | skipped
    result_json: str = "{}"  # JSON 序列化的结果内容


class AgentSynthesisPayloadModel(BaseModel):
    """工具结果合成载荷。"""

    original_goal: str = ""
    scene_id: str = "default"
    tool_results: list[AgentToolResultModel] = Field(default_factory=list)
