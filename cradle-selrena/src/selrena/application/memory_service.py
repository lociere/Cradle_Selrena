"""记忆服务 - 记忆管理编排（迁移自 cradle_selrena_core）"""

from typing import Optional

from selrena.domain.memory import Memory, MemoryType
from selrena.ports import MemoryPort
from selrena.utils.logger import logger


class MemoryService:
    """
    记忆服务
    
    负责：
    1. 记忆编码
    2. 记忆存储
    3. 记忆检索
    4. 记忆遗忘
    """
    
    def __init__(self, memory_port: MemoryPort):
        self.memory_port = memory_port
        logger.info("MemoryService 初始化完成")
    
    async def memorize(self, content: str, memory_type: MemoryType = MemoryType.EPISODIC,
                      tags: Optional[list[str]] = None, importance: float = 0.5) -> None:
        """编码并保存记忆"""
        memory = Memory(
            content=content,
            memory_type=memory_type,
            tags=tags or [],
            importance=importance,
        )
        await self.memory_port.save_memory(memory)
        logger.debug(f"记忆已保存：{content[:30]}...")
    
    async def recall(self, query: str, n_results: int = 5) -> list[Memory]:
        """检索记忆"""
        memories = await self.memory_port.retrieve_memories(query, n_results)
        logger.debug(f"检索到 {len(memories)} 条记忆")
        return memories
    
    async def forget(self, memory_id: str) -> None:
        """删除记忆"""
        await self.memory_port.delete_memory(memory_id)
        logger.info(f"记忆已删除：{memory_id}")
