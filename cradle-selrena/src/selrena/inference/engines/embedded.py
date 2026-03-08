"""本地嵌入式引擎实现（占位）。"""

from typing import List

from .base import BaseBrainBackend, ChatMessage, LLMConfig


class LlamaCppEmbeddedBackend(BaseBrainBackend):
    async def initialize(self):
        # 本地模型初始化逻辑
        pass

    async def cleanup(self):
        pass

    async def generate(self, messages: List[ChatMessage]) -> str:
        # 简单回显，用于测试
        if messages:
            last = messages[-1]
            content = getattr(last, "content", "")
            return f"[local] {content}"
        return "[local]"
