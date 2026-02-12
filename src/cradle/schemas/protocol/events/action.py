from enum import Enum
from typing import Any, Dict
from pydantic import Field
from .base import BaseEvent

class ActionType(str, Enum):
    """行动类型枚举"""
    SPEAK = "speak"           # 语音表达 (TTS)
    EXPRESSION = "expression" # 表情/身态管理 (Live2D/Avatar)
    UI_UPDATE = "ui_update"   # 界面交互 (Toast, 弹窗等)
    TOOL_USE = "tool_use"     # 工具调用 (API, 脚本, 外部软件)

class ActionLevel(str, Enum):
    """行动认知层级"""
    REFLEX = "reflex"       # 脊髓反射 (最快, 不经 LLM, 如: 立即闭嘴)
    ECHO = "echo"           # 鹦鹉学舌/简单回响 (中速, 简单的逻辑或规则)
    COGNITIVE = "cognitive" # 深度认知 (最慢, 经由 LLM 深思熟虑)

class ActionEvent(BaseEvent):
    """
    行动输出事件 (Output Event)
    
    代表系统决定执行的一个具体动作。
    流向: Mind/Reflex -> EventBus -> Body (Actuators)
    """
    action_type: ActionType = Field(..., description="行动的具体类型")
    level: ActionLevel = Field(ActionLevel.COGNITIVE, description="产生该行动的认知层级")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="执行该行动所需的详细参数")
    
class SpeakAction(ActionEvent):
    """语音表达动作"""
    name: str = "action.presentation.speak"
    action_type: ActionType = ActionType.SPEAK
    text: str = Field(..., description="需要朗读的文本内容")
    emotion: str = Field("neutral", description="朗读时的情感倾向")

class UIActionEvent(ActionEvent):
    """UI 更新动作"""
    name: str = "action.presentation.ui"
    action_type: ActionType = ActionType.UI_UPDATE
