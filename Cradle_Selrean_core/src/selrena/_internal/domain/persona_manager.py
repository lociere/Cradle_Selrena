# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from datetime import datetime

from typing import Any


from .persona import Persona


class PersonaManager:
    """简单的人格构建助手类。

    该类属于领域层逻辑，因此不作为独立模块，与 Persona 数据模型
    位于同一包中。负责生成用于系统提示的文本，一般包含名称、
    特征和当前时间，供 LLM 作为上下文参考。
    """

    def __init__(self, persona: Persona) -> None:

        self.persona = persona

    def build_system_prompt(self) -> str:
        """构建包含名称、特征和当前时间的纯文本系统提示。"""

        parts: list[str] = []

        if self.persona.name:

            parts.append(f"名称：{self.persona.name}")

        if self.persona.identity:

            parts.append(f"身份：{self.persona.identity}")

        if self.persona.values:

            parts.append(f"性格/价值观：{', '.join(self.persona.values)}")

        prompt = "\n".join(parts)

        prompt += "\n\n[Current Time]\n" + datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return prompt
