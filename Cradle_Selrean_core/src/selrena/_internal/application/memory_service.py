# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""Memory service: handles creating, storing and retrieving memories."""

from typing import Optional

from selrena._internal.domain.memory import Memory, MemoryType
from selrena._internal.ports import MemoryPort
from loguru import logger


class MemoryService:
    """Simple wrapper around MemoryPort."""

    def __init__(self, memory_port: MemoryPort):
        self.memory_port = memory_port
        logger.info("MemoryService initialized")

    async def memorize(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        tags: Optional[list[str]] = None,
        importance: float = 0.5,
    ) -> None:
        memory = Memory(
            content=content,
            memory_type=memory_type,
            tags=tags or [],
            importance=importance,
        )
        await self.memory_port.save_memory(memory)
        logger.debug(f"memory saved: {content[:30]}...")

    async def recall(self, query: str, n_results: int = 5) -> list[Memory]:
        memories = await self.memory_port.retrieve_memories(query, n_results)
        logger.debug(f"retrieved {len(memories)} memories")
        return memories

    async def forget(self, memory_id: str) -> None:
        await self.memory_port.delete_memory(memory_id)
        logger.info(f"memory removed: {memory_id}")
