# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import BaseEvent


class ActionType(str, Enum):
    """Types of actions."""

    SPEAK = "speak"
    CHANNEL_REPLY = "channel_reply"
    EXPRESSION = "expression"
    UI_UPDATE = "ui_update"
    TOOL_USE = "tool_use"


class ActionLevel(str, Enum):
    """Severity level of action, controls processing."""

    REFLEX = "reflex"
    ECHO = "echo"
    COGNITIVE = "cognitive"


class ActionEvent(BaseEvent):
    """Base class for all action events.

    Contains type, level, and optional parameters.
    """

    action_type: ActionType
    level: ActionLevel = ActionLevel.COGNITIVE
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SpeakAction(ActionEvent):
    """Presentation action used for text output."""

    name: str = "action.presentation.speak"
    action_type: ActionType = ActionType.SPEAK
    text: str
    emotion: str = "neutral"


class ChannelReplyAction(ActionEvent):
    """Action representing a reply sent via a channel."""

    name: str = "action.channel.reply"
    action_type: ActionType = ActionType.CHANNEL_REPLY
    text: str
    emotion: str = "neutral"
    vessel_id: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
