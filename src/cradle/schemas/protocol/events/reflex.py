from enum import Enum
from pydantic import Field
from .base import BaseEvent

class ReflexType(str, Enum):
    """反射类型枚举"""
    HALT = "halt"       # 紧急中断 (Immediate Stop) - 用于停止一切正在进行的动作 (说话、工具执行)
    MUTE = "mute"       # 静音 (Mute) - 仅停止发声，不一定停止思考
    ENGAGED = "engaged" # 接触状态 (User Engaged) - 用户正在输入/说话，系统应保持专注或做非语言反馈

class ReflexSignal(BaseEvent):
    """
    脊髓反射信号 (Reflex Signal) - Layer 1
    
    这类信号通常具有最高优先级，用于处理生存本能、打断和快速反馈。
    接收者通常是底层的 Driver (如 Player, Motor)。
    """
    name: str = "signal.reflex"
    reflex_type: ReflexType = Field(..., description="反射的具体类型")
