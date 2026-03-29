"""
文件名称：event_bus.py
所属层级：基础设施层
核心作用：进程内领域事件总线，实现模块间解耦通信，无直接硬编码依赖
设计原则：发布-订阅模式，异步非阻塞，仅做事件分发，无任何业务逻辑
"""
from typing import Callable, Type, Dict, List
from abc import ABC
from dataclasses import dataclass, field
from uuid import uuid4
from datetime import datetime
import asyncio


# ======================================
# 领域事件基类
# ======================================
@dataclass
class DomainEvent(ABC):
    """所有领域事件的基类，保证全链路可追踪"""
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = field(init=False)

    def __post_init__(self) -> None:
        """自动设置事件类型为子类类名，无需手动赋值"""
        self.event_type = self.__class__.__name__


# ======================================
# 事件总线实现（单例模式）
# ======================================
class DomainEventBus:
    """
    进程内领域事件总线，单例模式
    核心作用：模块间解耦，模块间不直接调用，仅通过事件通信
    """
    _instance = None

    def __new__(cls):
        """单例模式，保证整个进程只有一个事件总线"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        """初始化事件处理器存储，仅在单例创建时执行一次"""
        # 事件处理器字典：key=事件类型，value=处理器函数列表
        self._handlers: Dict[Type[DomainEvent], List[Callable]] = {}

    def subscribe(self, event_type: Type[DomainEvent], handler: Callable) -> None:
        """
        订阅指定类型的事件
        参数：
            event_type: 要订阅的事件类型（必须继承DomainEvent）
            handler: 异步事件处理器函数，入参为事件实例
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """
        发布领域事件，异步分发给所有订阅的处理器
        参数：
            event: 要发布的事件实例
        规范：单个处理器异常不影响其他处理器执行，不会吞异常
        """
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            return

        # 包装处理器，捕获单个处理器的异常，避免连锁崩溃
        async def wrapped_handler(handler: Callable, e: DomainEvent) -> None:
            try:
                await handler(e)
            except Exception as ex:
                try:
                    from selrena.core.observability.logger import get_logger
                    logger = get_logger("event_bus")
                    logger.error("事件处理器执行异常", error=str(ex), exc_info=True)
                except Exception:
                    # 回退到 print，以防 logger 尚未可用
                    print(f"[事件总线] 处理器执行异常: {str(ex)}")

        # 并发执行所有处理器
        tasks = [wrapped_handler(h, event) for h in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)