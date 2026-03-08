"""ZMQ 事件总线适配器（迁移自 cradle_selrena_core）"""

import asyncio
import json
import zmq
import zmq.asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

from selrena.utils.logger import logger


@dataclass
class ZMQConfig:
    """ZMQ 配置"""
    host: str = "127.0.0.1"
    pub_port: int = 5555  # 发布者端口
    sub_port: int = 5556  # 订阅者端口
    protocol: str = "tcp"


class ZMQEventBusAdapter:
    """
    ZMQ 事件总线适配器
    
    负责 Python AI 核心与 TypeScript 内核之间的事件通信
    """
    
    def __init__(self, config: Optional[ZMQConfig] = None):
        self.config = config or ZMQConfig()
        self.context = zmq.asyncio.Context()
        self.publisher: Optional[zmq.asyncio.PubSocket] = None
        self.subscriber: Optional[zmq.asyncio.SubSocket] = None
        self.is_connected = False
        self.event_handlers: Dict[str, List[Callable]] = {}
        self._receive_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """连接到 ZMQ 总线"""
        if self.is_connected:
            return
        
        try:
            # 创建发布者
            self.publisher = self.context.socket(zmq.PUB)
            pub_address = f"{self.config.protocol}://{self.config.host}:{self.config.pub_port}"
            self.publisher.bind(pub_address)
            logger.info(f"📡 ZMQ 发布者绑定到：{pub_address}")
            
            # 创建订阅者
            self.subscriber = self.context.socket(zmq.SUB)
            sub_address = f"{self.config.protocol}://{self.config.host}:{self.config.sub_port}"
            self.subscriber.bind(sub_address)
            self.subscriber.setsockopt_string(zmq.SUBSCRIBE, "")  # 订阅所有消息
            logger.info(f"📡 ZMQ 订阅者绑定到：{sub_address}")
            
            self.is_connected = True
            logger.info("✅ ZMQ 事件总线已连接")
            
            # 启动消息接收循环
            self._receive_task = asyncio.create_task(self._receive_messages())
            
        except Exception as e:
            logger.error(f"❌ ZMQ 连接失败：{e}")
            raise e
    
    async def disconnect(self) -> None:
        """断开连接"""
        if not self.is_connected:
            return
        
        try:
            # 取消接收任务
            if self._receive_task:
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
            
            # 关闭 sockets
            if self.publisher:
                self.publisher.close()
            if self.subscriber:
                self.subscriber.close()
            
            self.context.term()
            self.is_connected = False
            logger.info("✅ ZMQ 事件总线已断开连接")
            
        except Exception as e:
            logger.error(f"❌ ZMQ 断开连接失败：{e}")
    
    async def publish(self, event: Dict[str, Any]) -> None:
        """
        发布事件
        
        Args:
            event: 事件字典，包含 type, timestamp, traceId, source, payload 等字段
        """
        if not self.is_connected or not self.publisher:
            raise RuntimeError("ZMQ 事件总线未连接")
        
        try:
            message = json.dumps(event, ensure_ascii=False)
            await self.publisher.send_multipart([b"events", message.encode('utf-8')])
            logger.debug(f"📤 发布事件：{event.get('type')} ({event.get('traceId')})")
        except Exception as e:
            logger.error(f"❌ 发布事件失败：{e}")
            raise e
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.info(f"📥 订阅事件类型：{event_type}")
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """
        取消订阅
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if event_type in self.event_handlers:
            handlers = self.event_handlers[event_type]
            if handler in handlers:
                handlers.remove(handler)
                logger.info(f"📤 取消订阅事件类型：{event_type}")
    
    async def _receive_messages(self) -> None:
        """消息接收循环"""
        if not self.subscriber:
            return
        
        try:
            while self.is_connected:
                try:
                    # 接收消息
                    topic, message = await self.subscriber.recv_multipart()
                    
                    if topic == b"events":
                        event = json.loads(message.decode('utf-8'))
                        logger.debug(f"📥 收到事件：{event.get('type')} ({event.get('traceId')})")
                        
                        # 调用事件处理器
                        event_type = event.get('type', '')
                        handlers = self.event_handlers.get(event_type, [])
                        
                        for handler in handlers:
                            try:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(event)
                                else:
                                    handler(event)
                            except Exception as e:
                                logger.error(f"❌ 事件处理器错误 ({event_type}): {e}")
                
                except zmq.ZMQError as e:
                    if self.is_connected:
                        logger.error(f"❌ ZMQ 接收错误：{e}")
                    await asyncio.sleep(0.1)  # 避免忙等待
                
        except asyncio.CancelledError:
            logger.info("🛑 ZMQ 消息接收循环已取消")
        except Exception as e:
            if self.is_connected:
                logger.error(f"❌ ZMQ 接收循环错误：{e}")
    
    def is_ready(self) -> bool:
        """检查连接状态"""
        return self.is_connected
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息"""
        return asdict(self.config)


# 便捷函数
async def create_zmq_event_bus(config: Optional[ZMQConfig] = None) -> ZMQEventBusAdapter:
    """创建并连接 ZMQ 事件总线"""
    adapter = ZMQEventBusAdapter(config)
    await adapter.connect()
    return adapter
