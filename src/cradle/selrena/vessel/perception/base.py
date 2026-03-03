from abc import ABC, abstractmethod
from typing import Any, List, Tuple


class BaseNeuralSignal(ABC):
    """
    神经信号基类 (Neural Signal Base)
    所有感官模块（如视觉、听觉）必须将物理信号（光、声）转化为 LLM 兼容的数据格式并封装于此。
    """
    pass


class BaseCortex(ABC):
    """
    感知皮层基类 (Cortex Base)
    负责检测对应的外部物理信号并将其转导为内部数字信号。
    """

    @abstractmethod
    async def initialize(self):
        pass

    @abstractmethod
    async def cleanup(self):
        pass

    @abstractmethod
    def has_signal(self, text: str) -> bool:
        """检查原始输入（如文本里的标签或URL）中是否包含本模态可识别的物理刺激"""
        pass

    @abstractmethod
    async def process(self, text: str) -> Tuple[str, List[BaseNeuralSignal]]:
        """
        处理物理刺激。
        返回: (清洗/剥离后的纯净文本, 提取出的神经信号列表)
        """
        pass
