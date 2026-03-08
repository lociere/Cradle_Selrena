"""音频处理后端接口（STT/TTS）（迁移自 cradle_selrena_core）"""

from abc import ABC, abstractmethod
from pathlib import Path


class STTBackend(ABC):
    """语音识别后端抽象基类"""
    
    @abstractmethod
    async def transcribe(self, audio_path: str | Path) -> str:
        """
        语音转文字
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            识别的文本
        """
        pass


class TTSBackend(ABC):
    """语音合成后端抽象基类"""
    
    @abstractmethod
    async def synthesize(self, text: str, output_path: str | Path) -> str:
        """
        文字转语音
        
        Args:
            text: 输入文本
            output_path: 输出音频路径
            
        Returns:
            输出的音频文件路径
        """
        pass
