# 该文件已格式化，内部备注/注释请使用中文说明
"""视觉及类似后端的抽象接口。"""

from abc import ABC, abstractmethod
from pathlib import Path


class VisionBackend(ABC):
    """提供图像描述和 OCR 操作的基类。"""

    @abstractmethod
    async def describe(self, image_path: str | Path) -> str:
        """为指定图像生成文本描述。"""
        pass

    @abstractmethod
    async def ocr(self, image_path: str | Path) -> str:
        """对图像执行 OCR，并返回提取的文本。"""
        pass
