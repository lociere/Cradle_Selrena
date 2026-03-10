# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""AI 容器模块。

本模块定义了 `AIContainer` 类，负责：
1. 实例化并持有各种适配器（Kernel、Memory、Persona 等）。
2. 管理 LLM 后端的创建与清理。
3. 从配置中加载指定人格并构建相应服务。
4. 对外暴露统一的对话、记忆和推理接口。

还提供了一个全局访问函数以便获取单例。
"""

from pathlib import Path
from typing import Optional

# adapters are implementation details moved under _internal
# only _internal modules should import them directly; public API
# never exposes adapters.
from selrena._internal.adapters import KernelAdapter, MemoryAdapter, PersonaAdapter
from selrena._internal.application import (
    ConversationService,
    MemoryService,
    ReasoningService,
)
from selrena._internal.domain.persona import Persona
from selrena._internal.inference.llm import LLMBackend, DummyLLM, OpenAILLM, LocalLLM
from selrena._internal.ports.kernel_port import KernelPort
from selrena._internal.ports.memory_port import MemoryPort
from selrena._internal.ports.persona_port import PersonaPort
from selrena._internal.ports.agent import AgentPort
from selrena._internal.agent import CommandGenerator
from selrena._internal.core.logger import logger


class AIContainer:
    """核心 AI 容器。

    该类将各个服务和适配器组合在一起，形成一个
    可初始化、清理、并对外提供操作的整体。

    主要职责：
    1. 按照配置加载并管理 LLM 后端实例。
    2. 初始化 Kernel/Memory/Persona 等适配器。
    3. 创建 ConversationService、MemoryService 和 ReasoningService。
    4. 提供对话、记忆、推理接口的访问方法。
    """

    def __init__(self, config_dir: Path | str, data_dir: Path | str):
        # 规范路径类型为 pathlib.Path
        from pathlib import Path

        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir)

        # 低层组件实例引用，初始化时填充
        self.llm: Optional[LLMBackend] = None
        self.kernel: Optional[KernelPort] = None
        self.memory: Optional[MemoryPort] = None
        self.persona_adapter: Optional[PersonaPort] = None
        self.agent_port: Optional[AgentPort] = None

        # 高级服务引用
        self.conversation: Optional[ConversationService] = None
        self.memory_service: Optional[MemoryService] = None
        self.reasoning: Optional[ReasoningService] = None

        # 当前加载的人格
        self.current_persona: Optional[Persona] = None

        logger.info("AIContainer 实例创建")

    async def initialize(self, llm_config: dict, use_local_llm: bool = False):
        """根据提供的配置初始化各组件。

        Args:
            llm_config: 包含 LLM 参数的字典。
            use_local_llm: 为 True 时使用本地 LLM 后端；
                否则使用远程 OpenAI 或 DummyLLM。
        """
        logger.info("初始化 AI 容器...")

        # 1. 创建适配器
        self.kernel = KernelAdapter()
        self.memory = MemoryAdapter(self.data_dir / "memory")
        self.persona_adapter = PersonaAdapter(self.config_dir / "persona")

        # 2. 根据配置加载 LLM
        if use_local_llm:
            model_path = llm_config.get("model_path", "")
            if not model_path:
                raise ValueError("需要指定本地模型路径")
            self.llm = LocalLLM(model_path)
            await self.llm.initialize()
        else:
            api_key = llm_config.get("api_key", "")
            if api_key:
                self.llm = OpenAILLM(
                    api_key=api_key,
                    base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
                    model=llm_config.get("model", "gpt-3.5-turbo"),
                )
            else:
                # 未提供 key 时降级到模拟模型
                logger.warning("未提供 LLM API key，使用 DummyLLM 模拟回复")
                self.llm = DummyLLM()

        # 3. 加载或构造人格
        persona_name = llm_config.get("persona", "default")
        try:
            self.current_persona = await self.persona_adapter.load_persona(persona_name)
            logger.info(f"加载人格：{persona_name}")
        except FileNotFoundError:
            logger.warning(f"未找到指定人格 {persona_name}，使用默认模板")
            self.current_persona = Persona(
                name=persona_name,
                identity="默认身份描述",
                values=["诚实", "乐于助人"],
                expression_style={"tone": "友好"},
            )

        # 4. 创建高级服务
        self.memory_service = MemoryService(self.memory)
        self.conversation = ConversationService(
            persona=self.current_persona,
            llm=self.llm,
            kernel=self.kernel,
            memory=self.memory,
        )
        self.reasoning = ReasoningService(llm=self.llm)

        # 5. agent 相关设置
        # AgentPort 由 KernelAdapter 提供实现
        self.agent_port: AgentPort = self.kernel  # type: ignore[assignment]
        self.command_generator = CommandGenerator(self.agent_port)

        logger.info("AI 容器初始化完成")

    # 以下为外部访问接口
    def get_conversation_service(self):
        if not self.conversation:
            raise RuntimeError("ConversationService 尚未初始化")
        return self.conversation

    def get_memory_service(self):
        if not self.memory_service:
            raise RuntimeError("MemoryService 尚未初始化")
        return self.memory_service

    def get_reasoning_service(self):
        if not self.reasoning:
            raise RuntimeError("ReasoningService 尚未初始化")
        return self.reasoning

    def get_persona(self):
        return self.current_persona

    async def chat(self, message: str) -> str:
        """向会话服务发送消息并获得回复。

        Args:
            message: 用户输入文本。

        Returns:
            模型生成的文本。
        """
        if not self.conversation:
            raise RuntimeError("AI 容器尚未初始化会话服务")

        return await self.conversation.process_message(message)

    async def cleanup(self):
        """释放容器持有的资源。

        当前仅清理 LLM，将来可能关闭数据库连接、停止后台任务等。
        """
        logger.info("清理 AI 容器资源...")

        if self.llm:
            await self.llm.cleanup()

        logger.info("AI 容器已清理")


# 全局单例变量
global_ai_container: Optional[AIContainer] = None


def get_container() -> AIContainer:
    """获取全局 AIContainer 实例。

    如果尚未创建会抛出 RuntimeError。
    """
    if global_ai_container is None:
        raise RuntimeError("AI 容器尚未初始化")
    return global_ai_container
