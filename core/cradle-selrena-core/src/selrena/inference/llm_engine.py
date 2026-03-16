"""
文件名称：llm_engine.py
所属层级：推理层
核心作用：纯算力调用封装，仅负责LLM生成，不碰任何业务规则、人设、prompt构建
设计原则：
1. 仅做LLM API/本地模型调用封装，无任何业务逻辑
2. 所有prompt构建、人设注入都在应用层完成，这里仅做纯生成
3. 可插拔替换，更换模型仅需修改这里，核心代码零改动
4. 兼容本地模型和云端LLM，自动适配
"""
from typing import Optional
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.core.exceptions import InferenceException
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("llm_engine")


# ======================================
# LLM推理引擎
# ======================================
class LLMEngine:
    """
    LLM推理引擎，纯算力调用
    核心作用：接收完整的prompt，返回生成的文本，不做任何业务处理
    """
    def __init__(self, self_entity: SelrenaSelfEntity):
        """
        初始化LLM引擎
        参数：
            self_entity: 月见自我实体实例
        """
        self.self_entity = self_entity
        self.config = self_entity.inference_config.model
        # 本地模型实例，初始化时懒加载
        self._model = None
        logger.info("LLM引擎初始化完成", model_path=self.config.local_model_path)

    def _load_model(self) -> None:
        """懒加载本地模型，仅在第一次生成时加载"""
        if self._model is not None:
            return
        try:
            # ======================
            # 这里替换成你的本地模型加载代码
            # 示例：llama.cpp / ollama / openai-api
            # ======================
            # from llama_cpp import Llama
            # self._model = Llama(
            #     model_path=self.config.local_model_path,
            #     n_ctx=2048,
            #     n_threads=8
            # )
            logger.info("本地模型加载完成", model_path=self.config.local_model_path)
        except Exception as e:
            raise InferenceException(f"本地模型加载失败: {str(e)}")

    def generate(self, full_prompt: str) -> str:
        """
        生成回复，纯算力调用
        参数：
            full_prompt: 应用层构建好的完整prompt，包含人设、记忆、情绪、用户输入
        返回：LLM生成的纯文本
        异常：
            InferenceException: 生成失败时抛出
        """
        try:
            # 懒加载模型
            self._load_model()

            # ======================
            # 这里替换成你的模型调用代码
            # ======================
            # 示例：本地llama.cpp调用
            # output = self._model.create_completion(
            #     prompt=full_prompt,
            #     max_tokens=self.config.max_tokens,
            #     temperature=self.config.temperature,
            #     top_p=self.config.top_p,
            #     frequency_penalty=self.config.frequency_penalty,
            #     stop=["<|endoftext|>"]
            # )
            # reply = output["choices"][0]["text"].strip()

            # 临时示例，生产环境替换成真实模型调用
            reply = f"哼，{full_prompt.split('用户对你说：')[-1].split('\n')[0]}...笨蛋，我才没有在意呢。"

            logger.debug("LLM生成完成", reply_length=len(reply))
            return reply.strip()

        except Exception as e:
            raise InferenceException(f"LLM生成失败: {str(e)}")