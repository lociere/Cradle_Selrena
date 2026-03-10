"""LLM 适配器：封装不同后端的调用。"""

class LLMAdapter:
    async def generate(self, prompt: str, **kwargs) -> str:
        return ""
