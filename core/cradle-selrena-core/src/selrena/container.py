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
from selrena.application.chat_use_case import ChatUseCase
from selrena.application.active_thought_use_case import ActiveThoughtUseCase
from selrena.bridge.kernel_bridge import KernelBridge
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
        llm_engine = LLMEngine(self_entity=self_entity)
        self._instances["llm_engine"] = llm_engine

        # ======================================
        # 4. 应用层用例实例
        # ======================================
        chat_use_case = ChatUseCase(
            self_entity=self_entity,
            llm_engine=llm_engine
        )
        self._instances["chat_use_case"] = chat_use_case

        active_thought_use_case = ActiveThoughtUseCase(
            self_entity=self_entity
        )
        self._instances["active_thought_use_case"] = active_thought_use_case

        # ======================================
        # 5. 适配器层实例
        # ======================================
        # 入站适配器
        inbound_adapter = KernelEventInboundAdapter(
            self_entity=self_entity,
            chat_use_case=chat_use_case,
            active_thought_use_case=active_thought_use_case
        )
        self._instances["inbound_adapter"] = inbound_adapter

        # 出站适配器
        outbound_adapter = KernelEventOutboundAdapter(
            kernel_bridge=kernel_bridge
        )
        self._instances["outbound_adapter"] = outbound_adapter

        # ======================================
        # 6. 注册事件处理器
        # ======================================
        # 注册记忆同步事件处理器
        from selrena.domain.memory.long_term_memory import MemorySyncEvent
        event_bus.subscribe(MemorySyncEvent, lambda e: outbound_adapter.send_memory_sync(e.memory_fragment))

        # 注册内核消息处理器
        kernel_bridge.register_handler("chat_message", lambda msg: inbound_adapter.on_chat_message(
            ChatInput(
                user_input=msg["user_input"],
                scene_id=msg["scene_id"],
                familiarity=msg.get("familiarity", 0),
                trace_id=msg["trace_id"]
            )
        ))
        kernel_bridge.register_handler("life_heartbeat", lambda msg: inbound_adapter.on_life_heartbeat(
            ActiveThoughtInput(trace_id=msg["trace_id"])
        ))
        kernel_bridge.register_handler("memory_init", lambda msg: inbound_adapter.on_memory_init(msg["memories"]))
        kernel_bridge.register_handler("knowledge_init", lambda msg: inbound_adapter.on_knowledge_init(
            msg["persona_knowledge"],
            msg["general_knowledge"]
        ))

        # 标记为已初始化
        self._initialized = True
        logger.info("依赖注入容器初始化完成")

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