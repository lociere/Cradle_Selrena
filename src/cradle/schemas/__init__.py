"""Schema namespace package.

边界约束：
- ``configs`` 仅承载配置模型；
- ``domain`` 仅承载业务领域数据模型；
- ``protocol`` 仅承载事件/通信协议模型。

为避免跨模块耦合，禁止在该根入口做跨域聚合导出。
请从对应子模块显式导入。
"""

from . import configs, domain, protocol

__all__ = ["configs", "domain", "protocol"]
