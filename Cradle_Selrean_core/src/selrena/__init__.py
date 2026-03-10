# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""Python AI 子系统入口模块。

本包只对外公开 `PythonAICore` 类，代表整个 AI 核心服务。
内部各个子模块属于实现细节，调用者不应直接访问。
"""

from .runner import PythonAICore

__all__ = ["PythonAICore"]
