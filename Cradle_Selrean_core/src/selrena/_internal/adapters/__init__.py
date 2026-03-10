# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""适配器子模块的导出。

本包在迁移阶段用于集中暴露各类适配器类型，便于上层
统一引用。
"""

from .zmq_bus import ZMQEventBusAdapter, ZMQConfig

# 具体的适配器类分别定义在各自模块中

from .kernel import KernelAdapter

from .memory import MemoryAdapter

from .persona import PersonaAdapter

__all__: list[str] = [
    "ZMQEventBusAdapter",
    "ZMQConfig",
    "KernelAdapter",
    "MemoryAdapter",
    "PersonaAdapter",
]
