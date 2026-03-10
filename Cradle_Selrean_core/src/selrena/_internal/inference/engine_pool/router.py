# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
from typing import Any

from .base import BaseBrainBackend


class BrainFactory:
    """Simple factory that returns stub backend instances by name."""

    def create(self, name: str) -> BaseBrainBackend:
        # always return a basic stub implementation
        class Stub(BaseBrainBackend):
            async def generate(self, prompt: str) -> str:
                return f"[brain:{name}] {prompt[:20]}..."

        return Stub()


class HybridBrainRouter:
    """Example router that picks a backend based on criteria."""

    def __init__(self, factory: BrainFactory):
        self.factory = factory

    async def route(self, is_visual: bool = False) -> BaseBrainBackend:
        name = "vision" if is_visual else "text"
        return self.factory.create(name)
