"""人设领域模型 - 四层人格结构（迁移自 cradle_selrena_core）"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PersonaLayer(Enum):
    """四层人格层级"""
    IDENTITY = "identity"  # 核心身份：我是谁
    VALUES = "values"      # 价值观：我相信什么
    BEHAVIOR = "behavior"  # 行为模式：我如何行动
    EXPRESSION = "expression"  # 表达方式：我如何说话


@dataclass
class Persona:
    """
    人设领域模型
    
    Attributes:
        name: 角色名称
        identity: 核心身份描述
        values: 价值观列表
        behavior_patterns: 行为模式描述
        expression_style: 表达风格（语气、口头禅等）
        background: 背景故事
        relationships: 重要关系
    """
    name: str
    identity: str
    values: list[str] = field(default_factory=list)
    behavior_patterns: list[str] = field(default_factory=list)
    expression_style: dict[str, str] = field(default_factory=dict)
    background: Optional[str] = None
    relationships: dict[str, str] = field(default_factory=dict)
    
    def get_layer(self, layer: PersonaLayer) -> str:
        """获取特定层级的人设信息"""
        mapping = {
            PersonaLayer.IDENTITY: self.identity,
            PersonaLayer.VALUES: "\n".join(self.values),
            PersonaLayer.BEHAVIOR: "\n".join(self.behavior_patterns),
            PersonaLayer.EXPRESSION: str(self.expression_style),
        }
        return mapping.get(layer, "")
    
    def to_prompt(self) -> str:
        """生成系统提示词"""
        parts = [
            f"# 角色设定：{self.name}",
            f"## 核心身份\n{self.identity}",
            f"## 价值观\n" + "\n".join(f"- {v}" for v in self.values),
            f"## 行为模式\n" + "\n".join(f"- {b}" for b in self.behavior_patterns),
            f"## 表达风格\n{self.expression_style.get('tone', '自然友好')}",
        ]
        if self.background:
            parts.append(f"## 背景故事\n{self.background}")
        return "\n\n".join(parts)
