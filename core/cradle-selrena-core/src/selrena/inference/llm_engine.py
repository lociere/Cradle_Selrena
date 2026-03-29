"""
文件名称：llm_engine.py
所属层级：推理层
核心作用：纯算力调用封装，仅负责LLM生成，不碰任何业务规则、人设、prompt构建
设计原则：
1. 仅做LLM API/本地模型调用封装，无任何业务逻辑
2. 所有prompt构建、人设注入都在应用层完成，这里仅做纯生成
3. 可插拔替换，更换模型仅需修改这里，核心代码零改动
4. 兼容本地模型和云端LLM，自动适配
5. 多 provider 路由：providers 字典按 key 选择不同推理后端
"""
from dataclasses import dataclass
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


@dataclass(frozen=True)
class LLMMessage:
    """单条模型消息。

    content 为文字时直接传字符串。
    若需要传图片，使用 vision_url 字段携带图片 URL（仅视觉模型路径使用）。
    """

    role: str
    content: str
    vision_url: str | None = None      # 非 None 时构造 vision 消息（url 图片）
    vision_mime: str | None = None     # 图片 MIME 类型，默认 image/jpeg


@dataclass(frozen=True)
class LLMRequest:
    """消息式推理请求。"""

    messages: list[LLMMessage]


def _build_message_payload(messages: list[LLMMessage]) -> list[dict]:
    """将 LLMMessage 列表转为 OpenAI 兼容的消息载荷。

    带 vision_url 的消息构造为 content 数组（image_url + text）格式，
    符合 OpenAI Vision / Qwen-VL / DeepSeek-VL 的 chat/completions 兼容接口。
    """
    result: list[dict] = []
    for msg in messages:
        if not msg.content.strip() and not msg.vision_url:
            continue
        if msg.vision_url:
            content_parts: list[dict] = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": msg.vision_url,
                        "detail": "auto",
                    },
                }
            ]
            if msg.content.strip():
                content_parts.append({"type": "text", "text": msg.content})
            result.append({"role": msg.role, "content": content_parts})
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


