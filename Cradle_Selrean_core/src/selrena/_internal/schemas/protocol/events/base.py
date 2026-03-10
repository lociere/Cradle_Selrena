# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_EVENT_NAME_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


class BaseEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str | None = None
    timestamp: float = Field(default_factory=time.time)
    source: str = Field(default="unknown")
    name: str = Field(...)
    payload: Any = None

    # pydantic v2 configuration
    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "ignore",
    }

    @classmethod
    def normalize_name(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise ValueError("event name cannot be empty")
        if normalized.startswith(".") or normalized.endswith(".") or ".." in normalized:
            raise ValueError("invalid event name format")
        if any(ch not in _EVENT_NAME_ALLOWED_CHARS for ch in normalized):
            raise ValueError("event name contains invalid characters")
        return normalized

    def child_event(
        self, *, name: str, source: str, payload: Any = None, **extra
    ) -> "BaseEvent":
        return BaseEvent(
            name=self.normalize_name(name),
            source=source,
            payload=payload,
            trace_id=self.trace_id,
            parent_id=self.id,
            **extra,
        )
