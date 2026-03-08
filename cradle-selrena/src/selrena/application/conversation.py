"""对话服务 - 核心对话流程编排（迁移自 cradle_selrena_core）"""

from typing import Optional

from selrena.inference.engines.utils.preprocessor import MultimodalPreprocessor
from selrena.domain.emotion import EmotionCategory, EmotionState
from selrena.schemas.chat import Message, ChatHistory
from selrena.domain.memory import Memory, MemoryType
from selrena.domain.persona import Persona
from selrena.soul.persona import PersonaManager
from selrena.inference.llm import LLMBackend
from selrena.ports import KernelPort, MemoryPort
from selrena.utils.logger import logger


from dataclasses import dataclass


@dataclass
class ConversationResult:
    response: str
    emotion_state: EmotionState
    memory_to_store: Memory | None = None
    reasoning_steps: list[str] = None
    confidence: float = 1.0


class ConversationService:
    """
    对话服务
    
    负责：
    1. 接收用户输入
    2. 检索相关记忆
    3. 构建上下文
    4. 调用 LLM 生成回复
    5. 更新记忆
    6. 发送回复
    """
    
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
        # wrap persona in a manager for prompt construction
        self.persona_manager = PersonaManager(persona)
        self.emotion = EmotionState()
        logger.info("ConversationService 初始化完成")
    
    async def process_message(self, user_input: str, is_external: bool = False) -> str:
        """
        处理用户消息的完整流程
        
        Args:
            user_input: 用户输入文本
            is_external: 来自外部源时不使用持久短时记忆
            
        Returns:
            AI 回复文本
        """
        logger.info(f"收到用户消息：{user_input[:50]}... 外部: {is_external}")
        
        # 1. 检索相关记忆（外部请求不检索，避免泄露主用户历史）
        relevant_memories = []
        if not is_external:
            relevant_memories = await self.memory.retrieve_memories(user_input, n_results=3)
        logger.debug(f"检索到 {len(relevant_memories)} 条相关记忆")
        
        # 2. 构建对话上下文，使用 Message/ChatHistory 格式
        history = ChatHistory()
        for mem in relevant_memories:
            history.messages.append(Message(role="system", content=mem.content))
        history.add_message("user", user_input)
        context = self._build_context(history, relevant_memories)
        
        # 3. 调用 LLM 生成回复
        response = await self.llm.generate(context)
        if not response:
            response = "我好像走神了...能再说一遍吗？"
        
        # 4. 提取情感
        emotion = self._detect_emotion(response)
        self.emotion.update(emotion, 0.6)
        
        # 5. 保存对话到记忆
        await self._save_conversation(user_input, response)
        
        # 6. 发送回复
        await self.kernel.send_message(response, emotion=emotion.value)
        
        logger.info(f"回复生成：{response[:50]}...")
        return response

    async def process_conversation(self, user_id: str, message: str, conversation_id: str | None = None, is_external: bool = False) -> ConversationResult:
        """兼容 AIService 的调用，返回详细结果"""
        # 目前直接复用 process_message，扩展返回字段
        response = await self.process_message(message, is_external=is_external)
        result = ConversationResult(
            response=response,
            emotion_state=self.emotion,
            memory_to_store=None,
            reasoning_steps=[],
            confidence=1.0
        )
        return result
    
    def _build_context(self, history: ChatHistory, memories: list[Memory]) -> str:
        """构建 LLM 上下文，使用 ChatHistory 对象"""
        # 预处理历史消息、记忆文本，去除非文本块以便兼容纯文本模型
        msgs = [m.content for m in history.messages]
        clean_msgs = MultimodalPreprocessor.sanitize_for_text_core(msgs)

        # use PersonaManager to build the system prompt (adds timestamp etc.)
        context_parts = [
            self.persona_manager.build_system_prompt(),
            "\n# 对话历史\n",
        ]
        for idx, m in enumerate(clean_msgs):
            role = history.messages[idx].role if idx < len(history.messages) else "user"
            context_parts.append(f"{role}：{m}")

        context_parts.append("\n# 相关记忆\n")
        for mem in memories:
            context_parts.append(f"- {mem.content}")

        # 保留结尾的角色提示
        context_parts.append(f"{self.persona.name}：")
        return "\n".join(context_parts)
    
    def _detect_emotion(self, text: str) -> EmotionCategory:
        """简单的情感检测（未来用模型）"""
        text_lower = text.lower()
        
        positive_words = ["开心", "高兴", "哈哈", "嘻嘻", "好棒", "喜欢"]
        negative_words = ["难过", "伤心", "生气", "讨厌", "糟糕", "烦"]
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count > neg_count:
            return EmotionCategory.JOY
        elif neg_count > pos_count:
            return EmotionCategory.SADNESS
        else:
            return EmotionCategory.NEUTRAL
    
    async def _save_conversation(self, user_input: str, response: str) -> None:
        """保存对话到记忆"""
        user_memory = Memory(
            content=f"用户说：{user_input}",
            memory_type=MemoryType.EPISODIC,
            tags=["conversation", "user"],
        )
        
        bot_memory = Memory(
            content=f"我说：{response}",
            memory_type=MemoryType.EPISODIC,
            tags=["conversation", "bot"],
        )
        
        await self.memory.save_memory(user_memory)
        await self.memory.save_memory(bot_memory)
