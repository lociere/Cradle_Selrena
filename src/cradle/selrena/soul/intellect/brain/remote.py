from typing import List, Dict
from openai import AsyncOpenAI
from cradle.schemas.configs.soul import LLMConfig
from cradle.utils.logger import logger
from . import BaseBrainBackend

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
            return "（大脑暂时短路了...）"

    async def cleanup(self):
        if self.client:
            await self.client.close()
