# 记忆存储端口定义
from abc import ABC, abstractmethod
from typing import List

from selrena._internal.domain.memory import Memory


class MemoryPort(ABC):
    """供存储服务使用的抽象存储接口。

    当前实现基于文件系统，可替换为数据库或向量服务。
    """

    @abstractmethod
    async def save_memory(self, memory: Memory) -> None:
        """持久化保存 Memory 对象。"""

    @abstractmethod
    async def retrieve_memories(self, query: str, n_results: int = 5) -> List[Memory]:
        """返回与查询相关的记忆列表。"""

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> None:
        """通过标识符移除记忆。"""
