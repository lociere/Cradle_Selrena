import asyncio
import os
import sys

# ensure src on path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'src'))
if root not in sys.path:
    sys.path.insert(0, root)

import pytest
from selrena.core.ai_service import SimpleAIService


async def _run_service_start_stop(service: SimpleAIService):
    await service.start()
    assert service.is_running
    await service.process_message('user1', 'hello')
    await service.disconnect() if hasattr(service, 'disconnect') else None


def test_simple_service_start_stop():
    service = SimpleAIService()
    # should be able to start and stop without errors
    asyncio.run(_run_service_start_stop(service))

async def _run_service_response(svc: SimpleAIService):
    await svc.start()
    reply = await svc.process_message('u', 'test message')
    assert isinstance(reply, str)
    await svc.disconnect() if hasattr(svc, 'disconnect') else None


def test_simple_service_response():
    svc = SimpleAIService()
    asyncio.run(_run_service_response(svc))
