import asyncio
import re
from typing import Any, Dict, List, Optional, Union

from cradle.schemas.configs.soul import LLMConfig, SoulConfig
from cradle.schemas.domain.chat import Message as ChatMessage
from cradle.utils.logger import logger

from .base import BaseBrainBackend
from .utils.prompt_builder import PromptBuilder
from .utils.sanitizer import PayloadSanitizer


class BrainFactory:
    """
    大脑工厂 (Brain Factory)。
    
    负责根据配置组装具体的 AI 后端实例 (Backend Instance)。
    它是一个静态工厂，屏蔽了后端（本地 GGUF / 云端 API）的创建细节。
    """

    @staticmethod
    def create(config: Union[LLMConfig, SoulConfig]) -> "BaseBrainBackend":
        """
        创建大脑实例。
        
        Args:
            config: 若传入 SoulConfig，则创建全功能的混合路由 (HybridBrainRouter)；
                   若传入 LLMConfig，则创建单一后端 (如 OpenAIRemoteBackend)。
        """
        if isinstance(config, SoulConfig):
            logger.debug(" BrainFactory: 正在装配 [混合动力] 神经中枢 (Hybrid Brain)...")
            return HybridBrainRouter(config)

        return BrainFactory._create_single(config)

    @staticmethod
    def _create_single(config: LLMConfig) -> "BaseBrainBackend":
        if config.provider == "local_embedded":
            # 延迟导入以避免循环依赖
            from .embedded import LlamaCppEmbeddedBackend
            return LlamaCppEmbeddedBackend(config)

        from .remote import OpenAIRemoteBackend
        return OpenAIRemoteBackend(config)


