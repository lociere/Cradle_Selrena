"""
端口包声明：仅导出端口类。请勿在此文件中实现端口逻辑。

目的:
- 让外部可以通过 `from selrena._internal.ports import KernelPort` 之类的语句导入。
- 保持实现与接口分离，避免循环导入与包初始化时副作用。

注意: 如果新增端口，请在此处添加对应导出语句，并把类名加入 `__all__`。
"""
from .kernel_port import KernelPort
from .memory_port import MemoryPort
from .inference_port import InferencePort
from .persona_port import PersonaPort
from .agent import AgentPort

__all__ = [
    "KernelPort",
    "MemoryPort",
    "InferencePort",
    "PersonaPort",
    "AgentPort",
]
