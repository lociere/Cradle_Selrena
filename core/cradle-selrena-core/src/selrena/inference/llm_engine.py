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
import json
from typing import Optional
from urllib import error, request
from urllib.parse import urljoin

from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.core.config import LLMConfig
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
    def __init__(self, self_entity: SelrenaSelfEntity, llm_config: Optional[LLMConfig] = None):
        """初始化LLM引擎

        参数：
            self_entity: 月见自我实体实例
            llm_config: 可选的云端/API LLM配置，由内核注入
        """
        self.self_entity = self_entity
        self.config = self_entity.inference_config.model
        self.llm_config = llm_config
        # 本地模型实例，初始化时懒加载
        self._model = None
        logger.info("LLM引擎初始化完成", model_path=self.config.local_model_path, llm_config=self.llm_config)

    def _load_local_model(self) -> None:
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

    def _generate_via_api(self, full_prompt: str) -> str:
        """通过云端/API LLM生成回复"""
        if not self.llm_config:
            raise InferenceException("缺少 LLM 配置，无法调用云端服务")

        api_type = self.llm_config.api_type.lower().strip()
        api_key = self.llm_config.api_key
        if not api_key:
            raise InferenceException("缺少 LLM API Key，请在配置中提供")

        base_url = (self.llm_config.base_url or "https://api.deepseek.com").rstrip("/")
        request_method = (self.llm_config.request_method or "POST").upper()
        if self.llm_config.request_path:
            request_path = self.llm_config.request_path
        elif api_type in {"deepseek", "openai"}:
            request_path = "/v1/chat/completions"
        else:
            request_path = "/v1/completions"
        endpoint = urljoin(base_url + "/", request_path.lstrip("/"))

        model_name = self.llm_config.model or (
            "deepseek-chat" if api_type == "deepseek" else self.config.local_model_path
        )

        # 默认请求体（OpenAI/DeepSeek 兼容）
        if request_path.endswith("/chat/completions"):
            default_payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": full_prompt}],
                "max_tokens": self.config.max_tokens,
                "temperature": self.llm_config.temperature if self.llm_config.temperature is not None else self.config.temperature,
            }
        else:
            default_payload = {
                "model": model_name,
                "prompt": full_prompt,
                "max_tokens": self.config.max_tokens,
                "temperature": self.llm_config.temperature if self.llm_config.temperature is not None else self.config.temperature,
            }

        # 支持自定义请求体模板（占位符：{prompt},{model},{temperature}）
        if self.llm_config.request_body_template:
            template = self.llm_config.request_body_template
            try:
                body_text = template.format(
                    prompt=full_prompt,
                    model=default_payload["model"],
                    temperature=default_payload["temperature"],
                )
                payload = json.loads(body_text)
            except Exception as e:
                raise InferenceException(f"请求体模板解析失败: {str(e)}")
        else:
            payload = default_payload

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        # 允许在配置中覆盖或补充额外 Header
        if self.llm_config.request_headers:
            headers.update(self.llm_config.request_headers)

        try:
            req = request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method=request_method,
            )
            with request.urlopen(req, timeout=60) as resp:
                resp_data = json.load(resp)

            # 兼容不同API返回格式
            if isinstance(resp_data, dict):
                # 1) 可配置响应提取路径（点分隔字段）
                if self.llm_config.response_extract:
                    return self._extract_response_field(resp_data, self.llm_config.response_extract)

                # 2) 默认常见结构兼容
                if "choices" in resp_data and isinstance(resp_data["choices"], list) and resp_data["choices"]:
                    first = resp_data["choices"][0]
                    if isinstance(first, dict):
                        if "text" in first:
                            return str(first["text"]).strip()
                        if "message" in first and isinstance(first["message"], dict) and "content" in first["message"]:
                            return str(first["message"]["content"]).strip()
                if "result" in resp_data and isinstance(resp_data["result"], str):
                    return resp_data["result"].strip()

            raise InferenceException("无法从LLM响应中提取文本")
        except error.HTTPError as e:
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = "<无法读取响应体>"
            raise InferenceException(f"LLM API 请求失败: {e.code}, {body}")
        except Exception as e:
            raise InferenceException(f"LLM API 调用失败: {str(e)}")

    def _extract_response_field(self, data: dict, path: str) -> str:
        """按照点分隔路径提取响应字段，路径示例：choices.0.text"""
        parts = [p for p in path.split(".") if p != ""]
        current = data
        for part in parts:
            if isinstance(current, list):
                try:
                    idx = int(part)
                    current = current[idx]
                except Exception:
                    raise InferenceException(f"响应路径解析失败: {path}")
            elif isinstance(current, dict):
                if part not in current:
                    raise InferenceException(f"响应路径不存在: {path}")
                current = current[part]
            else:
                raise InferenceException(f"响应路径类型不匹配: {path}")
        if isinstance(current, str):
            return current.strip()
        return str(current)

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
            # 云端/API优先（如果配置了llm.api_type且不是 local）
            if self.llm_config and self.llm_config.api_type and self.llm_config.api_type.lower() != "local":
                try:
                    reply = self._generate_via_api(full_prompt)
                    logger.debug("LLM API 生成完成", reply_length=len(reply))
                    return reply
                except InferenceException as api_error:
                    # API 异常时自动降级到本地生成，保证交互不中断
                    logger.warning("LLM API 调用失败，自动降级本地生成", error=str(api_error))

            # 本地模型调用（默认或API降级）
            self._load_local_model()

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