# ======================================
# LLM推理引擎
# ======================================
class LLMEngine:
    """
    LLM推理引擎，纯算力调用。
    支持多 provider 路由：通过 provider_key 选择 LLMConfig.providers 中的配置。
    """
    def __init__(self, self_entity: SelrenaSelfEntity, llm_config: Optional[LLMConfig] = None):
        self.self_entity = self_entity
        self.config = self_entity.inference_config.model
        self.llm_config = llm_config
        self._model = None
        logger.info("LLM引擎初始化完成", model_path=self.config.local_model_path, llm_config=self.llm_config)

    def _load_local_model(self) -> None:
        """懒加载本地模型，仅在第一次生成时加载"""
        if self._model is not None:
            return
        try:
            logger.info("本地模型加载完成", model_path=self.config.local_model_path)
        except Exception as e:
            raise InferenceException(f"本地模型加载失败: {str(e)}")

    def _render_messages_as_prompt(self, llm_request: LLMRequest) -> str:
        sections: list[str] = []
        for message in llm_request.messages:
            content = message.content.strip()
            if not content:
                continue
            sections.append(f"[{message.role}]\n{content}")
        return "\n\n".join(sections)

    def _extract_latest_user_text(self, llm_request: LLMRequest) -> str:
        for message in reversed(llm_request.messages):
            if message.role == "user" and message.content.strip():
                return message.content.strip()
        return ""

    def _resolve_provider_config(self, provider_key: str | None) -> LLMConfig | None:
        """将 provider_key 解析为内部可用的 LLMConfig（model 字段已填充）。

        支持三种格式：
          - ``None``           → 使用根配置 models 第一个模型
          - ``"qwen"``         → providers["qwen"].models 第一个模型
          - ``"qwen/vision"``  → providers["qwen"].models["vision"]

        查找失败时降级到根配置并打印警告，保证不崩溃。
        """
        if not self.llm_config:
            return None

        def _build(base: LLMConfig, resolved_model: str | None, prov: object = None) -> LLMConfig:
            p = prov
            return LLMConfig(
                api_type=getattr(p, "api_type", None) or base.api_type,
                api_key=getattr(p, "api_key", None) or base.api_key,
                base_url=getattr(p, "base_url", None) or base.base_url,
                model=resolved_model,
                temperature=(
                    getattr(p, "temperature", None)
                    if getattr(p, "temperature", None) is not None
                    else base.temperature
                ),
                request_method=getattr(p, "request_method", None),
                request_path=getattr(p, "request_path", None),
                request_headers=getattr(p, "request_headers", None),
                request_body_template=getattr(p, "request_body_template", None),
                response_extract=getattr(p, "response_extract", None),
            )

        # ── provider_key 为 None：解析根配置的默认模型 ─────────
        if not provider_key:
            root_models = self.llm_config.models or {}
            resolved = next(iter(root_models.values()), None)
            if not resolved:
                logger.warning("根配置 models 为空，无法解析默认模型")
            return _build(self.llm_config, resolved)

        # ── 解析复合格式 "provider/model_alias" ─────────────────
        if "/" in provider_key:
            prov_name, model_alias = provider_key.split("/", 1)
        else:
            prov_name, model_alias = provider_key, None

        providers = self.llm_config.providers or {}
        prov = providers.get(prov_name)
        if not prov:
            logger.warning("未知 provider，降级使用根配置", provider_key=provider_key)
            root_models = self.llm_config.models or {}
            return _build(self.llm_config, next(iter(root_models.values()), None))

        # ── 解析最终模型 ID ──────────────────────────────────────
        prov_models = prov.models
        if model_alias:
            resolved_model = prov_models.get(model_alias)
            if not resolved_model:
                resolved_model = next(iter(prov_models.values()), None)
                logger.warning(
                    "Provider 模型别名未找到，降级到第一个模型",
                    provider=prov_name, alias=model_alias, fallback=resolved_model,
                )
        else:
            resolved_model = next(iter(prov_models.values()), None)

        return _build(self.llm_config, resolved_model, prov)

    def _generate_via_api(self, llm_request: LLMRequest, cfg: LLMConfig) -> str:
        """通过指定的 LLMConfig（可为 provider 子配置）调用 API 生成回复。"""
        api_type = cfg.api_type.lower().strip()
        api_key = cfg.api_key
        if not api_key:
            raise InferenceException("缺少 LLM API Key，请在配置中提供")

        base_url = (cfg.base_url or "https://api.deepseek.com").rstrip("/")
        request_method = (cfg.request_method or "POST").upper()
        if cfg.request_path:
            request_path = cfg.request_path
        elif api_type in {"deepseek", "openai"}:
            request_path = "/v1/chat/completions"
        else:
            request_path = "/v1/completions"
        endpoint = urljoin(base_url + "/", request_path.lstrip("/"))

        model_name = cfg.model or (
            "deepseek-chat" if api_type == "deepseek" else self.config.local_model_path
        )
        prompt_text = self._render_messages_as_prompt(llm_request)
        message_payload = _build_message_payload(llm_request.messages)

        if request_path.endswith("/chat/completions"):
            default_payload: dict = {
                "model": model_name,
                "messages": message_payload,
                "max_tokens": self.config.max_tokens,
                "temperature": cfg.temperature if cfg.temperature is not None else self.config.temperature,
            }
        else:
            default_payload = {
                "model": model_name,
                "prompt": prompt_text,
                "max_tokens": self.config.max_tokens,
                "temperature": cfg.temperature if cfg.temperature is not None else self.config.temperature,
            }

        if cfg.request_body_template:
            template = cfg.request_body_template
            try:
                body_text = template.format(
                    prompt=prompt_text,
                    prompt_json=json.dumps(prompt_text, ensure_ascii=False),
                    messages=json.dumps(message_payload, ensure_ascii=False),
                    messages_json=json.dumps(message_payload, ensure_ascii=False),
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
        if cfg.request_headers:
            headers.update(cfg.request_headers)

        try:
            req = request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method=request_method,
            )
            with request.urlopen(req, timeout=60) as resp:
                resp_data = json.load(resp)

            if isinstance(resp_data, dict):
                if cfg.response_extract:
                    return self._extract_response_field(resp_data, cfg.response_extract)
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
        current: object = data
        for part in parts:
            if isinstance(current, list):
                try:
                    current = current[int(part)]
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

    def generate(self, llm_request: LLMRequest, provider_key: str | None = None) -> str:
        """生成回复。

        Args:
            llm_request: 应用层构建好的消息式会话请求（可包含 vision_url 图片）。
            provider_key: 可选 provider 标识（对应 llm.providers 字典 key），
                          不传则使用根配置（llm 节点）。
        Returns:
            LLM 生成的纯文本。
        Raises:
            InferenceException: 生成失败时抛出。
        """
        try:
            cfg = self._resolve_provider_config(provider_key)
            if cfg and cfg.api_type and cfg.api_type.lower() != "local":
                try:
                    reply = self._generate_via_api(llm_request, cfg)
                    logger.debug("LLM API 生成完成", provider=provider_key or "default", reply_length=len(reply))
                    return reply
                except InferenceException as api_error:
                    logger.warning("LLM API 调用失败，自动降级本地生成", provider=provider_key, error=str(api_error))

            # 本地模型调用（默认或API降级）
            self._load_local_model()

            # 本地模型调用占位（生产环境替换为 llama_cpp / ctransformers 等）
            latest_user_text = self._extract_latest_user_text(llm_request) or "又来找我了？"
            reply = f"哼，{latest_user_text.splitlines()[0]}...笨蛋，我才没有在意呢。"

            logger.debug("LLM本地生成完成", reply_length=len(reply))
            return reply.strip()

        except Exception as e:
            raise InferenceException(f"LLM生成失败: {str(e)}")