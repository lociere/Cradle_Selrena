import asyncio
import os
import sys

# ensure path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'src'))
if root not in sys.path:
    sys.path.insert(0, root)

import pytest
from selrena.core.event_bus_client import SimpleEventBusClient, EventBusClient, EventBusTransport


async def _event_bus_send_receive(client, received):
    await client.connect()
    await client.send_event('foo', {'bar': 1})
    await asyncio.sleep(0.1)
    await client.disconnect()


def test_simple_event_bus_send_receive():
    client = SimpleEventBusClient()
    received = {}
    
    def handler(ev):
        received['event'] = ev
    client.register_handler('foo', handler)
    asyncio.run(_event_bus_send_receive(client, received))
    assert 'event' in received
    assert received['event']['payload']['bar'] == 1


async def _register_handler_and_listen_coroutine(client):
    called = False
    async def handler(ev):
        nonlocal called
        called = True
    client.register_handler('test', handler)
    await client.connect()
    await client.send_event('test', {})
    await asyncio.sleep(0.1)
    await client.disconnect()
    assert called


def test_register_handler_and_listen():
    client = SimpleEventBusClient()
    asyncio.run(_register_handler_and_listen_coroutine(client))
