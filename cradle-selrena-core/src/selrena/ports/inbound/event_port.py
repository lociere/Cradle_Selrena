"""通用内核事件接收接口。"""

from typing import Protocol, Any


class EventPort(Protocol):
    async def handle_event(self, event_type: str, payload: Any) -> None:
        ...
