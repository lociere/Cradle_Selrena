"""Protocol schema namespace.

保持边界清晰：请从 ``protocol.events.<module>`` 显式导入具体事件模型。
"""

from . import events

__all__ = ["events"]
