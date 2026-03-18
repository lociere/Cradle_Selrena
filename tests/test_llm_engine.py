import json

import pytest

from selrena.core.config import GlobalAIConfig
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.inference.llm_engine import LLMEngine, LLMMessage, LLMRequest


def make_minimal_config(llm_api_type: str = "local", **llm_kwargs: str) -> GlobalAIConfig:
    llm_conf = {"api_type": llm_api_type, "api_key": "test"} if llm_api_type != "local" else {"api_type": "local"}
    llm_conf.update(llm_kwargs)
    return GlobalAIConfig(
        persona={
            "base": {
                "name": "x",
                "nickname": "x",
                "role": "x",
                "apparent_age": "x",
                "gender": "x",
                "appearance": "x",
                "background": "x",
            },
            "core": {
                "personality": "x",
                "character_core": "x",
                "likes": "x",
            },
            "dialogue": {
                "dialogue_style": "x",
                "emotion_control": "x",
            },
            "safety": {
                "taboos": "x",
                "forbidden_phrases": [],
                "forbidden_regex": [],
            },
        },
        inference={
            "model": {
                "local_model_path": "/tmp",
                "max_tokens": 16,
                "temperature": 0.7,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
            },
            "life_clock": {
                "focused_interval_ms": 1000,
                "ambient_interval_ms": 2000,
                "default_mode": "standby",
                "focus_duration_ms": 10000,
                "ingress_debounce_ms": 600,
                "ingress_focused_debounce_ms": 300,
                "ingress_max_batch_messages": 4,
                "ingress_max_batch_items": 24,
                "summon_keywords": ["月见"],
                "focus_on_any_chat": False,
                "active_thought_modes": ["ambient", "focused"],
            },
            "memory": {
                "max_recall_count": 5,
                "retention_days": 30,
                "context_limit": 5,
                "conversation_window": 8,
                "summary_trigger_count": 12,
                "summary_keep_recent_count": 4,
                "summary_max_chars": 1200,
            },
            "multimodal": {
                "enabled": True,
                "strategy": "specialist_then_core",
                "max_items": 6,
                "core_model": "qwen-vl-core",
                "image_model": "qwen-image-specialist",
                "video_model": "qwen-video-specialist",
            },
            "action_stream": {
                "enabled": True,
                "channel": "live2d",
                "chunk_interval_ms": 80,
                "max_chunks_per_stream": 120,
                "emit_thinking_chunks": True,
                "emit_emotion_on_complete": True,
            },
        },
        llm=llm_conf,
    )


def test_llm_engine_local_mode_should_return_dummy_reply():
    config = make_minimal_config("local")
    self_entity = SelrenaSelfEntity(persona_config=config.persona, inference_config=config.inference)
    engine = LLMEngine(self_entity=self_entity, llm_config=config.llm)

    reply = engine.generate(LLMRequest(messages=[LLMMessage(role="user", content="hello")]))
    assert isinstance(reply, str)
    assert len(reply) > 0


@pytest.mark.parametrize("api_type", ["deepseek", "openai", "anthropic"])
def test_llm_engine_api_mode_requires_api_key(api_type: str):
    config = make_minimal_config(api_type)
    self_entity = SelrenaSelfEntity(persona_config=config.persona, inference_config=config.inference)
    engine = LLMEngine(self_entity=self_entity, llm_config=config.llm)

    # 引擎会自动降级，不应抛出异常
    assert isinstance(
        engine.generate(LLMRequest(messages=[LLMMessage(role="user", content="hello")])),
        str,
    )


def test_llm_engine_api_mode_happy_path(monkeypatch: pytest.MonkeyPatch):
    """验证 API 模式调用会正确解析不同格式的返回体。"""

    captured = {}

    class FakeResponse:
        def __init__(self, data: bytes):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request_obj, timeout=None):
        captured["request"] = request_obj
        # 模拟 OpenAI / DeepSeek 典型返回格式
        payload = {"choices": [{"text": "fake response"}]}
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    # 使用 **kwargs 传入 request_body_template
    # 注意：由于 llm_engine 使用 str.format，JSON 的大括号需要转义为 {{ 和 }}。
    # prompt_json 会自动做 JSON 转义，避免多行消息导致模板失效。
    config = make_minimal_config(
        "deepseek",
        request_body_template='{{"model":"{model}","prompt":{prompt_json},"temperature":{temperature}}}'
    )
    
    self_entity = SelrenaSelfEntity(persona_config=config.persona, inference_config=config.inference)
    engine = LLMEngine(self_entity=self_entity, llm_config=config.llm)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    reply = engine.generate(
        LLMRequest(
            messages=[
                LLMMessage(role="system", content="system prompt"),
                LLMMessage(role="user", content="hello"),
            ]
        )
    )

    assert reply == "fake response"
    assert captured["request"].full_url.endswith("/chat/completions")
    body = json.loads(captured["request"].data.decode("utf-8"))
    assert "system prompt" in body["prompt"]
    assert "hello" in body["prompt"]

