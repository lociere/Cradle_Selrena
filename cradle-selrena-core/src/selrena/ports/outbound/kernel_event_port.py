"""内核事件输出接口（唯一对外出口）。"""

from typing import Protocol, Any


class KernelEventPort(Protocol):
    async def send(self, event_type: str, payload: Any) -> bool:
        ...
