# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""情绪领域模型（从 cradle_selrena_core 迁移）。"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EmotionCategory(Enum):
    """基础情绪类别。"""

    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"


@dataclass
class EmotionState:
    """情绪状态的数据结构。

    属性：
        category: 情绪类别
        intensity: 强度，0-1
        valence: 价值感，-1 到 1
        arousal: 唤醒度，0-1
        trigger: 可选的触发事件
        timestamp: 记录时间
        decay_rate: 衰减速率（每秒）
    """

    category: EmotionCategory = EmotionCategory.NEUTRAL
    intensity: float = 0.0
    valence: float = 0.0
    arousal: float = 0.0
    trigger: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    decay_rate: float = 0.01
