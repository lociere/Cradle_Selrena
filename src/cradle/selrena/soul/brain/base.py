from abc import ABC, abstractmethod
from typing import List

from cradle.schemas.configs.soul import LLMConfig
from cradle.schemas.domain.chat import Message as ChatMessage


class BaseBrainBackend(ABC):
    """
    大脑后端接口 (Abstract Strategy)
    定义了任何一种 LLM 驱动（无论是云端还是本地）必须实现的方法。
    """

    # --- Initialization ---

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def initialize(self):
        """异步初始化 (例如加载模型、建立连接)"""
        pass

    async def cleanup(self):
        """清理资源"""
        pass

    # --- Core Interface ---

    @abstractmethod
    async def generate(self, messages: List[ChatMessage]) -> str:
        """
        核心思考方法
        :param messages: 标准的 Message 对象列表
        :return: 生成的文本回复
        """
        pass

    @property
    def is_multimodal(self) -> bool:
        """是否支持多模态输入 (默认为 False，子类可覆盖)"""
        return False
