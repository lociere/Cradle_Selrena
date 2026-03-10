# 该文件已格式化，内部备注/注释请使用中文说明
"""LLM 后端抽象及实现。"""

from abc import ABC, abstractmethod
from typing import Optional
import httpx
import asyncio

from loguru import logger

# 可选依赖，用于本地 llama
LLAMA_CPP_AVAILABLE = False
try:
    import llama_cpp

    LLAMA_CPP_AVAILABLE = True
except ImportError:
    pass


class LLMBackend(ABC):
    """所有 LLM 后端的抽象基类。"""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """根据提示生成文本。"""
        pass


class DummyLLM(LLMBackend):
    """离线测试时使用的占位模型。"""

    async def generate(self, prompt: str) -> str:
        # 模拟原来中文 dummy 回复以兼容测试
        if len(prompt) < 100:
            return "这是一个模拟回复：" + prompt
        return f"[模拟] {prompt[:50]}..."

    async def cleanup(self) -> None:
        return


class OpenAILLM(LLMBackend):
    """对 OpenAI 兼容 HTTP 接口的封装。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-3.5-turbo",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=60.0)

    async def generate(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {"model": self.model, "prompt": prompt}
        resp = await self.client.post(
            f"{self.base_url}/completions", json=data, headers=headers
        )
        resp.raise_for_status()
        r = resp.json()
        return r.get("choices", [{}])[0].get("text", "")

    async def cleanup(self) -> None:
        await self.client.aclose()


class LocalLLM(LLMBackend):
    """本地模型包装器（需要 llama_cpp 库）。

    本类为存根，完整实现依赖于 llama_cpp 安装。
    """

    def __init__(self, model_path: str):
        if not LLAMA_CPP_AVAILABLE:
            raise RuntimeError("llama_cpp not available")
        self.model_path = model_path
        self.model = None

    async def generate(self, prompt: str) -> str:
        if self.model is None:
            self.model = llama_cpp.Llama(model_path=self.model_path)
        return self.model(prompt)

    async def cleanup(self) -> None:
        # 无需显式清理
        pass
