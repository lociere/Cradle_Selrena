# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""事件总线客户端接口与简单实现在 core 层。

外部调用者（例如 runner）只使用此模块中的类，与具体
传输实现（zmq adapter）解耦，便于测试与将来扩展。
"""

from __future__ import annotations

from typing import Any, Dict, Callable, Protocol, Optional

from selrena._internal.adapters import ZMQEventBusAdapter, ZMQConfig
from .logger import logger


class EventBusTransport(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    def register_handler(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Any]
    ) -> None: ...
    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> bool: ...


class EventBusClient:
    """封装传输层的总线客户端。

    默认使用 ZMQEventBusAdapter，可通过构造函数注入
    自定义 transport（例如测试用的 SimpleEventBusClient）。
    """

    def __init__(
        self,
        transport: Optional[EventBusTransport] = None,
        zmq_config: Optional[ZMQConfig] = None,
    ) -> None:
        if transport is not None:
            self._transport = transport
        else:
            self._transport = ZMQEventBusAdapter(config=zmq_config)

    async def connect(self) -> None:
        await self._transport.connect()

    async def disconnect(self) -> None:
        await self._transport.disconnect()

    def register_handler(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        self._transport.register_handler(event_type, handler)

    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        return await self._transport.send_event(event_type, payload)


class SimpleEventBusClient:
    """内存事件总线，仅用于单元测试。"""

    def __init__(self) -> None:
        self._handlers: Dict[str, list[Callable[[Dict[str, Any]], Any]]] = {}

    async def connect(self) -> None:
        # 无操作
        pass

    async def disconnect(self) -> None:
        # 无操作
        pass

    def register_handler(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        for h in self._handlers.get(event_type, []):
            try:
                h(payload)
            except Exception:
                logger.exception("SimpleEventBus handler raised")
        return True
