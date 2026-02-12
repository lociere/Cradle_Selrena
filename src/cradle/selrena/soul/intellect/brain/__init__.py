from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Optional
from cradle.schemas.configs.soul import LLMConfig, SoulConfig
from cradle.utils.logger import logger

class BaseBrainBackend(ABC):
    """
    大脑后端接口 (Abstract Strategy)
    定义了任何一种 LLM 驱动（无论是云端还是本地）必须实现的方法。
    """
    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def initialize(self):
        """异步初始化 (例如加载模型、建立连接)"""
        pass

    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """
        核心思考方法
        :param messages: OpenAI 格式的历史消息列表 [{"role": "user", "content": "..."}]
        :return: 生成的文本回复
        """
        pass

    async def cleanup(self):
        """清理资源"""
        pass

class BrainFactory:
    """大脑工厂：根据配置生产具体的后端实例"""
    
    @staticmethod
    def create(config: Union[LLMConfig, SoulConfig]) -> "BaseBrainBackend":
        # 如果传入的是完整的 SoulConfig，说明我们要启用混合调度 (Hybrid Brain)
        if isinstance(config, SoulConfig):
            logger.debug("🧠 BrainFactory: 正在装配 [混合动力] 神经中枢 (Hybrid Brain)...")
            return HybridBrainRouter(config)
            
        # 传统的单一 Config 模式 (保持兼容)
        return BrainFactory._create_single(config)

    @staticmethod
    def _create_single(config: LLMConfig) -> "BaseBrainBackend":
        if config.provider == "local_embedded":
            from .embedded import LlamaCppEmbeddedBackend
            logger.debug("🧠 BrainFactory: 正在装配 [本地内嵌] 神经后端...")
            return LlamaCppEmbeddedBackend(config)
        else:
            # 默认为 OpenAI (兼容模式)
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
        super().__init__(soul_config.llm) # 仅仅是为了满足基类签名
        self.soul_config = soul_config
        self.strategy = soul_config.strategy
        
        self._local_brain: Optional[BaseBrainBackend] = None
        self._cloud_brain: Optional[BaseBrainBackend] = None
        
    async def initialize(self):
        """懒加载策略：虽然是 Hybrid，但只初始化当前策略需要的"""
        # 1. 总是初始化本地大脑 (因为它是最后的防线)
        local_cfg = self.soul_config.providers.get(self.soul_config.active_provider)
        # 如果 active 本身就是云端，那 local_brain 就是云端，这没问题
        if local_cfg:
            self._local_brain = BrainFactory._create_single(local_cfg)
            await self._local_brain.initialize()
            
        # 2. 如果开启了 API 策略，且 API 提供商存在，预加载云端大脑
        if self.strategy.enabled:
            api_cfg = self.soul_config.providers.get(self.strategy.api_provider)
            if api_cfg:
                self._cloud_brain = BrainFactory._create_single(api_cfg)
                await self._cloud_brain.initialize()

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """能够自动降级的生成逻辑"""
        
        # 1. 检查是否应该使用 Cloud API
        use_cloud = self.strategy.enabled
        
        # TODO: 这里可以拓展：检查 module_map，或者检查消息是否包含“复杂任务”标记
        
        if use_cloud and self._cloud_brain:
            try:
                # 尝试云端生成
                return await self._cloud_brain.generate(messages)
            except Exception as e:
                logger.warning(f"[HybridBrain] 云端 API 调用失败: {e}")
                if self.strategy.fallback_to_local:
                    logger.info("[HybridBrain] 正在自动降级到本地模型...")
                    # Fallthrough to local
                else:
                    raise e # 不降级则直接抛出
        
        # 2. 本地生成 (Default / Fallback)
        if self._local_brain:
            return await self._local_brain.generate(messages)
            
        return "Error: No brain backend available."
        
    async def cleanup(self):
        if self._local_brain:
            await self._local_brain.cleanup()
        if self._cloud_brain:
            await self._cloud_brain.cleanup()
