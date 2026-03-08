"""视觉理解后端接口（迁移自 cradle_selrena_core）"""

from abc import ABC, abstractmethod
from pathlib import Path


class VisionBackend(ABC):
    """视觉理解后端抽象基类"""
    
    @abstractmethod
    async def describe(self, image_path: str | Path) -> str:
        """
        描述图片内容（Image Captioning）
        
        Args:
            image_path: 图片路径
            
        Returns:
            图片描述文本
        """
        pass
    
    @abstractmethod
    async def ocr(self, image_path: str | Path) -> str:
        """
        光学字符识别
        
        Args:
            image_path: 图片路径
            
        Returns:
            识别的文本
        """
        pass
