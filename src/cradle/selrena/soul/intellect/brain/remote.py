from typing import List, Dict
from openai import AsyncOpenAI
from cradle.schemas.configs.soul import LLMConfig
from cradle.utils.logger import logger
from .base import BaseBrainBackend

class OpenAIRemoteBackend(BaseBrainBackend):
    """
    OpenAI 协议兼容后端 (云端/中转台/Ollama Server)
    使用标准的 AsyncOpenAI 客户端进行网络请求。
    """
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client: AsyncOpenAI = None

    async def initialize(self):
        if not self.config.api_key:
            logger.warning("[OpenAI Backend] 未配置 API Key，将进入 Mock 模式 (如果上层业务逻辑支持)")
            # 这里我们不直接处理 Mock，Mock 这个概念属于 SoulIntellect 的业务层，后端只负责生图
            # 如果没有 key，OpenAI 客户端初始化可能会在某些库版本报错，或者在请求时报错。
            pass
            
        self.client = AsyncOpenAI(
            api_key=self.config.api_key or "sk-placeholder", # 防止空值初始化报错
            base_url=self.config.base_url
        )
        logger.debug(f"[OpenAI Backend] 已连接至: {self.config.base_url}")

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        if getattr(self.config, "api_mode", "chat") == "responses":
            return await self._generate_with_responses(messages)

        return await self._generate_with_chat(messages)

    async def _generate_with_chat(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[OpenAI Backend] 思考失败: {e}")
            err = str(e)
            if "404" in err and "Not support" in err:
                logger.info("[OpenAI Backend] Chat 不支持当前模型/端点，自动尝试 Responses。")
                return await self._generate_with_responses(messages, fallback_to_chat=False)
            return "大脑暂时短路了，请稍后再试。"

    async def _generate_with_responses(self, messages: List[Dict[str, str]], fallback_to_chat: bool = True) -> str:
        try:
            response = await self.client.responses.create(
                model=self.config.model,
                input=self._to_responses_input(messages),
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
            )
            text = self._extract_responses_text(response)
            if text:
                return text
            if fallback_to_chat:
                logger.warning("[OpenAI Backend] Responses 返回为空，降级到 Chat Completions。")
                return await self._generate_with_chat(messages)
            return "大脑暂时短路了，请稍后再试。"
        except Exception as e:
            logger.error(f"[OpenAI Backend] Responses 调用失败: {e}")
            if fallback_to_chat:
                logger.info("[OpenAI Backend] 自动降级到 Chat Completions。")
                return await self._generate_with_chat(messages)
            return "大脑暂时短路了，请稍后再试。"

    @staticmethod
    def _to_responses_input(messages: List[Dict[str, str]]) -> List[Dict[str, object]]:
        items: List[Dict[str, object]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            content = str(message.get("content", ""))
            if not content:
                continue
            if role == "assistant":
                content_type = "output_text"
            else:
                content_type = "input_text"
            items.append(
                {
                    "role": role,
                    "content": [{"type": content_type, "text": content}],
                }
            )
        return items

    @staticmethod
    def _extract_responses_text(response) -> str:
        try:
            text = getattr(response, "output_text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception:
            pass

        output = getattr(response, "output", None)
        if not output:
            return ""

        chunks: List[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") in ("output_text", "text"):
                    value = getattr(content, "text", "")
                    if value:
                        chunks.append(value)
        return "\n".join(chunks).strip()

    async def cleanup(self):
        if self.client:
            await self.client.close()
