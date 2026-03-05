from typing import List, Optional

from openai import APITimeoutError, AsyncOpenAI

from cradle.schemas.configs.soul import LLMConfig
from cradle.schemas.domain.chat import Message as ChatMessage
from cradle.utils.logger import logger

from .base import BaseBrainBackend
from .utils.preprocessor import MultimodalPreprocessor


class OpenAIRemoteBackend(BaseBrainBackend):
    """
    OpenAI 协议兼容后端 (纯文本/多模态)
    【架构降级声明】：
    现在 Remote Backend 是完全无状态、无副作用的纯文本计算单元。
    """

    # --- Initialization ---

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client: Optional[AsyncOpenAI] = None

    async def initialize(self):
        self.client = AsyncOpenAI(
            api_key=self.config.api_key or "sk-placeholder",
            base_url=self.config.base_url,
            timeout=getattr(self.config, "timeout", 60.0),
            max_retries=2
        )
        logger.debug(f"[BrainKernel] Initialized core: {self.config.model}")

    async def cleanup(self):
        if self.client:
            await self.client.close()

    @property
    def is_multimodal(self) -> bool:
        # Heuristic: 检查模型名是否暗示支持多模态
        model = self.config.model.lower()
        return any(k in model for k in ("vision", "gpt-4", "claude-3", "gemini", "qwen", "llava", "vl"))

    # --- Core Logic ---

    async def generate(self, messages: List[ChatMessage]) -> str:
        # 这个方法现在接收的是已经经过 Perception 层或 Router 层处理过的记忆或多模态消息
        # 转换为 OpenAI 兼容的 Dict 格式
        chat_messages = MultimodalPreprocessor.to_llm_payload(messages)

        try:
            # logger.debug(f"[BrainKernel] Thinking... input_len={len(str(chat_messages))}")
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=chat_messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            choices = getattr(response, "choices", None) or []
            if not choices:
                logger.warning(f"[BrainKernel] {self.config.model} returned no choices.")
                return ""

            first_message = getattr(choices[0], "message", None)
            content = getattr(first_message, "content", None)
            if not content:
                logger.warning(
                    f"[BrainKernel] {self.config.model} returned empty.")
                return ""

            return content

        except APITimeoutError:
            logger.error(f"[BrainKernel] Timeout: {self.config.model}")
            raise
        except Exception as e:
            logger.error(f"[BrainKernel] Error: {e}", exc_info=True)
            raise
