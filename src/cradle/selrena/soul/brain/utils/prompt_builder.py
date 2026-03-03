from typing import Any, Dict, List, Union
from cradle.schemas.domain.chat import Message as ChatMessage

class PromptBuilder:
    """负责将不同的特征、系统设定、摘要组合成最终发送给模型的结构化 Prompt 的构建器"""

    @staticmethod
    def build_vision_extraction_prompt(last_user_msg: ChatMessage) -> List[ChatMessage]:
        """构建专门用于提取视觉特征的 Prompt"""
        system_msg = ChatMessage(
            role="system",
            content="你是强大的视觉特征提取器。请客观描述图片中的内容、主体、关键元素（若有文字请提取OCR）。只输出视觉信息，不要以聊天助手语气回复。"
        )
        return [system_msg, last_user_msg]

    @staticmethod
    def build_fallback_message(error_type: str = "generic") -> str:
        """构建降级或崩溃时的托底回复"""
        if error_type == "vision_failure":
            return "（图片识别失败）"
        elif error_type == "empty_response":
            return "大脑一片空白..."
        return "大脑暂时无法响应。"

    @staticmethod
    def build_memory_injection(relevant_memories: List[str]) -> ChatMessage:
        """构建记忆注入块"""
        memory_block = "\n".join([f"- {m}" for m in relevant_memories])
        return ChatMessage(
            role="system",
            content=f"【闪回记忆 (相关历史)】\n{memory_block}\n(以上信息仅供参考，不一定与当前对话直接相关)"
        )

    @staticmethod
    def build_context_window(persona_prompt: ChatMessage, relevant_memories: List[str], chat_history: List[ChatMessage], final_content: Any) -> List[ChatMessage]:
        """
        [Context Composition Layer]
        Assemble the final prompt chain using Pydantic Models.
        Order: Persona -> Memories -> Chat History -> Current User Message
        Returns: A list of Message objects
        """
        # 1. Base Structure
        context_messages: List[ChatMessage] = []
        
        # Ensure persona is valid
        if persona_prompt and isinstance(persona_prompt, ChatMessage):
            context_messages.append(persona_prompt)

        # 2. Inject Memories (if available)
        if relevant_memories:
            # Now build_memory_injection returns a ChatMessage directly
            memory_msg = PromptBuilder.build_memory_injection(relevant_memories)
            context_messages.append(memory_msg)

        # 3. Chat History (Schema Support Only)
        for msg in chat_history:
            if isinstance(msg, ChatMessage):
                context_messages.append(msg)

        # 4. Current Message (The Trigger)
        # Standardize current message creation
        context_messages.append(ChatMessage(role="user", content=final_content))

        return context_messages
