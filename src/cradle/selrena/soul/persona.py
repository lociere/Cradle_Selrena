from datetime import datetime
from typing import Any, Dict, Optional

from cradle.schemas.configs.soul import PersonaConfig


class PersonaManager:
    """人格管理器"""

    def __init__(self, config: PersonaConfig):
        self.config = config

    def build_system_prompt(self) -> Dict[str, str]:
        """构建 System Prompt"""

        # 直接复用 Schema 中定义的模板生成逻辑，确保 YAML 配置完整生效
        # 包括 name, role, emotion_control, likes, taboos, etc.
        base_prompt = self.config.get_system_prompt()
        
        # 追加动态时间，增强时间感知
        time_block = f"\n\n[Current Time]\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return {
            "role": "system",
            "content": base_prompt + time_block
        }
