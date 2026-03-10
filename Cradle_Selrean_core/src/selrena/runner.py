# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""外部调用入口：Python AI 核心服务。

这个类将所有内部组件封装为一个简单的对外接口，
供第一层内核或测试直接使用。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Callable

from .container import AIContainer
from ._internal.core.event_bus import EventBusClient


class PythonAICore:
    """Python AI 子系统的唯一入口。

    用法示例：
        core = PythonAICore(config_dir, data_dir)
        await core.start(llm_config)
        core.register_handler("user_input", handler)
        await core.send_event("ai_response", {"foo": "bar"})
        await core.stop()
    """

    def __init__(
        self,
        config_dir: str | None = None,
        data_dir: str | None = None,
        event_bus: Any | None = None,
    ) -> None:
        # default paths if not provided
        if config_dir is None:
            config_dir = "./config"
        if data_dir is None:
            data_dir = "./data"

        self.container = AIContainer(config_dir=config_dir, data_dir=data_dir)
        # allow overriding event bus (e.g. tests may use SimpleEventBusClient)
        if event_bus is not None:
            self.event_bus = event_bus
        else:
            self.event_bus = EventBusClient()
        self._started = False

    async def start(
        self, llm_config: dict[str, Any] = None, use_local_llm: bool = False
    ) -> None:
        """启动子系统。

        Args:
            llm_config: LLM 配置字典，参考 AIContainer.initialize 参数。
            use_local_llm: 是否使用本地模型。
        """
        if llm_config is None:
            llm_config = {}
        # 初始化容器及其组件
        await self.container.initialize(llm_config, use_local_llm)
        # 连接事件总线
        await self.event_bus.connect()
        self._started = True

    async def stop(self) -> None:
        """停止子系统并释放资源。"""
        if not self._started:
            return
        await self.event_bus.disconnect()
        await self.container.cleanup()
        self._started = False

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """注册事件处理器，事件由事件总线转发。"""
        self.event_bus.register_handler(event_type, handler)

    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """发送事件到内核或其他订阅者。"""
        return await self.event_bus.send_event(event_type, payload)

    # convenience accessors if needed
    def get_container(self) -> AIContainer:
        return self.container
