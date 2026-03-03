"""Napcat 服务器组件：接收 Napcat 客户端的入站连接。

该组件让 Selrena 作为 OneBot 主端运行，Napcat 以客户端模式将
事件主动推送过来。实现保持轻量，安全侧仅提供基础令牌校验。
对上仍使用全局事件总线的 ``napcat.event`` / ``napcat.send`` 主题，
与旧 NapcatAdapter 兼容，避免上层逻辑变更。
"""

import asyncio
import json
from typing import Any

import websockets

from cradle.core.config_manager import global_config
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger


class NapcatServer:
    """用于接收 Napcat OneBot 事件的 WebSocket 服务端。"""

    def __init__(self):
        self.bus = global_event_bus
        self.config = global_config.get_system().napcat
        self._server: websockets.server.Serve | None = None
        self._clients: set[websockets.WebSocketServerProtocol] = set()
        self._task: asyncio.Task | None = None

    async def initialize(self):
        if not self.config.enable:
            logger.info("[NapcatServer] 已禁用，跳过启动")
            return

        port = self.config.listen_port
        # 某些 WebSocket 库不接受带逗号的子协议字符串，但 Napcat 常发送
        # "onebot,<token>"。因此这里不写死 `subprotocols`，改用自定义
        # 选择器，按客户端请求动态校验并回显可接受的子协议。

        def select_subprotocol(connection, client_protocols):
            # client_protocols 来自 Sec-WebSocket-Protocol 请求头。
            # 遍历并挑选首个可接受协议，同时记录关键令牌信息，便于排查握手失败。
            for proto in client_protocols:
                if not isinstance(proto, str):
                    continue
                if not proto.startswith("onebot"):
                    continue
                if proto == "onebot":
                    logger.info(f"[NapcatServer] 客户端请求了纯 onebot 子协议")
                    return proto
                # 形如 "onebot,<token>"，按配置校验令牌。
                parts = proto.split(",", 1)
                if len(parts) == 2:
                    _, tok = parts
                    if self.config.token and tok != self.config.token:
                        logger.warning(
                            f"[NapcatServer] 客户端提供的令牌 '{tok}' 与配置不符"
                        )
                        # 继续尝试后续候选协议。
                        continue
                    logger.info(f"[NapcatServer] 客户端请求了带令牌子协议 {proto}")
                    return proto
            # 未找到可接受子协议。
            logger.info("[NapcatServer] 未发现兼容的子协议")
            return None

        try:
            self._server = await websockets.serve(
                self._handler,
                "0.0.0.0",
                port,
                subprotocols=None,
                select_subprotocol=select_subprotocol,
            )
        except OSError as exc:
            if exc.errno == 10048:
                logger.error(
                    f"[NapcatServer] 端口 {port} 已被占用，已跳过 NapcatServer 启动。"
                )
                logger.error(
                    "[NapcatServer] 请结束占用该端口的进程，或修改 napcat.listen_port 后重启。"
                )
                return
            raise
        self.bus.subscribe("napcat.send", self.on_send)
        logger.info(f"[NapcatServer] 正在监听端口 {port}")
        # 注册到生命周期，便于系统统一关闭。
        try:
            from cradle.core.lifecycle import global_lifecycle
            global_lifecycle.register(self)
        except ImportError:
            pass

    async def cleanup(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self.bus.unsubscribe_receiver(self)
        for ws in list(self._clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._clients.clear()

    async def _handler(self, ws: websockets.WebSocketServerProtocol, path: str | None = None):
        # 部分 websockets 版本可能不会传入 path 参数。
        self._clients.add(ws)
        proto = ws.subprotocol
        logger.info(f"[NapcatServer] 客户端已连接 {ws.remote_address} 子协议={proto}")
        try:
            async for msg in ws:
                # ``ws`` 读到的数据可能是 str/bytes，甚至直接是 Python 对象。
                # 线上曾出现 Napcat 直接推 list 而非 JSON 字符串，
                # 这会让 ``json.loads`` 抛 TypeError。这里显式区分处理。
                # 同时记录消息类型，方便排障。
                logger.debug(f"[NapcatServer] 收到帧 类型={type(msg)} 内容={msg!r}")

                if isinstance(msg, (bytes, str)):
                    try:
                        data = json.loads(msg)
                    except Exception:
                        # 非法 JSON 帧：忽略。
                        continue
                else:
                    # 已是 Python 对象（list/dict 等），直接使用。
                    data = msg

                event = BaseEvent(name="napcat.event",
                                  payload=data, source="NapcatServer")
                await self.bus.publish(event)
        except Exception as e:
            logger.error(f"[NapcatServer] 连接处理出错: {e}")
        finally:
            self._clients.discard(ws)
            logger.info(f"[NapcatServer] 客户端断开连接 {ws.remote_address}")

    async def on_send(self, event: Any):
        # 向全部已连接客户端广播发送。
        payload = event.payload
        text = json.dumps(payload)
        logger.debug(f"[NapcatServer] 正在向客户端发送: {text}")
        for ws in list(self._clients):
            try:
                await ws.send(text)
            except Exception:
                pass
