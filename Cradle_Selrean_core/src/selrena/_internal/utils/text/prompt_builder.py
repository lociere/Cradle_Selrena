# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from typing import Dict, Any


class PromptBuilder:
    """Helper to construct prompt strings from various pieces."""

    @staticmethod
    def build(system: str, history: str) -> str:
        return f"{system}\n{history}"
