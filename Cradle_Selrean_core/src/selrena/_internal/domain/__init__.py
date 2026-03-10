# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""领域层的导出。

此包定义核心业务实体，并在迁移阶段提供统一接口。
"""

from .persona import Persona, PersonaLayer

from .memory import Memory, MemoryType

from .emotion import EmotionCategory, EmotionState

__all__: list[str] = [
    "Persona",
    "PersonaLayer",
    "Memory",
    "MemoryType",
    "EmotionCategory",
    "EmotionState",
]
