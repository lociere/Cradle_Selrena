"""LLM 引擎：上层调用此类，不包含业务规则。"""

class LLMEngine:
    async def call(self, prompt: str, **kwargs):
        return ""
