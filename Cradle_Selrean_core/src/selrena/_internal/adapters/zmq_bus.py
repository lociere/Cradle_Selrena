# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""ZMQ 事件总线适配器。

本模块提供与第一层内核间通讯所需的发布/订阅功能。
实现仅依赖 zmq.asyncio，其他协议已在之前版本中移除。
"""

from __future__ import annotations

import asyncio
import json
import zmq
import zmq.asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass

from loguru import logger


@dataclass
class ZMQConfig:
    host: str = "127.0.0.1"
    pub_port: int = 5555
    sub_port: int = 5556
    protocol: str = "tcp"


class ZMQEventBusAdapter:
    """简单的 ZMQ 发布/订阅客户端。

    负责与外部（通常是 TypeScript 内核进程）进行事件交互。
    """

    def __init__(self, config: Optional[ZMQConfig] = None):
        self.config = config or ZMQConfig()
        self.context = zmq.asyncio.Context()
        self.publisher: Optional[zmq.asyncio.PubSocket] = None
        self.subscriber: Optional[zmq.asyncio.SubSocket] = None
        self.is_connected = False
        self.event_handlers: Dict[str, List[Callable[[Dict[str, Any]], Any]]] = {}
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        if self.is_connected:
            return
        # 绑定两端；第一层核心会作为客户端连接
        try:
            self.publisher = self.context.socket(zmq.PUB)
            pub_address = (
                f"{self.config.protocol}://{self.config.host}:{self.config.pub_port}"
            )
            self.publisher.bind(pub_address)
            logger.info(f"📡 ZMQ publisher bound to: {pub_address}")

            self.subscriber = self.context.socket(zmq.SUB)
            sub_address = (
                f"{self.config.protocol}://{self.config.host}:{self.config.sub_port}"
            )
            self.subscriber.bind(sub_address)
            self.subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
            logger.info(f"📡 ZMQ subscriber bound to: {sub_address}")

            self.is_connected = True
            logger.info("✅ ZMQ event bus connected")
            self._receive_task = asyncio.create_task(self._receive_messages())
        except Exception as e:
            logger.error(f"❌ ZMQ connect failed: {e}")
            raise

    async def disconnect(self) -> None:
        if not self.is_connected:
            return
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self.publisher:
            self.publisher.close()
        if self.subscriber:
            self.subscriber.close()
        self.context.term()
        self.is_connected = False
        logger.info("✅ ZMQ event bus disconnected")

    async def _receive_messages(self) -> None:
        assert self.subscriber is not None
        while True:
            try:
                raw = await self.subscriber.recv_string()
                payload = json.loads(raw)
                evt_type = payload.get("type")
                handlers = self.event_handlers.get(evt_type, [])
                for h in handlers:
                    try:
                        h(payload)
                    except Exception:
                        logger.exception("handler error")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("receive loop error")
                await asyncio.sleep(0.1)

    def register_handler(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        self.event_handlers.setdefault(event_type, []).append(handler)

    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        if not self.is_connected or self.publisher is None:
            return False
        try:
            message = json.dumps({"type": event_type, "payload": payload})
            await self.publisher.send_string(message)
            return True
        except Exception:
            logger.exception("publish failed")
            return False
