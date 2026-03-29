"""
文件名称：kernel_ingress_cortex.py
所属层级：适配器层-入站 Cortex
核心作用：负责把内核原始消息解析为标准类型，向应用层输出纯净输入模型。
"""

from __future__ import annotations

from selrena.application.active_thought_use_case import ActiveThoughtInput
from selrena.application.agent_plan_use_case import AgentPlanInput
from selrena.application.chat_use_case import ChatInput
from selrena.core.contracts.kernel_ingress_contracts import (
    AgentPlanPayloadModel,
    KnowledgeBaseInitPayloadModel,
    KernelLongTermMemoryRecord,
    KernelMessageEnvelope,
    KnowledgeInitPayloadModel,
    LifeHeartbeatPayloadModel,
    MemoryInitPayloadModel,
    PerceptionEventPayloadModel,
)


class KernelIngressCortex:
    """内核入站消息解析器。"""

    def parse_perception_message(self, message: dict) -> ChatInput:
        envelope = KernelMessageEnvelope.model_validate(message)
        payload = PerceptionEventPayloadModel.model_validate(envelope.payload)
        return ChatInput(
            model_input=payload.content.model_dump(),
            scene_id=payload.source,
            familiarity=payload.familiarity,
            trace_id=envelope.trace_id,
        )

    def parse_life_heartbeat(self, message: dict) -> ActiveThoughtInput:
        envelope = KernelMessageEnvelope.model_validate(message)
        payload = LifeHeartbeatPayloadModel.model_validate(envelope.payload)
        return ActiveThoughtInput(
            trace_id=envelope.trace_id,
            attention_mode=payload.attention_mode,
        )

    def parse_memory_init(self, message: dict) -> list[KernelLongTermMemoryRecord]:
        envelope = KernelMessageEnvelope.model_validate(message)
        payload = MemoryInitPayloadModel.model_validate(envelope.payload)
        return payload.memories

    def parse_knowledge_init(self, message: dict) -> KnowledgeBaseInitPayloadModel:
        envelope = KernelMessageEnvelope.model_validate(message)
        payload = KnowledgeInitPayloadModel.model_validate(envelope.payload)
        return payload.knowledge_base

    def parse_agent_plan(self, message: dict) -> AgentPlanInput:
        envelope = KernelMessageEnvelope.model_validate(message)
        payload = AgentPlanPayloadModel.model_validate(envelope.payload)
        return AgentPlanInput(
            user_goal=payload.user_goal,
            scene_id=payload.scene_id,
            trace_id=envelope.trace_id,
        )
