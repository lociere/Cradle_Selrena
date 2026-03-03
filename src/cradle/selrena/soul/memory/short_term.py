import json
import os
import re
from typing import Any, Dict, List

from cradle.schemas.domain.chat import Message
from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath


class ShortTermMemory:
    """
    短期记忆管理器 (持久化 + 滑动窗口)
    负责存储当前对话上下文，并在系统重启时恢复记忆。
    """

    def __init__(self, max_history_len: int = 20):
        """
        [Standardized]
        ShortTermMemory no longer manages file persistence by itself.
        It is now a pure in-memory sliding window buffer.
        Persistence is handled by the Brain or a dedicated SessionManager if needed.
        """
        self.max_history_len = max_history_len
        self.messages: List[Message] = []

    def add(self, role: str, content: str):
        """Add a new memory entry."""
        msg = Message(role=role, content=content)
        self.messages.append(msg)
        self._trim()

    def get_messages(self, include_system: bool = False, system_prompt: str = "") -> List[Dict[str, str]]:
        """
        Get messages for LLM consumption.
        """
        payload = [msg.model_dump(include={'role', 'content'})
                   for msg in self.messages]

        if include_system and system_prompt:
            system_msg = {"role": "system", "content": system_prompt}
            return [system_msg] + payload

        return payload

    def clear(self):
        """Clear all active short-term memories."""
        self.messages = []

    def _trim(self):
        """Maintain the sliding window size."""
        if len(self.messages) > self.max_history_len:
            self.messages = self.messages[-self.max_history_len:]
