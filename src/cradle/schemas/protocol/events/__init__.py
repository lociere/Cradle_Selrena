"""Event schema namespace.

保持显式依赖：
- 基类: ``events.base``
- 动作: ``events.action``
- 感知: ``events.perception``
- 反射: ``events.reflex``
"""

from . import action, base, perception, reflex

__all__ = ["base", "action", "perception", "reflex"]
