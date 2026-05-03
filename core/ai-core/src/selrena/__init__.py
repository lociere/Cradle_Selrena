"""
月见（Selrena）Python AI 层
核心定位：纯灵魂意识核心，仅负责思考、人格、记忆、情绪
严格遵循：不碰任何场景/平台/IO杂活，所有输入输出均为标准化参数
"""
__version__ = "1.0.0"
__author__ = "Selrena Dev Team"

# 仅对外暴露核心入口，内部模块完全隐藏（最小权限原则）
__all__ = [
    "SelrenaSelfEntity",
    "KernelBridge",
]

# 延迟导入，避免循环依赖
from .identity.self_entity import SelrenaSelfEntity
from .ipc_server.outbound.kernel_bridge import KernelBridge
