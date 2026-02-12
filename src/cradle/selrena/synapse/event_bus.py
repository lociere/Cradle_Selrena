import asyncio
from typing import Callable, Any, Dict, List
from collections import defaultdict
from cradle.utils.logger import logger
from cradle.schemas.protocol.events.base import BaseEvent

class EventBus:
    """
    神经中枢,负责在身体各器官和灵魂之间传递电信号
    
    Architecture V2 Update:
    - 废弃了旧的 `Event` (Dataclass)
    - 全面采用 `BaseEvent` (Pydantic Model) 及其子类
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        # 接收者映射: ReceiverObj -> List[(EventName, Callback)]
        self._receivers: Dict[Any, List[tuple]] = defaultdict(list)
        logger.debug("神经中枢 (EventBus) 初始化完毕。")

    def subscribe(self, event_name: str, callback: Callable):
        """
        器官可以订阅特定的神经信号
        return: unsubscribe callback (一个用于取消订阅的函数)
        """
        self._subscribers[event_name].append(callback)
        
        # 自动识别并记录接收者 (如果是绑定方法)
        receiver = getattr(callback, "__self__", None)
        if receiver:
            self._receivers[receiver].append((event_name, callback))
            
        logger.debug(f"[神经连接] 模块已接入: 信号={event_name}, 接收者={callback.__qualname__}")
        
        def unsubscribe():
            self.unsubscribe(event_name, callback)
        return unsubscribe

    def unsubscribe_receiver(self, receiver: Any):
        """
        [新增] 断开某一器官的所有神经连接
        不再需要手动保存 unsubscribe handle，只要传入对象本身即可一键断开。
        """
        if receiver in self._receivers:
            logger.debug(f"[神经阻断] 正在切断 {receiver.__class__.__name__} 的所有连接...")
            # 复制列表进行迭代，因为 unsubscribe 会修改 _receivers
            for event_name, cb in list(self._receivers[receiver]):
                self.unsubscribe(event_name, cb)
            # 确保彻底清理
            if receiver in self._receivers:
                del self._receivers[receiver]

    def unsubscribe(self, event_name: str, callback: Callable):
        """断开特定的一根神经连接"""
        # 1. 从订阅表移除
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(callback)
                # logger.debug(f"[神经断开] 信号={event_name}, 接收者={callback.__qualname__}")
                if not self._subscribers[event_name]:
                    del self._subscribers[event_name]
            except ValueError:
                pass
        
        # 2. 从接收者映射表移除 (保持一致性)
        receiver = getattr(callback, "__self__", None)
        if receiver and receiver in self._receivers:
            try:
                self._receivers[receiver].remove((event_name, callback))
                if not self._receivers[receiver]:
                    del self._receivers[receiver]
            except ValueError:
                pass

    async def publish(self, event: BaseEvent):
        """发送神经信号 (Strict Protocol)"""
        if not isinstance(event, BaseEvent):
             # 最后的容错警告，但我们应当避免这种情况
             logger.warning(f"[Protocol Breach] ⚠️ 接收到非标准信号: {type(event)} -> 尝试 Duck Typing 但不推荐")
        
        # 统一使用 BaseEvent 接口
        event_name = event.name
        sender = event.source

        if event_name in self._subscribers:
            # 找到所有通过这根神经连接的器官，并发通知它们
            callbacks = self._subscribers[event_name]
            logger.debug(f"[神经冲动] 信号传导: {event_name} (from: {sender}) -> 激活 {len(callbacks)} 个受体")
            tasks = [cb(event) for cb in callbacks]
            await asyncio.gather(*tasks)
        else:
            # logger.warning(f"[神经信号丢失] 无受体响应: {event_name}")
            pass

# 全局单例
global_event_bus = EventBus()
