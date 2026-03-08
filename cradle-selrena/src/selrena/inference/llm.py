"""LLM 后端接口与实现（迁移自 cradle_selrena_core）"""

from abc import ABC, abstractmethod
from typing import Optional
import httpx
import asyncio

from selrena.utils.logger import logger

# 检查可选依赖
LLAMA_CPP_AVAILABLE = False
try:
    import llama_cpp
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    pass


class LLMBackend(ABC):
    """LLM 后端抽象基类"""
    
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """生成文本回复"""
        pass


class DummyLLM(LLMBackend):
    """简单的占位 LLM，用于本地测试或无 API key 时。

    它仅仅回显 prompt 或返回固定文本，方便离线跑流程。
    """
    async def generate(self, prompt: str) -> str:
        # 如果 prompt 较短就直接返回一条默认消息
        if len(prompt) < 100:
            return "这是一个模拟回复：" + prompt
        # 否则取前 50 字并说明这是模拟
        return f"[模拟] {prompt[:50]}..."
    
    async def cleanup(self) -> None:
        """清理资源（无操作）。"""
        return


class OpenAILLM(LLMBackend):
    """
    OpenAI 兼容 API 的 LLM 实现
    
    支持：
    - OpenAI GPT
    - Azure OpenAI
    - 其他兼容 API（如本地 vLLM、Ollama 等）
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"OpenAILLM 初始化完成：{model}")
    
    async def generate(self, prompt: str) -> str:
        """调用 OpenAI 兼容 API 生成文本"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(f"LLM 生成：{content[:50]}...")
            return content
        except Exception as e:
            logger.error(f"LLM 调用失败：{e}")
            return ""
    
    async def cleanup(self):
        """清理资源"""
        await self.client.aclose()


class LocalLLM(LLMBackend):
    """
    本地 LLM 实现（GGUF 模型）
    
    使用 llama-cpp-python 作为后端
    """
    
    def __init__(self, model_path: str, n_ctx: int = 2048, n_threads: int = 4):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.model = None
        logger.info(f"LocalLLM 初始化完成：{model_path}")
    
    async def initialize(self):
        """异步初始化模型"""
        if not LLAMA_CPP_AVAILABLE:
            logger.warning("llama_cpp 未安装，本地LLM功能不可用")
            self.model = None
            return
        
        try:
            from llama_cpp import Llama
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
            )
            logger.info("本地模型加载成功")
        except Exception as e:
            logger.error(f"本地模型加载失败：{e}")
            self.model = None
    
    async def generate(self, prompt: str) -> str:
        """使用本地模型生成"""
        if not self.model:
            raise RuntimeError("模型未初始化")
        
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None,
            lambda: self.model(prompt, max_tokens=512, stop=["\n\n"], echo=False)
        )
        
        content = output["choices"][0]["text"]
        logger.debug(f"本地 LLM 生成：{content[:50]}...")
        return content
    
    async def cleanup(self):
        """清理资源"""
        self.model = None
