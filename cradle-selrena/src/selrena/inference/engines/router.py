"""引擎池路由与工厂（迁移并简化配置依赖）。"""

from typing import Any, Union

from selrena.utils.logger import logger

from .base import BaseBrainBackend


class BrainFactory:
    @staticmethod
    def create(config: Union[Any, Any]) -> BaseBrainBackend:
        # config 可以是任意类型，具体实现由上层负责
        return BrainFactory._create_single(config)

    @staticmethod
    def _create_single(config: Any) -> BaseBrainBackend:
        # 简化的默认策略：使用远程后端
        from .remote import OpenAIRemoteBackend
        return OpenAIRemoteBackend(config)


class HybridBrainRouter(BaseBrainBackend):
    def __init__(self, config: Any):
        super().__init__(config)
        self.soul_config = config
        self._backend: BaseBrainBackend | None = None

    async def initialize(self):
        # 选择提供者逻辑占位
        self._backend = BrainFactory._create_single(self.config)
        await self._backend.initialize()

    async def cleanup(self):
        if self._backend is not None:
            await self._backend.cleanup()
            self._backend = None

    async def generate(self, messages):
        if self._backend is None:
            raise RuntimeError("HybridBrainRouter not initialized")
        return await self._backend.generate(messages)

    async def perceive(self, message):
        if self._backend is None:
            return None
        return await self._backend.perceive(message)

    @property
    def is_multimodal(self) -> bool:
        return self._backend.is_multimodal if self._backend else False
