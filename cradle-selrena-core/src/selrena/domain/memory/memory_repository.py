"""记忆仓储抽象接口。"""

from typing import Protocol, Any


class MemoryRepository(Protocol):
    def add_memory(self, memory: Any) -> None:
        ...

    def query(self, query: str) -> list[Any]:
        ...
