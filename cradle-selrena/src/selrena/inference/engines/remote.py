"""远程云端引擎实现占位。"""

from typing import List

from .base import BaseBrainBackend, ChatMessage, LLMConfig


class OpenAIRemoteBackend(BaseBrainBackend):
    async def initialize(self):
        # 未来可在此实现认证等逻辑
        pass

    async def cleanup(self):
        pass

    async def generate(self, messages: List[ChatMessage]) -> str:
        # 简单回显最后一条消息
        if messages:
            last = messages[-1]
            content = getattr(last, "content", "")
            return f"[remote] {content}"
        return "[remote]"
