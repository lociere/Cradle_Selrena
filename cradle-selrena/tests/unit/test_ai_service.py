import asyncio
import os
import sys

# ensure src on path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'src'))
if root not in sys.path:
    sys.path.insert(0, root)

import pytest
from selrena.core.ai_service import SimpleAIService, AIService


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


def test_ai_service_external_message(tmp_path):
    """AIService should accept external-style payload and still process it without using memory."""
    # create a real AIService with HTTP transport pointing to unused port (not actually connecting)
    cfg = tmp_path / "cfg"
    data = tmp_path / "data"
    service = AIService(event_bus_host="localhost", event_bus_port=12345,
                        config_dir=str(cfg), data_dir=str(data))
    payload = {"content": [{"type": "text", "text": "external"}], "is_external_source": True}
    async def run():
        # container already created in constructor
        await service.ai_container.initialize(llm_config={}, use_local_llm=False)
        # subscribe internal event
        events = []
        from selrena.utils.event_bus import subscribe
        unsub = subscribe("ai.response", lambda r: events.append(r))
        await service._handle_user_input({"payload": payload})
        unsub()
        # ensure internal event fired
        assert events, "内部事件未发布"
    asyncio.run(run())


def test_chat_history_construction():
    from selrena.schemas.chat import ChatHistory, Message
    hist = ChatHistory()
    hist.add_message("user", "hello")
    hist.messages.append(Message(role="assistant", content="hi"))
    assert len(hist.messages) == 2
    assert hist.messages[0].role == "user"
    assert isinstance(hist.messages[1].content, str)


def test_content_block_and_message_validation():
    from selrena.schemas.multimodal import TextContent, ImageContent, ContentBlock
    from selrena.schemas.chat import Message
    t = TextContent(text="foo")
    i = ImageContent(image_url={"url": "http://img"})
    assert isinstance(t, ContentBlock)
    assert isinstance(i, ContentBlock)
    m = Message(role="user", content=[t, i])
    assert m.content[0].type == "text"


def test_kernel_adapter_speak_event(monkeypatch):
    from selrena.adapters import KernelAdapter
    events = []
    class DummyBus:
        async def publish(self, action):
            events.append(action)
    adapter = KernelAdapter(event_bus=DummyBus())
    import asyncio
    asyncio.run(adapter.send_message("hello", emotion="joy"))
    assert events and events[0].action_type == "speak"
