"""AI 核心唯一对外入口，暴露基础生命周期方法。"""

from __future__ import annotations

from typing import Any, Callable, Dict


class PythonAICore:
    """Selrena Python AI 子系统的单例入口。

    方法仅为示例，具体实现将在各模块中完成。
    """

    def __init__(self, config_dir: str | None = None, data_dir: str | None = None):
        self.config_dir = config_dir or "./config"
        self.data_dir = data_dir or "./data"
        self._started = False

    async def start(self, **kwargs: Any) -> None:
        """启动 AI 核心。"""
        self._started = True

    async def stop(self) -> None:
        """停止 AI 核心并清理资源。"""
        self._started = False

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """注册事件处理器。"""
        pass

    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """发送事件到内核或其他订阅者"""
        return False
