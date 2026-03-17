"""
文件名称：kernel_event_adapter.py
所属层级：适配器层-入站适配器
核心作用：实现入站端口的抽象接口，处理内核传入的信号，调用对应的用例
设计原则：
1. 仅做协议转换，不碰业务逻辑
2. 把内核传入的原始消息，转换为应用层能处理的标准化输入
3. 不做任何流程编排，仅做路由转发
"""
from selrena.ports.inbound.perception_port import PerceptionPort
from selrena.application.chat_use_case import ChatUseCase, ChatInput, ChatOutput
from selrena.application.active_thought_use_case import ActiveThoughtUseCase, ActiveThoughtInput, ActiveThoughtOutput
from selrena.application.agent_plan_use_case import AgentPlanUseCase, AgentPlanInput, AgentPlanOutput
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("inbound_adapter")


class KernelEventInboundAdapter(PerceptionPort):
    """
    内核事件入站适配器
    核心作用：接收内核传入的IPC消息，转换为标准化输入，调用对应的用例
    设计规范：仅做协议转换和路由，不碰任何业务逻辑
    """
    def __init__(
        self,
        self_entity: SelrenaSelfEntity,
        chat_use_case: ChatUseCase,
        active_thought_use_case: ActiveThoughtUseCase,
        agent_plan_use_case: AgentPlanUseCase,
    ):
        self.self_entity = self_entity
        self.chat_use_case = chat_use_case
        self.active_thought_use_case = active_thought_use_case
        self.agent_plan_use_case = agent_plan_use_case
        logger.info("内核入站适配器初始化完成")

    async def on_perception_message(self, message: dict) -> ChatOutput:
        """接收通用感知消息并转换为对话输入。"""
        payload = message.get("payload", {})
        input_data = ChatInput(
            model_input=payload.get("input", {"items": []}),
            scene_id=payload.get("scene_id", "default"),
            familiarity=payload.get("familiarity", 0),
            trace_id=message.get("trace_id", ""),
        )
        return await self.on_chat_message(input_data)

    async def on_chat_message(self, input_data: ChatInput) -> ChatOutput:
        """接收内核的对话消息，调用对话用例"""
        logger.info(
            "收到内核对话消息",
            trace_id=input_data.trace_id,
            scene_id=input_data.scene_id
        )
        return await self.chat_use_case.execute(input_data, input_data.trace_id)

    async def on_life_heartbeat(self, input_data: ActiveThoughtInput) -> ActiveThoughtOutput:
        """接收内核的生命心跳，调用主动思维用例"""
        logger.debug(
            "收到内核生命心跳",
            trace_id=input_data.trace_id
        )
        return await self.active_thought_use_case.execute(input_data, input_data.trace_id)

    async def on_memory_init(self, memories: list[dict]) -> None:
        """接收内核注入的历史长期记忆"""
        logger.info("收到内核历史记忆注入", memory_count=len(memories))
        self.self_entity.long_term_memory.init_from_kernel(memories)

    async def on_knowledge_init(self, persona_knowledge: list[dict], general_knowledge: list[dict]) -> None:
        """接收内核注入的知识库"""
        logger.info(
            "收到内核知识库注入",
            persona_count=len(persona_knowledge),
            general_count=len(general_knowledge)
        )
        self.self_entity.knowledge_base.init_from_kernel(persona_knowledge, general_knowledge)

    async def on_agent_plan(self, input_data: AgentPlanInput) -> AgentPlanOutput:
        """接收内核的 Agent 规划请求，仅返回思考建议。"""
        logger.info("收到 Agent 规划请求", trace_id=input_data.trace_id, scene_id=input_data.scene_id)
        return await self.agent_plan_use_case.execute(input_data, input_data.trace_id)