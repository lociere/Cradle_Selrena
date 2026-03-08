"""事件总线客户端

用于与TS内核事件总线通信的Python客户端
支持HTTP/WebSocket/ZeroMQ等多种通信方式
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class EventBusTransport(Enum):
    """事件总线传输协议"""
    HTTP = "http"
    WEBSOCKET = "websocket"
    ZEROMQ = "zeromq"


class EventBusClient:
    """
    事件总线客户端
    
    负责与TS内核事件总线通信，发送和接收事件
    """
    
    def __init__(
        self,
        transport: EventBusTransport = EventBusTransport.HTTP,
        host: str = "localhost",
        port: int = 3000,
        endpoint: str = "/events"
    ):
        """
        初始化事件总线客户端
        
        Args:
            transport: 传输协议
            host: 主机地址
            port: 端口号
            endpoint: HTTP端点路径
        """
        self.transport = transport
        self.host = host
        self.port = port
        self.endpoint = endpoint
        self.base_url = f"http://{host}:{port}"
        self.event_handlers: Dict[str, Callable] = {}
        self.is_connected = False

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """注册事件处理器."""
        self.event_handlers[event_type] = handler
        logger.info(f"已注册事件处理器: {event_type}")

    async def start_listening(self) -> None:
        """启动监听循环（占位实现）。"""
        # 实际应根据 transport 读取事件，这里只是保持连接
        while self.is_connected:
            await asyncio.sleep(1)
        
        # 根据传输协议初始化连接
        if transport == EventBusTransport.HTTP:
            self._init_http_client()
        elif transport == EventBusTransport.WEBSOCKET:
            self._init_websocket_client()
        elif transport == EventBusTransport.ZEROMQ:
            self._init_zeromq_client()
    
    def _init_http_client(self):
        """初始化HTTP客户端"""
        try:
            import aiohttp
            self.session = None
            self._session_class = aiohttp.ClientSession
        except ImportError:
            logger.warning("aiohttp未安装，将使用requests（同步）")
            self.session = None
            self._session_class = None
    
    def _init_websocket_client(self):
        """初始化WebSocket客户端"""
        try:
            import websockets
            self.websocket = None
            self._websocket_class = websockets.connect
        except ImportError:
            logger.error("websockets未安装，无法使用WebSocket传输")
            raise
    
    def _init_zeromq_client(self):
        """初始化ZeroMQ客户端"""
        try:
            import zmq
            import zmq.asyncio
            self.context = zmq.asyncio.Context()
            self.socket = None
        except ImportError:
            logger.error("pyzmq未安装，无法使用ZeroMQ传输")
            raise
    
    async def connect(self):
        """连接到事件总线"""
        try:
            if self.transport == EventBusTransport.HTTP:
                await self._connect_http()
            elif self.transport == EventBusTransport.WEBSOCKET:
                await self._connect_websocket()
            elif self.transport == EventBusTransport.ZEROMQ:
                await self._connect_zeromq()
            
            self.is_connected = True
            logger.info(f"已连接到事件总线 ({self.transport.value}://{self.host}:{self.port})")
            
        except Exception as e:
            logger.error(f"连接事件总线失败: {e}")
            raise
    
    async def _connect_http(self):
        """连接HTTP事件总线"""
        if self._session_class:
            import aiohttp
            self.session = await self._session_class().__aenter__()
    
    async def _connect_websocket(self):
        """连接WebSocket事件总线"""
        ws_url = f"ws://{self.host}:{self.port}/ws"
        self.websocket = await self._websocket_class(ws_url)
    
    async def _connect_zeromq(self):
        """连接ZeroMQ事件总线"""
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f"tcp://{self.host}:{self.port}")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
    
    async def disconnect(self):
        """断开连接"""
        try:
            if self.transport == EventBusTransport.HTTP and self.session:
                await self.session.close()
            elif self.transport == EventBusTransport.WEBSOCKET and self.websocket:
                await self.websocket.close()
            elif self.transport == EventBusTransport.ZEROMQ and self.socket:
                self.socket.close()
            
            self.is_connected = False
            logger.info("已断开事件总线连接")
            
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
    
    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        发送事件到事件总线
        
        Args:
            event_type: 事件类型
            payload: 事件载荷
            
        Returns:
            是否发送成功
        """
        if not self.is_connected:
            logger.warning("未连接到事件总线")
            return False
        
        event = {
            "type": event_type,
            "timestamp": asyncio.get_event_loop().time(),
            "payload": payload
        }
        
        try:
            if self.transport == EventBusTransport.HTTP:
                return await self._send_http_event(event)
            elif self.transport == EventBusTransport.WEBSOCKET:
                return await self._send_websocket_event(event)
            elif self.transport == EventBusTransport.ZEROMQ:
                return await self._send_zeromq_event(event)
            
        except Exception as e:
            logger.error(f"发送事件失败: {e}")
            return False
    
    async def _send_http_event(self, event: Dict) -> bool:
        """通过HTTP发送事件"""
        if not self.session:
            # 使用requests作为备选
            try:
                import requests
                response = requests.post(
                    f"{self.base_url}{self.endpoint}",
                    json=event,
                    timeout=5
                )
                return response.status_code == 200
            except ImportError:
                logger.error("requests未安装，无法发送HTTP事件")
                return False
        
        async with self.session.post(f"{self.base_url}{self.endpoint}", json=event) as response:
            return response.status == 200
    
    async def _send_websocket_event(self, event: Dict) -> bool:
        """通过WebSocket发送事件"""
        if not self.websocket:
            return False
        try:
            await self.websocket.send(json.dumps(event))
            return True
        except Exception as e:
            logger.error(f"WebSocket发送失败: {e}")
            return False
    
    async def _send_zeromq_event(self, event: Dict) -> bool:
        """通过ZeroMQ发送事件"""
        if not self.socket:
            return False
        try:
            self.socket.send_json(event)
            return True
        except Exception as e:
            logger.error(f"ZeroMQ发送失败: {e}")
            return False

# ---------------------------------------------------------------------------
# 简化事件总线客户端，用于快速测试/简化模式
# ---------------------------------------------------------------------------
class SimpleEventBusClient:
    """极简事件总线客户端，仅在本地内存中收发事件"""

    def __init__(self, host: str = "localhost", port: int = 3000):
        self.handlers: Dict[str, Callable] = {}
        self.is_connected = False

    async def connect(self):
        self.is_connected = True
        logger.info("SimpleEventBusClient 已连接（内存模式）")

    async def disconnect(self):
        self.is_connected = False
        logger.info("SimpleEventBusClient 断开连接")

    def register_handler(self, event_type: str, handler: Callable) -> None:
        self.handlers[event_type] = handler
        logger.info(f"Simple 客户端注册处理器: {event_type}")

    async def start_listening(self):
        # no-op
        while self.is_connected:
            await asyncio.sleep(1)

    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        # immediately invoke handler if present
        handler = self.handlers.get(event_type)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler({"type": event_type, "payload": payload})
                else:
                    handler({"type": event_type, "payload": payload})
                return True
            except Exception as e:
                logger.error(f"Simple 客户端处理事件失败: {e}")
                return False
        return True