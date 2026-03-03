import asyncio
import signal
from typing import Any, List, Protocol

from cradle.schemas.protocol.events.base import BaseEvent
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger


class LifecycleComponent(Protocol):
    """
    生命周期组件协议
    任何需要优雅关闭的模块都应该实现 cleanup 或 stop 方法
    """

    async def cleanup(self): ...
    async def stop(self): ...


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
        self._default_shutdown_timeout = 10.0  # 每个组件的超时限制 (秒)

        # 监听系统级关闭信号
        global_event_bus.subscribe("system.shutdown", self._on_shutdown_signal)

    async def __aenter__(self):
        """支持 Async Context Manager"""
        self._is_running = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动触发关闭"""
        if exc_type:
            logger.error(f"[Lifecycle] Context exit with error: {exc_val}")
        await self.shutdown(reason="context_exit")

    def register(self, component: Any):
        """注册一个组件到生命周期管理"""
        # 检查组件是否有 cleanup 或 stop 方法
        if hasattr(component, "cleanup") or hasattr(component, "stop"):
            if component not in self._components:
                self._components.append(component)
                logger.debug(f"[Lifecycle] 已注册组件: {component.__class__.__name__}")
            else:
                logger.warning(
                    f"[Lifecycle] 组件重复注册: {component.__class__.__name__}")

    async def unregister(self, component: Any):
        """
        注销并停止特定组件，不影响其他系统组件。
        用于热重载或动态卸载场景。
        """
        if component in self._components:
            name = component.__class__.__name__
            logger.info(f"[Lifecycle] 正在动态注销组件: {name}...")

            await self._stop_component(component)

            # 2. 从列表移除
            if component in self._components:
                self._components.remove(component)
            logger.info(f"[Lifecycle] 组件 {name} 已安全移除。")
        else:
            logger.warning(
                f"[Lifecycle] 尝试注销未注册组件: {getattr(component, '__class__', {}).get('__name__', 'Unknown')}")

    async def _on_shutdown_signal(self, event: BaseEvent):
        """接收到神经系统的关闭信号"""
        reason = str(event.payload.get(
            "reason", "unknown")) if event.payload else "unknown"
        logger.warning(f"收到关闭信号，原因: {reason}。正在启动优雅退出流程...")
        await self.shutdown(reason=reason)

    async def wait_for_shutdown(self):
        """阻塞直到接收到关闭信号"""
        self._is_running = True
        logger.info("[Lifecycle] 系统主循环已就绪，等待终止信号...")
        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            logger.warning("[Lifecycle] 主循环被取消")
            await self.shutdown(reason="cancelled")

    async def _stop_component(self, component: Any, timeout: float = 5.0):
        """封装单个组件的停止逻辑，带超时保护"""
        name = component.__class__.__name__
        logger.info(f"正在停止: {name}...")

        async def _do_stop():
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

        try:
            await asyncio.wait_for(_do_stop(), timeout=timeout)
            logger.info(f"已停止: {name}")
        except asyncio.TimeoutError:
            logger.error(f"停止组件 {name} 超时 ({timeout}s)! 可能会有资源泄漏。")
        except Exception as e:
            logger.error(f"停止组件 {name} 时发生错误: {e}")

    async def shutdown(self, reason: str = "manual"):
        """执行关闭序列"""
        if not self._is_running and self._shutdown_event.is_set():
            logger.debug("[Lifecycle] 系统已关闭，跳过重复关闭请求。")
            return

        self._is_running = False
        logger.info(f"--- 正在执行系统停机序列 (Reason: {reason}) ---")

        # 1. 逆序关闭组件 (遵循栈的原则：后进先出)
        # 复制列表以防修改
        components_to_stop = list(reversed(self._components))

        for component in components_to_stop:
            # 使用较长的超时时间确保数据保存，但防止无限挂起
            await self._stop_component(component, timeout=self._default_shutdown_timeout)

        # Clear list
        self._components.clear()

        logger.info("--- 系统已安全休眠 ---")

        # 释放 wait_for_shutdown 的阻塞
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()


# 全局生命周期实例
global_lifecycle = LifecycleManager()
