# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from pathlib import Path
from typing import Optional

from selrena._internal.domain.persona import Persona
from selrena._internal.ports.persona_port import PersonaPort
from loguru import logger


class PersonaAdapter(PersonaPort):
    """基于 YAML 文件的人格配置适配器。

    默认读取 `configs/persona` 目录；也可在构造时传入
    自定义路径。提供加载与保存功能。
    """

    def __init__(self, config_path: Path | None = None):
        from selrena._internal.utils.io.path import ProjectPath

        self.config_path = config_path or (ProjectPath.CONFIGS_DIR / "persona")
        self.config_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"PersonaAdapter 初始化于 {self.config_path}")

    async def load_persona(self, name: str) -> Persona:
        """从指定名称的 YAML 文件中读取人格配置。"""
        import yaml

        persona_file = self.config_path / f"{name}.yaml"
        if not persona_file.exists():
            raise FileNotFoundError(f"persona config not found: {persona_file}")
        content = await asyncio.to_thread(persona_file.read_text, encoding="utf-8")
        data = yaml.safe_load(content)
        return Persona(
            name=data.get("name", name),
            identity=data.get("identity", ""),
            values=data.get("values", []),
            behavior_patterns=data.get("behavior_patterns", []),
            expression_style=data.get("expression_style", {}),
            background=data.get("background"),
            relationships=data.get("relationships", {}),
        )

    async def save_persona(self, persona: Persona) -> None:
        """将 Persona 对象写回到 YAML 文件。"""
        import yaml

        persona_file = self.config_path / f"{persona.name}.yaml"
        data = {
            "name": persona.name,
            "identity": persona.identity,
            "values": persona.values,
            "behavior_patterns": persona.behavior_patterns,
            "expression_style": persona.expression_style,
            "background": persona.background,
            "relationships": persona.relationships,
        }
        content = yaml.dump(data, allow_unicode=True, default_flow_style=False)
        await asyncio.to_thread(persona_file.write_text, content, encoding="utf-8")
