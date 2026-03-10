# 该文件已格式化，内部备注/注释请使用中文说明
"""音频/语音接口抽象，包含 STT 和 TTS。"""

from abc import ABC, abstractmethod
from pathlib import Path


class STTBackend(ABC):
    """语音转文字后端的抽象基类。"""

    @abstractmethod
    async def transcribe(self, audio_path: str | Path) -> str:
        """将指定音频文件转换为文本。"""
        pass


class TTSBackend(ABC):
    """文字转语音后端的抽象基类。"""

    @abstractmethod
    async def synthesize(self, text: str, output_path: str | Path) -> str:
        """根据文本生成音频并保存到输出路径。"""
        pass