class HybridBrainRouter(BaseBrainBackend):
    """
    混合动力大脑路由 (Hybrid Brain Router)。
    
    这是 SELRENA 的核心思考调度器。它不直接产生思想，而是作为“额叶指挥官”，
    根据任务类型（文本、视觉、复杂逻辑）将请求分发给最擅长的模型后端。
    
    核心能力：
    1. **混合编排 (Hybrid Orchestration)**: 支持同时使用本地模型（处理隐私敏感/低延迟任务）和云端模型（处理高智商/视觉任务）。
    2. **自动容灾 (Auto Fallback)**: 当云端主力模型挂掉时，自动切回本地模型维持最低限度的意识。
    3. **视觉增强 (Vision Flow)**: 自动识别视觉请求，调用视觉模型（如 Qwen-VL）生成描述，再注入给思考模型。
    """

    # --- Initialization ---

    def __init__(self, soul_config: SoulConfig):
        super().__init__(soul_config.llm)
        self.soul_config = soul_config
        self.strategy = soul_config.strategy

        # 所有已激活的后端实例池 (name -> backend)
        self._active_backends: Dict[str, BaseBrainBackend] = {}
        
        # 专用的本地回退后端引用 (指向 _active_backends 中的某个实例)
        self._fallback_backend: Optional[BaseBrainBackend] = None

    async def initialize(self):
        """
        初始化路由器。
        预加载核心模型和回退模型，确保系统启动时关键路径可用。
        """
        # 1. 预加载核心思考模型 (Core Provider)
        core_name = self._core_provider_name
        logger.info(f"[HybridBrain] 初始化核心思考后端: {core_name}")
        await self._get_or_create_backend(core_name)

        # 2. 预加载本地回退模型 (Fallback Provider)
        if self.strategy.fallback_to_local:
            local_provider_name = "local_embedded"
            
            # [Optimization] 避免重复加载
            # 如果核心模型本身就是 local_embedded，直接复用引用，节省显存
            if core_name == local_provider_name:
                logger.info("[HybridBrain] 核心模型即为本地模型，复用实例作为 Fallback。")
                self._fallback_backend = self._active_backends.get(core_name)
            else:
                # 否则，尝试独立加载本地模型
                if local_provider_name in self.soul_config.providers:
                    logger.info(f"[HybridBrain] 初始化备用本地后端: {local_provider_name}")
                    self._fallback_backend = await self._get_or_create_backend(local_provider_name)
                else:
                    logger.warning("[HybridBrain] 策略要求 fallback_to_local，但未找到 local_embedded 配置！")

    async def cleanup(self):
        """释放所有后端资源"""
        for name, backend in self._active_backends.items():
            await backend.cleanup()
        self._active_backends.clear()
        self._fallback_backend = None

    # --- Properties ---

    @property
    def _core_provider_name(self) -> str:
        """
        获取当前策略下的主力思考模型 (The Brain)。
        逻辑简化：核心思考者始终由 strategy.core_provider 定义。
        """
        return self.strategy.core_provider

    @property
    def _vision_provider_name(self) -> str:
        """
        获取当前策略下的视觉模型 (The Eyes)。
        Logic:
        - Single Multimodal: 视觉由核心大脑全权负责。
        - Split Tasks: 视觉由专门的 Vision Expert 负责 (如果未配置则回退到核心)。
        """
        if self.strategy.routing_mode == "single_multimodal":
            return self.strategy.core_provider
        
        # split_tasks 模式下，获取 'vision' 专家，缺省用 core_provider
        return self.strategy.module_map.get(
            "vision", self.strategy.core_provider)

    # --- Public API ---

    async def generate(self, messages: List[ChatMessage]) -> str:
        """
        [Master Routing]
        根据策略配置，选择 'Single Multimodal' 或 'Split Tasks' 执行路径。
        """
        # [Layer 0] 入口标准化
        normalized_messages = PayloadSanitizer.normalize_messages(messages)
        
        mode = self.strategy.routing_mode
        core_provider = self._core_provider_name
        is_visual = PayloadSanitizer.is_visual_request(normalized_messages)

        logger.debug(
            f"[HybridBrain] Routing Decision: mode={mode}, has_visual={is_visual}, core={core_provider}")

        try:
            # === Path 1: Single Multimodal (All-in-One) ===
            # 将所有任务（文本/视觉）直接交给一个强大的多模态模型
            if mode == "single_multimodal":
                return await self._execute_single_multimodal(normalized_messages, core_provider)

            # === Path 2: Split Tasks (Expert Assembly) ===
            # 视觉任务走 Vision Expert，文本任务走 Core Logic
            if is_visual:
                return await self._execute_split_tasks_pipeline(normalized_messages, core_provider)

            # Pure Text Flow
            return await self._execute_pure_text_flow(normalized_messages, core_provider)

        except Exception as e:
            logger.error(
                f"[HybridBrain] Primary inference failed: {e}",
                exc_info=True)
            return await self._execute_fallback(messages)

    # --- Strategy Implementations ---

    async def _execute_single_multimodal(self, messages: List[ChatMessage], provider_name: str) -> str:
        """策略一：单模型全能模式 (Direct Relay)"""
        backend = await self._get_or_create_backend(provider_name)
        if not backend:
            raise ValueError(f"Core backend '{provider_name}' not configured.")
        
        # 直接转发原始多模态消息
        return await backend.generate(messages)

    async def _execute_split_tasks_pipeline(self, messages: List[ChatMessage], core_provider_name: str) -> str:
        """
        策略二：专家分工模式 (Pipeline processing)
        Step 1: Perception (Vision Expert) -> Description
        Step 2: Cognition (Core Logic) -> Final Response
        """
        vision_provider_name = self._vision_provider_name
        vision_backend = await self._get_or_create_backend(vision_provider_name)
        core_backend = await self._get_or_create_backend(core_provider_name)

        if not core_backend:
            raise ValueError("Core logic backend missing")

        # 1. Perception Logic
        # 如果视觉专家不可用，尝试让核心模型自己处理（如果核心支持）
        if not vision_backend:
            logger.warning(f"[HybridBrain] Vision expert '{vision_provider_name}' missing.")
            if getattr(core_backend, "is_multimodal", False):
                 logger.info(f"[HybridBrain] Fallback to Core Multimodal capability.")
                 return await core_backend.generate(messages)
            else:
                 # 核心也不支持，只能降级为纯文本
                 logger.warning("[HybridBrain] Vision skipped (No capable model).")
                 return await core_backend.generate(PayloadSanitizer.sanitize_for_text_core(messages))

        # 2. Vision Interpretation (Transcribe Image to Text)
        try:
            logger.debug(f"[HybridBrain] Invoking Vision Expert ({vision_provider_name}) for transcription...")
            vision_summary = await self._transcribe_visual_content(messages, vision_backend)
            if vision_summary:
                logger.debug(f"=========== [Vision Expert Report] ===========\n{vision_summary}\n==============================================")
        except Exception as e:
            logger.warning(f"[HybridBrain] Vision transcription failed: {e}")
            # Fallback: Core takes over if multimodal
            if getattr(core_backend, "is_multimodal", False):
                 return await core_backend.generate(messages)
            
            # [User Request] 视觉失败时直接忽略，不通过错误提示干扰对话
            logger.info("[HybridBrain] Vision failed. Dropping visual context silently.")
            vision_summary = ""

        # 3. Cognitive Processing (Inject Description into Context)
        logger.debug(f"[HybridBrain] Relaying transcribed context to Core ({core_provider_name})...")
        handoff_messages = PayloadSanitizer.sanitize_for_text_core(messages, vision_summary)
        
        return await core_backend.generate(handoff_messages)

    async def _execute_pure_text_flow(self, messages: List[ChatMessage], provider_name: str) -> str:
        """纯文本处理流"""
        backend = await self._get_or_create_backend(provider_name)
        if not backend:
            raise ValueError(f"Backend '{provider_name}' missing.")
        
        # 即使是纯文本流，也可以进行一次清理以防万一
        clean_messages = PayloadSanitizer.sanitize_for_text_core(messages)
        return await backend.generate(clean_messages)

    async def _execute_fallback(self, messages: List[ChatMessage]) -> str:
        """执行容灾回退"""
        if self._fallback_backend:
            logger.warning(f"[HybridBrain] Switching to Fallback Backend...")
            try:
                # Fallback backend is assumed to be text-only or limited
                pure_messages = PayloadSanitizer.sanitize_for_text_core(messages)
                return await self._fallback_backend.generate(pure_messages)
            except Exception as local_err:
                logger.error(f"[HybridBrain] Fallback failed: {local_err}")

        return PromptBuilder.build_fallback_message("generic")

    # --- Helpers ---

    async def _transcribe_visual_content(self, messages: List[ChatMessage], vision_backend: BaseBrainBackend) -> str:
        """调用视觉后台进行转录"""
        # 提取包含图片的最后一条消息进行专门处理
        # TODO: Future optimization: handle multi-image history
        last_user_msg_list = PayloadSanitizer.extract_last_vision_msg(messages)
        
        if not last_user_msg_list:
            return ""

        # 构建视觉提取专用的 Prompt
        vision_prompt_messages = PromptBuilder.build_vision_extraction_prompt(last_user_msg_list[0])
        
        return await vision_backend.generate(vision_prompt_messages)

    async def _get_or_create_backend(
            self, provider_key: str) -> Optional[BaseBrainBackend]:
        """
        获取或创建后端实例（懒加载模式）。
        
        Args:
            provider_key: soul_config.providers 中的 key (如 'deepseek', 'local_embedded')
        """
        # 1. 查缓存
        if provider_key in self._active_backends:
            return self._active_backends[provider_key]

        # 2. 查配置
        cfg = self.soul_config.providers.get(provider_key)
        if not cfg:
            logger.warning(
                f"[HybridBrain] Provider config for '{provider_key}' not found in soul.yaml")
            return None

        # 3. 实例化并初始化
        logger.debug(f"[HybridBrain] Lazy loading backend: {provider_key}...")
        try:
            backend = BrainFactory._create_single(cfg)
            await backend.initialize()
            self._active_backends[provider_key] = backend
            return backend
        except Exception as e:
            logger.error(f"[HybridBrain] Failed to initialize backend '{provider_key}': {e}")
            return None
