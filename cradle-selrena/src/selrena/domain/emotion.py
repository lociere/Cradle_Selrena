"""情感领域模型（迁移自 cradle_selrena_core）"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EmotionCategory(Enum):
    """基础情感分类"""
    JOY = "joy"          # 喜悦
    SADNESS = "sadness"  # 悲伤
    ANGER = "anger"      # 愤怒
    FEAR = "fear"        # 恐惧
    SURPRISE = "surprise"  # 惊讶
    DISGUST = "disgust"    # 厌恶
    NEUTRAL = "neutral"    # 中性


@dataclass
class EmotionState:
    """
    情感状态领域模型
    
    Attributes:
        category: 情感分类
        intensity: 强度 (0-1)
        valence: 效价 (-1 到 1，负向到正向)
        arousal: 唤醒度 (0-1，低到高)
        trigger: 触发事件
        timestamp: 时间戳
        decay_rate: 衰减率 (每秒减少的强度)
    """
    category: EmotionCategory = EmotionCategory.NEUTRAL
    intensity: float = 0.0
    valence: float = 0.0
    arousal: float = 0.0
    trigger: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    decay_rate: float = 0.01
    
    def update(self, category: EmotionCategory, intensity: float, 
               valence: Optional[float] = None, 
               arousal: Optional[float] = None,
               trigger: Optional[str] = None):
        """更新情感状态"""
        self.category = category
        self.intensity = max(0.0, min(1.0, intensity))
        if valence is not None:
            self.valence = max(-1.0, min(1.0, valence))
        if arousal is not None:
            self.arousal = max(0.0, min(1.0, arousal))
        if trigger:
            self.trigger = trigger
        self.timestamp = datetime.now()
    
    def decay(self, delta_seconds: float) -> float:
        """
        情感衰减
        
        Args:
            delta_seconds: 经过的秒数
            
        Returns:
            衰减后的强度
        """
        self.intensity = max(0.0, self.intensity - (self.decay_rate * delta_seconds))
        if self.intensity < 0.01:
            self.category = EmotionCategory.NEUTRAL
        return self.intensity
    
    def to_dict(self) -> dict[str, any]:
        """转换为字典"""
        return {
            "category": self.category.value,
            "intensity": self.intensity,
            "valence": self.valence,
            "arousal": self.arousal,
            "trigger": self.trigger,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def describe(self) -> str:
        """人类可读的情感描述"""
        if self.intensity < 0.1:
            return "平静"
        
        intensity_desc = {
            (0, 0.3): "轻微",
            (0.3, 0.6): "中等",
            (0.6, 0.8): "强烈",
            (0.8, 1.0): "极度",
        }
        
        desc = "未知"
        for (low, high), label in intensity_desc.items():
            if low <= self.intensity < high:
                desc = label
                break
        
        return f"{desc}{self.category.value}"
