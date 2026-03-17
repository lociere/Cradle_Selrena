"""
文件名称：container.py
所属层级：基础设施层
核心作用：依赖注入容器，管理所有单例实例，解决循环依赖问题
设计原则：
1. 单例模式，所有核心实例统一管理
2. 解决循环依赖问题，按依赖顺序初始化
3. 所有依赖通过构造函数注入，不使用硬编码导入
4. 严格遵循分层边界，仅在根目录初始化时调用
"""
from typing import Final
from selrena.core.config import GlobalAIConfig
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.inference.llm_engine import LLMEngine
from selrena.inference.multimodal_router import MultimodalRouter
from selrena.application.chat_use_case import ChatUseCase
from selrena.application.active_thought_use_case import ActiveThoughtUseCase, ActiveThoughtInput
from selrena.application.agent_plan_use_case import AgentPlanUseCase, AgentPlanInput
from selrena.application.memory_sync_use_case import MemorySyncUseCase
from selrena.adapters.outbound.kernel_bridge import KernelBridge
from selrena.adapters.inbound.kernel_event_adapter import KernelEventInboundAdapter
from selrena.adapters.outbound.kernel_event_adapter import KernelEventOutboundAdapter
from selrena.core.event_bus import DomainEventBus
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("container")


class DIContainer:
    """
    依赖注入容器，单例模式
    核心作用：统一管理所有核心实例，解决循环依赖，按正确顺序初始化
    """
    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._initialized: bool = False
        # 所有实例存储
        self._instances: dict[str, object] = {}

    def init(self, config: GlobalAIConfig) -> None:
        """
        初始化容器，按依赖顺序创建所有实例
        参数：
            config: 内核注入的全局冻结配置
        规范：按「基础设施→领域层→推理层→应用层→适配器层→桥接层」的顺序初始化
        """
        if self._initialized:
            logger.warning("容器已初始化，无需重复初始化")
            return

        logger.info("依赖注入容器开始初始化")

        # ======================================
        # 1. 基础设施层实例
        # ======================================
        event_bus = DomainEventBus()
        self._instances["event_bus"] = event_bus

        kernel_bridge = KernelBridge()
        self._instances["kernel_bridge"] = kernel_bridge

        # ======================================
        # 2. 领域层核心实例：全局自我实体（灵魂根节点）
        # ======================================
        self_entity = SelrenaSelfEntity(
            persona_config=config.persona,
            inference_config=config.inference
        )
        self._instances["self_entity"] = self_entity

        # 初始化人设注入器
        self_entity.persona_injector.init(
            persona_config=config.persona,
            inject_mode="prompt"  # 可通过配置修改
        )
        logger.info("全局自我实体初始化完成")

        # ======================================
        # 3. 推理层实例
        # ======================================
        llm_engine = LLMEngine(self_entity=self_entity, llm_config=config.llm)
        self._instances["llm_engine"] = llm_engine

        multimodal_router = MultimodalRouter(inference_config=config.inference)
        self._instances["multimodal_router"] = multimodal_router

        # ======================================
        # 4. 应用层用例实例
        # ======================================
        chat_use_case = ChatUseCase(
            self_entity=self_entity,
            llm_engine=llm_engine,
            multimodal_router=multimodal_router,
        )
        self._instances["chat_use_case"] = chat_use_case

        active_thought_use_case = ActiveThoughtUseCase(
            self_entity=self_entity
        )
        self._instances["active_thought_use_case"] = active_thought_use_case

        agent_plan_use_case = AgentPlanUseCase(self_entity=self_entity)
        self._instances["agent_plan_use_case"] = agent_plan_use_case

        # ======================================
        # 5. 适配器层实例
        # ======================================
        # 入站适配器
        inbound_adapter = KernelEventInboundAdapter(
            self_entity=self_entity,
            chat_use_case=chat_use_case,
            active_thought_use_case=active_thought_use_case,
            agent_plan_use_case=agent_plan_use_case,
        )
        self._instances["inbound_adapter"] = inbound_adapter

        # 出站适配器
        outbound_adapter = KernelEventOutboundAdapter(
            kernel_bridge=kernel_bridge
        )
        self._instances["outbound_adapter"] = outbound_adapter

        memory_sync_use_case = MemorySyncUseCase(kernel_event_port=outbound_adapter)
        self._instances["memory_sync_use_case"] = memory_sync_use_case

        # ======================================
        # 6. 注册事件处理器
        # ======================================
        # 注册记忆同步事件处理器
        from selrena.domain.memory.long_term_memory import MemorySyncEvent
        from selrena.domain.memory.short_term_memory import ShortTermMemorySyncEvent
        event_bus.subscribe(MemorySyncEvent, memory_sync_use_case.on_long_term_memory_sync)
        event_bus.subscribe(ShortTermMemorySyncEvent, memory_sync_use_case.on_short_term_memory_sync)

        # 注册内核消息处理器
        kernel_bridge.register_handler("perception_message", lambda msg: inbound_adapter.on_perception_message(msg))
        kernel_bridge.register_handler("life_heartbeat", lambda msg: inbound_adapter.on_life_heartbeat(
            ActiveThoughtInput(
                trace_id=msg["trace_id"],
                attention_mode=msg.get("payload", {}).get("attention_mode", "ambient")
            )
        ))
        kernel_bridge.register_handler(
            "memory_init",
            lambda msg: inbound_adapter.on_memory_init(msg.get("payload", {}).get("memories", msg.get("memories", [])))
        )
        kernel_bridge.register_handler("knowledge_init", lambda msg: inbound_adapter.on_knowledge_init(
            msg.get("payload", {}).get("persona_knowledge", msg.get("persona_knowledge", [])),
            msg.get("payload", {}).get("general_knowledge", msg.get("general_knowledge", []))
        ))
        kernel_bridge.register_handler("heartbeat", lambda _msg: self._handle_heartbeat())

        kernel_bridge.register_handler("agent_plan", lambda msg: inbound_adapter.on_agent_plan(
            AgentPlanInput(
                user_goal=msg.get("payload", {}).get("user_goal", msg.get("user_goal", "")),
                scene_id=msg.get("payload", {}).get("scene_id", msg.get("scene_id", "default")),
                trace_id=msg["trace_id"],
            )
        ))

        # 配置初始化处理：内核会通过 config_init 请求注入配置（用于确认通信链路正常运行）
        kernel_bridge.register_handler("config_init", lambda msg: self._handle_config_init(msg))

        # 标记为已初始化
        self._initialized = True
        logger.info("依赖注入容器初始化完成")

    async def _handle_config_init(self, msg: dict) -> dict:
        """处理内核发送的 config_init 请求，确认通信链路正常。"""
        logger.info("收到 config_init 请求，确认内核与 Python AI 通信通道可用", trace_id=msg.get("trace_id"))
        return {"status": "ok"}

    async def _handle_heartbeat(self) -> dict:
        """处理AI原生桥心跳请求。"""
        return {"status": "alive"}

    # ======================================
    # 实例获取方法
    # ======================================
    def get_self_entity(self) -> SelrenaSelfEntity:
        return self._instances["self_entity"]

    def get_kernel_bridge(self) -> KernelBridge:
        return self._instances["kernel_bridge"]

    def get_inbound_adapter(self) -> KernelEventInboundAdapter:
        return self._instances["inbound_adapter"]

    def get_outbound_adapter(self) -> KernelEventOutboundAdapter:
        return self._instances["outbound_adapter"]

    def get_chat_use_case(self) -> ChatUseCase:
        return self._instances["chat_use_case"]

    def get_active_thought_use_case(self) -> ActiveThoughtUseCase:
        return self._instances["active_thought_use_case"]