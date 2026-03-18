"""
文件名称：scene_session.py
所属层级：领域层-会话模块
核心作用：管理按 scene_id 隔离的长在线对话会话、历史压缩与并发串行化。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from selrena.domain.memory.short_term_memory import ShortTermMemory


@dataclass(frozen=True)
class ConversationMessage:
    """单条会话消息，仅保留模型推理所需的最小字段。"""

    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationSession:
    """场景级会话状态，负责维护最近消息与压缩摘要。"""

    scene_id: str
    summary_text: str = ""
    _messages: list[ConversationMessage] = field(default_factory=list)

    def append_message(self, role: str, content: str) -> ConversationMessage:
        message = ConversationMessage(role=role, content=content.strip())
        self._messages.append(message)
        return message

    def get_recent_messages(self, limit: int) -> list[ConversationMessage]:
        if limit <= 0:
            return []
        return self._messages[-limit:]

    def compact_history(
        self,
        trigger_count: int,
        keep_recent_count: int,
        max_summary_chars: int,
    ) -> None:
        if trigger_count <= 0 or len(self._messages) <= trigger_count:
            return

        safe_keep_recent = max(1, min(keep_recent_count, trigger_count - 1))
        archive_count = len(self._messages) - safe_keep_recent
        archived_messages = self._messages[:archive_count]
        self._messages = self._messages[archive_count:]

        archived_text = self._format_messages(archived_messages)
        if not archived_text:
            return

        if self.summary_text:
            merged = f"{self.summary_text}\n{archived_text}"
        else:
            merged = archived_text

        if len(merged) > max_summary_chars:
            merged = merged[-max_summary_chars:]
        self.summary_text = merged.strip()

    def clear(self) -> None:
        self.summary_text = ""
        self._messages = []

    def _format_messages(self, messages: list[ConversationMessage]) -> str:
        lines: list[str] = []
        for message in messages:
            content = message.content.replace("\n", " ").strip()
            if not content:
                continue
            timestamp = message.timestamp.isoformat(timespec="seconds")
            lines.append(f"[{timestamp}] {message.role}: {content}")
        return "\n".join(lines)


class SceneSessionRuntime:
    """每个场景的运行时容器：会话态、短期记忆、并发锁。"""

    def __init__(self, scene_id: str, short_term_max_length: int):
        self.scene_id = scene_id
        self.short_term_memory = ShortTermMemory(scene_id=scene_id, max_length=short_term_max_length)
        self.session = ConversationSession(scene_id=scene_id)
        self.lock = asyncio.Lock()

    def clear(self) -> None:
        self.short_term_memory.clear()
        self.session.clear()