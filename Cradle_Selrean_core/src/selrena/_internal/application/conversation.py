# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""对话服务 - 处理对话流程。"""

from typing import Optional
from dataclasses import dataclass

from selrena._internal.utils.text.preprocessor import MultimodalPreprocessor
from selrena._internal.domain.emotion import EmotionCategory, EmotionState
from selrena._internal.schemas.chat import Message, ChatHistory
from selrena._internal.domain.memory import Memory, MemoryType
from selrena._internal.domain.persona import Persona
from selrena._internal.domain.persona_manager import PersonaManager
from selrena._internal.inference.llm import LLMBackend
from selrena._internal.ports.kernel_port import KernelPort
from selrena._internal.ports.memory_port import MemoryPort
from loguru import logger


@dataclass
class ConversationResult:
    response: str
    emotion_state: EmotionState
    memory_to_store: Memory | None = None
    reasoning_steps: list[str] = None
    confidence: float = 1.0


class ConversationService:
    """高级对话协调器。"""

    def __init__(
        self,
        persona: Persona,
        llm: LLMBackend,
        kernel: KernelPort,
        memory: MemoryPort,
    ):
        self.persona = persona
        self.llm = llm
        self.kernel = kernel
        self.memory = memory
        self.persona_manager = PersonaManager(persona)
        self.emotion = EmotionState()
        logger.info("ConversationService 初始化")

    async def process_message(self, message: str) -> str:
        # 简单管线：将输入保存到记忆，调用 LLM，返回响应
        if self.memory:
            from selrena._internal.domain.memory import Memory, MemoryType

            mem = Memory(content=message, memory_type=MemoryType.EPISODIC)
            await self.memory.save_memory(mem)
        response = await self.llm.generate(message)
        # 可选地也将模型输出存为记忆
        if self.memory:
            resp_mem = Memory(content=response, memory_type=MemoryType.EPISODIC)
            await self.memory.save_memory(resp_mem)
        return response
