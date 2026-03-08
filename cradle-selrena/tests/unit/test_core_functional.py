import asyncio
import os
import sys
from pathlib import Path

# ensure src is on path for tests
root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'src'))
if root not in sys.path:
    sys.path.insert(0, root)

import pytest

from selrena.container import AIContainer
from selrena.inference.llm import DummyLLM as _DummyLLM


async def _basic_chat_coroutine(cfg_dir, data_dir):
    container = AIContainer(config_dir=cfg_dir, data_dir=data_dir)
    # initialize without API key to trigger DummyLLM
    await container.initialize(llm_config={}, use_local_llm=False)

    reply = await container.chat("你好")
    assert isinstance(reply, str)
    assert "模拟" in reply or "这是一个模拟" in reply

    # memory files should have been created
    mem_files = list((data_dir / "memory").glob("*.json"))
    assert mem_files, "应该有记忆文件产生"

    await container.cleanup()


def test_basic_chat(tmp_path):
    # use temporary dirs for config and data
    cfg_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    cfg_dir.mkdir()
    data_dir.mkdir()

    asyncio.run(_basic_chat_coroutine(cfg_dir, data_dir))


async def _persona_save_and_load_coroutine(cfg_dir):
    from selrena.adapters import PersonaAdapter
    from selrena.domain.persona import Persona
    pa = PersonaAdapter(cfg_dir)
    persona = Persona(name="test", identity="我是测试")
    await pa.save_persona(persona)
    loaded = await pa.load_persona("test")
    assert loaded.name == "test"
    assert loaded.identity == "我是测试"


def test_persona_save_and_load(tmp_path):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    asyncio.run(_persona_save_and_load_coroutine(cfg_dir))
