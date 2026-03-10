"""推理能力调用接口。"""

from typing import Protocol, Any


class InferencePort(Protocol):
    async def call_llm(self, prompt: str, **kwargs: Any) -> str:
        ...

    async def embed(self, text: str) -> list[float]:
        ...
