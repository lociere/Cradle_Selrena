"""Adapters exports during migration."""

from .zmq.event_bus import ZMQEventBusAdapter, ZMQConfig

import asyncio
from pathlib import Path
from typing import Optional

from selrena.domain.memory import Memory
from selrena.domain.persona import Persona
from selrena.ports import KernelPort, MemoryPort, Personaport
from selrena.utils.logger import logger


class KernelAdapter(KernelPort):
    """
    ????? - ???? TS ??
    """
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        logger.info("KernelAdapter ????? (TS ??)")

    async def send_message(self, text: str, emotion: Optional[str] = None) -> None:
        from selrena.schemas.events import SpeakAction
        action = SpeakAction(
            source="AI",
            text=text,
            emotion=emotion or "neutral"
        )
        if self.event_bus:
            await self.event_bus.publish(action)
            logger.debug(f"消息已通过事件总线发送：{text[:50]}...")
        else:
            # 没有事件总线就直接打印，保证本地运行时有输出
            logger.info(f"[KernelAdapter] {text}")
            print(f"AI 输出：{text}")

    async def play_audio(self, audio_path: str) -> None:
        logger.info(f"?????{audio_path}")

    async def capture_screen(self) -> str:
        logger.info("??????")
        return ""

    async def read_file(self, path: str) -> str:
        return await asyncio.to_thread(Path(path).read_text, encoding="utf-8")

    async def write_file(self, path: str, content: str) -> None:
        await asyncio.to_thread(Path(path).write_text, content, encoding="utf-8")


class MemoryAdapter(MemoryPort):
    """??????? - ????????"""
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"MemoryAdapter ??????{storage_path}")

    async def save_memory(self, memory: Memory) -> None:
        import json
        memory_file = self.storage_path / f"{memory.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        content = json.dumps(memory.to_dict(), ensure_ascii=False, indent=2)
        await asyncio.to_thread(memory_file.write_text, content, encoding="utf-8")

    async def retrieve_memories(self, query: str, n_results: int = 5) -> list[Memory]:
        memories = []
        for f in self.storage_path.glob("*.json"):
            import json
            content = await asyncio.to_thread(f.read_text, encoding="utf-8")
            data = json.loads(content)
            memory = Memory.from_dict(data)
            if query.lower() in memory.content.lower():
                memories.append(memory)
        return memories[:n_results]

    async def delete_memory(self, memory_id: str) -> None:
        memory_file = self.storage_path / f"{memory_id}.json"
        if memory_file.exists():
            await asyncio.to_thread(memory_file.unlink)


class PersonaAdapter(Personaport):
    """???????"""
    def __init__(self, config_path: Path):
        self.config_path = config_path
        logger.info(f"PersonaAdapter ??????{config_path}")

    async def load_persona(self, name: str) -> Persona:
        import yaml
        persona_file = self.config_path / f"{name}.yaml"
        if not persona_file.exists():
            raise FileNotFoundError(f"????????{persona_file}")
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

__all__: list[str] = ["ZMQEventBusAdapter", "ZMQConfig", "KernelAdapter", "MemoryAdapter", "PersonaAdapter"]
