from abc import ABC, abstractmethod
from typing import List, Dict
from cradle.schemas.configs.soul import LLMConfig


class BaseBrainBackend(ABC):
    """
    大脑后端接口 (Abstract Strategy)
    定义了任何一种 LLM 驱动（无论是云端还是本地）必须实现的方法。
    """

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def initialize(self):
        """异步初始化 (例如加载模型、建立连接)"""
        pass

    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """
        核心思考方法
        :param messages: OpenAI 格式的历史消息列表 [{"role": "user", "content": "..."}]
        :return: 生成的文本回复
        """
        pass

    async def cleanup(self):
        """清理资源"""
        pass
