from typing import List, Dict, Union, Optional
from cradle.schemas.configs.soul import LLMConfig, SoulConfig
from cradle.utils.logger import logger
from .base import BaseBrainBackend


class BrainFactory:
    """大脑工厂：根据配置生产具体的后端实例"""

    @staticmethod
    def create(config: Union[LLMConfig, SoulConfig]) -> "BaseBrainBackend":
        if isinstance(config, SoulConfig):
            logger.debug("🧠 BrainFactory: 正在装配 [混合动力] 神经中枢 (Hybrid Brain)...")
            return HybridBrainRouter(config)

        return BrainFactory._create_single(config)

    @staticmethod
    def _create_single(config: LLMConfig) -> "BaseBrainBackend":
        if config.provider == "local_embedded":
            from .embedded import LlamaCppEmbeddedBackend

            logger.debug("🧠 BrainFactory: 正在装配 [本地内嵌] 神经后端...")
            return LlamaCppEmbeddedBackend(config)

        from .remote import OpenAIRemoteBackend

        logger.debug(f"🧠 BrainFactory: 正在装配 [云端 API] 神经后端 ({config.provider})...")
        return OpenAIRemoteBackend(config)


class HybridBrainRouter(BaseBrainBackend):
    """
    混合动力大脑路由 (Smart Router)
    职责:
    1. 持有多个后端实例 (Local + API)
    2. 根据 Strategy 策略动态转发请求
    3. 处理 API 失败后的自动降级 (Failover)
    """

    def __init__(self, soul_config: SoulConfig):
        super().__init__(soul_config.llm)
        self.soul_config = soul_config
        self.strategy = soul_config.strategy

        self._local_brain: Optional[BaseBrainBackend] = None
        self._cloud_brains: Dict[str, BaseBrainBackend] = {}

    @staticmethod
    def _is_visual_request(messages: List[Dict[str, str]]) -> bool:
        if not messages:
            return False

        for msg in reversed(messages):
            role = str(msg.get("role", ""))
            if role != "user":
                continue
            content = str(msg.get("content", ""))
            if not content:
                continue
            text = content.lower()
            if "【视觉输入】" in content:
                return True
            visual_markers = (
                "ocr", "截图", "图像", "图片", "image", "vision", "photo", "看图", "识图"
            )
            if any(marker in text for marker in visual_markers):
                return True
            return False
        return False

    async def _ensure_cloud_brain(self, provider_key: str) -> Optional[BaseBrainBackend]:
        if provider_key in self._cloud_brains:
            return self._cloud_brains[provider_key]

        cfg = self.soul_config.providers.get(provider_key)
        if not cfg:
            logger.warning(f"[HybridBrain] provider '{provider_key}' 未配置，无法初始化云端后端。")
            return None

        backend = BrainFactory._create_single(cfg)
        await backend.initialize()
        self._cloud_brains[provider_key] = backend
        return backend

    def _pick_provider_for_messages(self, messages: List[Dict[str, str]]) -> str:
        if self._is_visual_request(messages):
            return self.strategy.module_map.get("vision", self.strategy.api_provider)
        return self.strategy.module_map.get("complex_logic", self.strategy.api_provider)

    async def initialize(self):
        local_cfg = self.soul_config.providers.get(self.soul_config.active_provider)
        if local_cfg:
            self._local_brain = BrainFactory._create_single(local_cfg)
            await self._local_brain.initialize()

        if self.strategy.enabled:
            await self._ensure_cloud_brain(self.strategy.api_provider)

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        use_cloud = self.strategy.enabled

        if use_cloud:
            provider_key = self._pick_provider_for_messages(messages)
            cloud_backend = await self._ensure_cloud_brain(provider_key)
        else:
            cloud_backend = None

        if use_cloud and cloud_backend:
            try:
                return await cloud_backend.generate(messages)
            except Exception as e:
                logger.warning(f"[HybridBrain] 云端 API 调用失败: {e}")
                if self.strategy.fallback_to_local:
                    logger.info("[HybridBrain] 正在自动降级到本地模型...")
                else:
                    raise e

        if self._local_brain:
            return await self._local_brain.generate(messages)

        return "Error: No brain backend available."

    async def cleanup(self):
        if self._local_brain:
            await self._local_brain.cleanup()
        for backend in self._cloud_brains.values():
            await backend.cleanup()
