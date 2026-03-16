"""
文件名称：logger.py
所属层级：基础设施层-可观测性
核心作用：全局结构化日志器，统一日志格式，便于问题排查
设计原则：仅做日志输出，无业务逻辑，全链路trace_id透传
"""
import structlog
from typing import Any

# 全局结构化日志器配置
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

# 全局日志器单例
logger = structlog.get_logger("selrena-ai-core")


def get_logger(module_name: str) -> Any:
    """
    获取指定模块的日志器
    参数：
        module_name: 模块名称，用于日志标记
    返回：
        绑定了模块名称的结构化日志器
    """
    return logger.bind(module=module_name)