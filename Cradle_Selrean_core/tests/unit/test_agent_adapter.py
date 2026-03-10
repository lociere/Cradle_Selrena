import pytest
import asyncio
import sys, os

# make src package importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from selrena._internal.adapters import KernelAdapter
from selrena._internal.schemas.events import MCPCommandAction


class DummyBus:
    def __init__(self):
        self.published = []

    async def publish(self, action):
        self.published.append(action)


def test_kernel_adapter_send_command():
    async def inner():
        bus = DummyBus()
        adapter = KernelAdapter(event_bus=bus)
        cmd = {"foo": "bar"}
        await adapter.send_command(cmd)
        assert bus.published, "command not sent"
        assert isinstance(bus.published[0], MCPCommandAction)
        assert bus.published[0].command == cmd
    asyncio.run(inner())
