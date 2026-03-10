"""感知信号接收接口。"""

from typing import Protocol, Any


class PerceptionPort(Protocol):
    async def receive(self, payload: Any) -> None:
        ...
