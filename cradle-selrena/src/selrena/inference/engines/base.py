"""抽象大脑后端接口（迁移并简化依赖）。"""

from abc import ABC, abstractmethod
from typing import Any, List, Dict

# 为了避免尚未迁移的 schemas 依赖，这里使用通用类型。
ChatMessage = Dict[str, Any]
LLMConfig = Any


class BaseBrainBackend(ABC):
    """抽象大脑后端接口。"""

    def __init__(self, config: LLMConfig):
        # config 在日后可替换为具体配置模型
        self.config = config

    @abstractmethod
    async def initialize(self):
        pass

    async def cleanup(self):
        pass

    @abstractmethod
    async def generate(self, messages: List[ChatMessage]) -> str:
        pass

    async def perceive(self, message: ChatMessage) -> str | None:
        return None

    @property
    def is_multimodal(self) -> bool:
        return False
