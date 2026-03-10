import pytest
import asyncio
import sys, os
# ensure package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from selrena._internal.agent import CommandGenerator
from selrena._internal.ports.agent import AgentPort


class DummyPort(AgentPort):
    def __init__(self):
        self.commands = []

    async def send_command(self, command: dict) -> None:
        self.commands.append(command)


def test_command_generator_sends():
    async def inner():
        port = DummyPort()
        gen = CommandGenerator(port)
        await gen.build("test_intent", [{"tool": "echo", "args": {"msg": "hi"}}])
        assert port.commands
        assert port.commands[0]["intent"] == "test_intent"
        assert port.commands[0]["tools"][0]["tool"] == "echo"
    asyncio.run(inner())
