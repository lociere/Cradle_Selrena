import json

import pytest

from selrena.core.config import GlobalAIConfig
from selrena.domain.self.self_entity import SelrenaSelfEntity
from selrena.inference.llm_engine import LLMEngine


def make_minimal_config(llm_api_type: str = "local") -> GlobalAIConfig:
    return GlobalAIConfig(
        persona={
            "base": {
                "name": "x",
                "nickname": "x",
                "age": 1,
                "gender": "x",
                "core_identity": "x",
                "self_description": "x",
            },
            "character_traits": {},
            "behavior_rules": [],
            "boundary_limits": [],
        },
        inference={
            "model": {
                "local_model_path": "/tmp",
                "max_tokens": 16,
                "temperature": 0.7,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
            },
            "life_clock": {"thought_interval_ms": 1000},
            "memory": {"max_recall_count": 5, "retention_days": 30},
        },
        llm={"api_type": llm_api_type, "api_key": "test"} if llm_api_type != "local" else {"api_type": "local"},
    )


def test_llm_engine_local_mode_should_return_dummy_reply():
    config = make_minimal_config("local")
    self_entity = SelrenaSelfEntity(persona_config=config.persona, inference_config=config.inference)
    engine = LLMEngine(self_entity=self_entity, llm_config=config.llm)

    reply = engine.generate("hello")
    assert isinstance(reply, str)
    assert len(reply) > 0


@pytest.mark.parametrize("api_type", ["deepseek", "openai", "anthropic"])
def test_llm_engine_api_mode_requires_api_key(api_type: str):
    config = make_minimal_config(api_type)
    self_entity = SelrenaSelfEntity(persona_config=config.persona, inference_config=config.inference)
    engine = LLMEngine(self_entity=self_entity, llm_config=config.llm)

    with pytest.raises(Exception):
        # 由于不会向真实 API 发出请求，这里仅确保有 key 且不报错（key 丢失会抛出）
        engine.generate("hello")


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

    config = make_minimal_config("deepseek")
    # 使用自定义 body 模板验证可配置性
    config.llm.request_body_template = '{"model":"{model}","prompt":"{prompt}","temperature":{temperature}}'
    self_entity = SelrenaSelfEntity(persona_config=config.persona, inference_config=config.inference)
    engine = LLMEngine(self_entity=self_entity, llm_config=config.llm)

    monkeypatch.setattr("selrena.inference.llm_engine.request.urlopen", fake_urlopen)
    reply = engine.generate("hello")

    assert reply == "fake response"
    assert captured["request"].full_url.endswith("/v1/completions")
    body = json.loads(captured["request"].data.decode("utf-8"))
    assert body["prompt"] == "hello"
