import pytest
import asyncio
import sys, os
from pathlib import Path
import shutil
# make src package available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

def make_temp_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d

from selrena.container import AIContainer


def test_basic_chat_flow(tmp_path):
    async def inner():
        # prepare temporary config and data directories
        config_dir = make_temp_dir(tmp_path, "config")
        data_dir = make_temp_dir(tmp_path, "data")

        container = AIContainer(config_dir, data_dir)
        # initialize with no API key -> DummyLLM
        await container.initialize({}, use_local_llm=False)

        response1 = await container.chat("Hello")
        assert "模拟" in response1 or response1.startswith("这是一个模拟回复"), "DummyLLM response expected"

        # second message should still produce something and may write memory files
        response2 = await container.chat("How are you?")
        assert response2, "Should return some text"

        # verify memory files created
        mem_files = list((data_dir / "memory").glob("*.json"))
        assert mem_files, "Conversation memories should be saved"

        # cleanup resources
        await container.cleanup()
    asyncio.run(inner())
