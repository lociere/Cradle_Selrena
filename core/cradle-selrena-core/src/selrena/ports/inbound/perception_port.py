"""
文件名称：perception_port.py
所属层级：端口层-入站端口
核心作用：定义入站信号的抽象接口，遵循依赖倒置原则
设计原则：
1. 仅定义抽象接口，不做实现
2. 所有来自内核的入站信号，必须通过此接口定义
3. 完全屏蔽底层通信细节，应用层仅依赖此接口
"""
from abc import ABC, abstractmethod
from selrena.application.chat_use_case import ChatInput, ChatOutput
from selrena.application.active_thought_use_case import ActiveThoughtInput, ActiveThoughtOutput
from selrena.application.agent_plan_use_case import AgentPlanInput, AgentPlanOutput
from selrena.core.contracts.kernel_ingress_contracts import KnowledgeBaseInitPayloadModel, KernelLongTermMemoryRecord


class PerceptionPort(ABC):
    """
    感知入站端口抽象接口
    核心作用：定义AI层能接收的所有外界信号，完全屏蔽底层通信细节
    真人逻辑对齐：对应人脑的感官输入接口，仅定义能接收什么信号，不关心信号从哪里来
    """

    @abstractmethod
    async def on_perception_message(self, input_data: ChatInput) -> ChatOutput:
        """
        接收通用感知消息（第三方平台统一入口）
        参数：
            input_data: 标准化对话输入
        返回：标准化对话输出
        """
        pass

    @abstractmethod
    async def on_life_heartbeat(self, input_data: ActiveThoughtInput) -> ActiveThoughtOutput:
        """
        接收内核的生命心跳，触发主动思维
        参数：
            input_data: 心跳输入
        返回：思维结果输出
        """
        pass

    @abstractmethod
    async def on_memory_init(self, memories: list[KernelLongTermMemoryRecord]) -> None:
        """
        接收内核注入的历史长期记忆
        参数：
            memories: 历史记忆列表
        """
        pass

    @abstractmethod
    async def on_knowledge_init(
        self,
        knowledge_base: KnowledgeBaseInitPayloadModel,
    ) -> None:
        """
        接收内核注入的知识库
        参数：
            knowledge_base: 知识库完整载荷
        """
        pass

    @abstractmethod
    async def on_agent_plan(self, input_data: AgentPlanInput) -> AgentPlanOutput:
        """
        接收任务规划请求（MCP），仅返回思考与工具建议，不执行任务。
        """
        pass