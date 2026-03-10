# 核心内核端口定义
from abc import ABC, abstractmethod
from typing import Optional


class KernelPort(ABC):
    """TS/Rust 内核向 Python 服务提供的接口。

    所有方法均为异步非阻塞，内核通过事件总线实现这些操作。
    """

    @abstractmethod
    async def send_message(self, text: str, emotion: Optional[str] = None) -> None:
        """向前端或聊天适配器发送文本消息。"""

    @abstractmethod
    async def play_audio(self, audio_path: str) -> None:
        """请求内核播放本地音频文件。"""

    @abstractmethod
    async def capture_screen(self) -> str:
        """截取屏幕并返回文件路径。"""

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """读取并返回内核可访问文件的内容。"""

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """通过内核将文本写入文件。"""
