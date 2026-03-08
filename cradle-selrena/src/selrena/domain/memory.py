"""记忆领域模型（迁移自 cradle_selrena_core）"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MemoryType(Enum):
    """记忆类型"""
    EPISODIC = "episodic"      # 情景记忆：特定事件
    SEMANTIC = "semantic"      # 语义记忆：事实知识
    PROCEDURAL = "procedural"  # 程序记忆：技能习惯


@dataclass
class Memory:
    """
    记忆领域模型
    
    Attributes:
        content: 记忆内容
        memory_type: 记忆类型
        timestamp: 创建时间
        importance: 重要程度 (0-1)
        emotion: 关联情感
        tags: 标签列表
        metadata: 额外元数据
    """
    content: str
    memory_type: MemoryType = MemoryType.EPISODIC
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 0.5
    emotion: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "type": self.memory_type.value,
            "timestamp": self.timestamp.isoformat(),
            "importance": self.importance,
            "emotion": self.emotion,
            "tags": self.tags,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Memory":
        """从字典创建"""
        return cls(
            content=data["content"],
            memory_type=MemoryType(data.get("type", "episodic")),
            timestamp=datetime.fromisoformat(data.get("timestamp")) if data.get("timestamp") else datetime.now(),
            importance=data.get("importance", 0.5),
            emotion=data.get("emotion"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
