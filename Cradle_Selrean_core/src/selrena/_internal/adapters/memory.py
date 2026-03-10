# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""文件系统记忆存储适配器。

如果用户未传入存储路径，默认为
运行时目录下的 `data/selrena/memory` 子目录；
此路径便于统一管理与调试。
"""

import asyncio
from pathlib import Path
from typing import Optional

from selrena._internal.domain.memory import Memory
from selrena._internal.ports.memory_port import MemoryPort
from loguru import logger


class MemoryAdapter(MemoryPort):
    """简单的文件型记忆存储。

    所有记忆以 JSON 文件形式写入指定目录，
    文件名由时间戳生成。
    """

    def __init__(self, storage_path: Path | None = None):
        from selrena._internal.utils.io.path import get_data_path

        # 默认目录：runtime/data/selrena/memory
        self.storage_path = storage_path or get_data_path("selrena/memory")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"MemoryAdapter 初始化于 {self.storage_path}")

    async def save_memory(self, memory: Memory) -> None:
        """将记忆保存为 JSON 文件。"""
        import json

        memory_file = (
            self.storage_path / f"{memory.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        )
        content = json.dumps(memory.to_dict(), ensure_ascii=False, indent=2)
        await asyncio.to_thread(memory_file.write_text, content, encoding="utf-8")

    async def retrieve_memories(self, query: str, n_results: int = 5) -> list[Memory]:
        """从文件中检索包含查询文本的记忆。"""
        memories: list[Memory] = []
        for f in self.storage_path.glob("*.json"):
            import json

            content = await asyncio.to_thread(f.read_text, encoding="utf-8")
            data = json.loads(content)
            memory = Memory.from_dict(data)
            if query.lower() in memory.content.lower():
                memories.append(memory)
        return memories[:n_results]

    async def delete_memory(self, memory_id: str) -> None:
        """删除指定 id 的记忆文件。"""
        memory_file = self.storage_path / f"{memory_id}.json"
        if memory_file.exists():
            await asyncio.to_thread(memory_file.unlink)

