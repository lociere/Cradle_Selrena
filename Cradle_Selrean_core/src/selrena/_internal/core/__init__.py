# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""核心基础设施导出。

本包定义纯内部的基础设施模块，位于框架核心层，符合
架构文档的规定。
"""

from .config_manager import ConfigManager, global_config

from .event_bus import EventBusClient, EventBusTransport, SimpleEventBusClient

__all__: list[str] = [
    "ConfigManager",
    "global_config",
    "EventBusClient",
    "EventBusTransport",
    "SimpleEventBusClient",
]
