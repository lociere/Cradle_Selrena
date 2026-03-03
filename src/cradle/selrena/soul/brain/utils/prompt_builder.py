from typing import Any, Dict, List, Union
from cradle.schemas.domain.chat import Message as ChatMessage

class PromptBuilder:
    """负责将不同的特征、系统设定、摘要组合成最终发送给模型的结构化 Prompt 的构建器"""

    @staticmethod
    def build_vision_extraction_prompt(last_user_msg: ChatMessage) -> List[ChatMessage]:
        """构建专门用于提取视觉特征的 Prompt"""
        content = (
            "<system_instruction>\n"
            "You are a powerful vision feature extractor.\n"
            "Objectively describe the image content, subjects, actions, and key elements.\n"
            "If text is present, extract it via OCR.\n"
            "Output ONLY the visual description in CHINESE.\n"
            "Do NOT use conversational tone.\n"
            "</system_instruction>"
        )
        system_msg = ChatMessage(role="system", content=content)
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
        content = (
            "<memory_context>\n"
            f"{memory_block}\n"
            "</memory_context>\n"
            "(System Note: Relevant past memories retrieved from database. Use as context if needed.)"
        )
        return ChatMessage(role="system", content=content)

    @staticmethod
    def build_context_window(persona_prompt: ChatMessage, relevant_memories: List[str], chat_history: List[ChatMessage], final_content: Any) -> List[ChatMessage]:
        """
        [Context Composition Layer]
        Assemble the final prompt chain using Pydantic Models.
        Order: Persona -> Memories -> Chat History -> Current User Message
        Returns: A list of Message objects
        
        [Normalization]
        Specifically for local LLMs (llama-cpp), consecutive messages with the same role are merged
        to strictly adhere to the `System -> User -> Assistant -> User` pattern.
        """
        raw_messages: List[ChatMessage] = []
        
        # 1. Base Structure - Persona (System)
        if persona_prompt and isinstance(persona_prompt, ChatMessage):
            raw_messages.append(persona_prompt)

        # 2. Inject Memories (System) - Merged immediately if possible
        if relevant_memories:
            memory_msg = PromptBuilder.build_memory_injection(relevant_memories)
            raw_messages.append(memory_msg)

        # 3. Chat History (User/Assistant...)
        for msg in chat_history:
            if isinstance(msg, ChatMessage):
                raw_messages.append(msg)

        # 4. Current Message (User)
        current_msg = ChatMessage(role="user", content=final_content)
        raw_messages.append(current_msg)

        if not raw_messages:
            return []

        # [Merge Logic]
        normalized_messages: List[ChatMessage] = []
        # Use model_copy to prevent mutating original memory objects
        current_block = raw_messages[0].model_copy()

        for next_msg in raw_messages[1:]:
            if next_msg.role == current_block.role:
                # Merge roles
                # Convert to string for safe merging (assuming text-heavy context for local LLMs)
                # If content is a list/complex object, we force string conversion to avoid type errors
                content_a = current_block.content
                content_b = next_msg.content
                
                text_a = content_a if isinstance(content_a, str) else str(content_a)
                text_b = content_b if isinstance(content_b, str) else str(content_b)
                
                current_block.content = f"{text_a}\n\n{text_b}"
            else:
                 normalized_messages.append(current_block)
                 current_block = next_msg.model_copy()
        
        normalized_messages.append(current_block)

        return normalized_messages
