# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""人格领域模型（从之前的 cradle_selrena_core 迁移）。

定义了贯穿 AI 逻辑的分层人格结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PersonaLayer(Enum):
    """四个人格层。

    IDENTITY：核心身份（“我是...”）
    VALUES：价值观和信念（“我相信...”）
    BEHAVIOR：行为模式（“我通过...”行动）
    EXPRESSION：表达风格（语气、措辞等）
    """

    IDENTITY = "identity"
    VALUES = "values"
    BEHAVIOR = "behavior"
    EXPRESSION = "expression"


@dataclass
class Persona:
    """人格配置数据。

    属性：
        name: 角色名称
        identity: 核心身份描述
        values: 价值观/信念列表
        behavior_patterns: 行为描述列表
        expression_style: 风格提示（语气、措辞等）
        background: 可选背景故事
        relationships: 重要关系映射
    """

    name: str
    identity: str = ""
    values: list[str] = field(default_factory=list)
    behavior_patterns: list[str] = field(default_factory=list)
    expression_style: dict = field(default_factory=dict)
    background: Optional[str] = None
    relationships: dict = field(default_factory=dict)
