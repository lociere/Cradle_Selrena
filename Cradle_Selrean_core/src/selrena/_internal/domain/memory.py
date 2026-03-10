# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""记忆领域模型（从 cradle_selrena_core 迁移）。"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MemoryType(Enum):
    """记忆类型。"""

    EPISODIC = "episodic"  # 具体事件
    SEMANTIC = "semantic"  # 事实性知识
    PROCEDURAL = "procedural"  # 技能和流程


@dataclass
class Memory:
    """记忆记录模型。

    属性：
        content: 记忆内容文本
        memory_type: 记忆类型/类别
        timestamp: 创建时间
        importance: 0 到 1 之间的重要程度
        emotion: 可选情绪标签
        tags: 用户定义的标签列表
        metadata: 以字典形式存储的额外字段
    """

    content: str
    memory_type: MemoryType = MemoryType.EPISODIC
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 0.5
    emotion: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "content": self.content,
            "memory_type": self.memory_type.value,
            "timestamp": self.timestamp.isoformat(),
            "importance": self.importance,
            "emotion": self.emotion,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Memory":
        m = cls(
            content=data.get("content", ""),
            memory_type=MemoryType(data.get("memory_type", MemoryType.EPISODIC.value)),
            timestamp=(
                datetime.fromisoformat(data.get("timestamp"))
                if data.get("timestamp")
                else datetime.now()
            ),
            importance=data.get("importance", 0.5),
            emotion=data.get("emotion"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
        return m
