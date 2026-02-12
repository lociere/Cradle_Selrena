import asyncio
import signal
from typing import List, Protocol, Any
from cradle.utils.logger import logger
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.schemas.protocol.events.base import BaseEvent

class LifecycleComponent(Protocol):
    """
    生命周期组件协议
    任何需要优雅关闭的模块都应该实现 cleanup 或 stop 方法
    """
    async def cleanup(self): ...

class LifecycleManager:
    """
    生命周期管理器 (Central Nervous System Control)
    负责协调系统的启动、运行和优雅退出。
    确保在断电前，记忆已保存、连接已断开。
    """
    def __init__(self):
        self._components: List[LifecycleComponent] = []
        self._is_running = False
        self._shutdown_event = asyncio.Event()
        
        # 监听系统级关闭信号
        global_event_bus.subscribe("system.shutdown", self._on_shutdown_signal)

    def register(self, component: Any):
        """注册一个组件到生命周期管理"""
        # 检查组件是否有 cleanup 或 stop 方法
        if hasattr(component, "cleanup") or hasattr(component, "stop"):
            self._components.append(component)
            logger.debug(f"[Lifecycle] 已注册组件: {component.__class__.__name__}")

    async def unregister(self, component: Any):
        """
        注销并停止特定组件，不影响其他系统组件。
        用于热重载或动态卸载场景。
        """
        if component in self._components:
            name = component.__class__.__name__
            logger.info(f"[Lifecycle] 正在动态注销组件: {name}...")
            
            try:
                # 1. 触发清理
                if hasattr(component, "cleanup"):
                    if asyncio.iscoroutinefunction(component.cleanup):
                        await component.cleanup()
                    else:
                        component.cleanup()
                elif hasattr(component, "stop"):
                    if asyncio.iscoroutinefunction(component.stop):
                        await component.stop()
                    else:
                        component.stop()
            except Exception as e:
                logger.error(f"注销组件 {name} 失败: {e}")
            
            # 2. 从列表移除
            self._components.remove(component)
            logger.info(f"[Lifecycle] 组件 {name} 已安全移除。")

    async def _on_shutdown_signal(self, event: BaseEvent):
        """接收到神经系统的关闭信号"""
        reason = event.payload.get("reason", "unknown") if event.payload else "unknown"
        logger.warning(f"收到关闭信号，原因: {reason}。正在启动优雅退出流程...")
        await self.shutdown()

    async def wait_for_shutdown(self):
        """阻塞直到接收到关闭信号"""
        self._is_running = True
        await self._shutdown_event.wait()

    async def shutdown(self):
        """执行关闭序列"""
        if not self._is_running:
            return
            
        self._is_running = False
        logger.info("--- 正在执行系统停机序列 ---")

        # 1. 逆序关闭组件 (遵循栈的原则：后进先出)
        # 例如：先注册了 Memory，后注册了 Ear。
        # 关闭时：先关 Ear (停止接收输入)，再关 Memory (保存数据)。
        for component in reversed(self._components):
            name = component.__class__.__name__
            try:
                logger.info(f"正在停止: {name}...")
                
                # 优先调用 cleanup (异步)，其次是 stop (同步/异步)
                if hasattr(component, "cleanup"):
                    if asyncio.iscoroutinefunction(component.cleanup):
                        await component.cleanup()
                    else:
                        component.cleanup()
                        
                elif hasattr(component, "stop"):
                    if asyncio.iscoroutinefunction(component.stop):
                        await component.stop()
                    else:
                        component.stop()
                        
                logger.info(f"已停止: {name}")
            except Exception as e:
                logger.error(f"停止组件 {name} 时发生错误: {e}")

        logger.info("--- 系统已安全休眠 ---")
        
        # 释放 wait_for_shutdown 的阻塞
        self._shutdown_event.set()

# 全局生命周期实例
global_lifecycle = LifecycleManager()
