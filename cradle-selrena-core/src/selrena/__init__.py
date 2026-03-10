"""Selrena Python 包根入口。

对外仅暴露核心类和工厂函数。
"""

from .ai_core import PythonAICore
from .domain.self.self_entity import SelrenaSelfEntity

__all__ = ["PythonAICore", "SelrenaSelfEntity"]
