# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""Collection of generic payload models.

This module is intentionally lightweight and decoupled from multimodal
content to allow arbitrary data passing without overhead.
"""

from typing import Any
from pydantic import BaseModel


class Payload(BaseModel):
    """Simple key-value container for arbitrary data."""

    data: Any


__all__: list[str] = ["Payload"]
