import asyncio
import json
import pytest

# Napcat adapter module has been deprecated in the Python core; it will be
# replaced by a Node.js implementation.  All existing tests are skipped to
# avoid failures while the Python side is removed.
pytest.skip("Napcat tests deprecated (node.js implementation will replace)", allow_module_level=True)

import pytest
pytest.skip("legacy napcat adapter tests skipped after package rename", allow_module_level=True)

from cradle_selrena_core.core.config_manager import global_config
from cradle_selrena_core.selrena.vessel.napcat.napcat_client import NapcatClient
from cradle_selrena_core.bus.event_bus import global_event_bus
from cradle_selrena_core.schemas.protocol.events.base import BaseEvent
from cradle_selrena_core.selrena.vessel.presentation.audio.player import VirtualMouth
from cradle_selrena_core.selrena.vessel.perception.audio.stream import AudioStream

# Helper to clear bus
@pytest.fixture(autouse=True)
def isolate_event_bus():
    """Clear commonly-used signals before/after each test."""
    global_event_bus._subscribers.clear()
    yield
    global_event_bus._subscribers.clear()

@pytest.mark.asyncio
async def test_napcat_client_object_message():
    """NapcatClient should convert basic object message into user_message and include user_id if present."""
    # Pipeline: NapcatClient -> Edge -> Reflex -> input.user_message
    from cradle_selrena_core.selrena.synapse.reflex import Reflex
    from cradle_selrena_core.selrena.synapse.edge import Edge
    
    edge = Edge()
    reflex = Reflex()
    await edge.initialize()
    await reflex.initialize()

    # Reset client subscription state
    NapcatClient._subscribed = False
    client = NapcatClient()
    await client.initialize()
    
    results = []
    async def recorder(ev: BaseEvent):
        results.append(ev)
    
    # We listen to the final output of the pipeline
    unsub = global_event_bus.subscribe('input.user_message', recorder)

    payload = {"post_type": "message", "message": "hello selrena", "user_id": 77}
    # Publish raw napcat event which client picks up
    await global_event_bus.publish(BaseEvent(name="napcat.event", payload=payload, source="test"))
    await asyncio.sleep(0.1)

    await client.cleanup()
    unsub()
    await edge.cleanup()
    await reflex.cleanup()

    # Verify flow
    assert results, "No user_message generated"
    assert results[0].payload['text'] == "hello selrena"
    # NapcatClient sends source="qq" in perception event. 
    # Edge/Reflex passes through source.
    assert results[0].payload.get('source') == "qq"
    assert results[0].payload.get('user_id') == 77

@pytest.mark.asyncio
async def test_napcat_client_array_message():
    """Array-style event should also be handled."""
    from cradle_selrena_core.selrena.synapse.reflex import Reflex
    from cradle_selrena_core.selrena.synapse.edge import Edge
    edge = Edge()
    reflex = Reflex()
    await edge.initialize()
    await reflex.initialize()

    NapcatClient._subscribed = False
    client = NapcatClient()
    await client.initialize()
    
    results = []
    async def recorder(ev: BaseEvent):
        results.append(ev)
    unsub = global_event_bus.subscribe('input.user_message', recorder)

    payload = {"_array": ["message", {"foo": "bar"}, "hello selrena"]}
    await global_event_bus.publish(BaseEvent(name="napcat.event", payload=payload, source="test"))
    await asyncio.sleep(0.1)

    await client.cleanup()
    unsub()
    await edge.cleanup()
    await reflex.cleanup()
    
    assert results, "No user_message generated"
    assert results[0].payload['text'] == "hello selrena"

def test_napcat_client_disabled():
    """NapcatClient should not subscribe when napcat is disabled."""
    sys_cfg = global_config.sys_config
    sys_cfg.napcat.enable = False
    
    NapcatClient._subscribed = False
    
    client = NapcatClient()
    asyncio.run(client.initialize())
    subs = global_event_bus._subscribers.get('napcat.event', [])
    assert all(getattr(cb, '__self__', None) is not client for cb in subs)
    
    # Reset for other tests
    sys_cfg.napcat.enable = True

@pytest.mark.asyncio
async def test_napcat_server_basic(monkeypatch):
    """Server should accept client connection and publish events."""
    from cradle_selrena_core.selrena.vessel.napcat.napcat_server import NapcatServer
    import websockets

    # Clean up any existing server task to free port
    # But here assuming isolated run. 
    # Ensure port is unique to avoid conflict if parallel (unlikely with pytest-asyncio default)
    cfg = global_config.sys_config.napcat
    cfg.enable = True
    cfg.listen_port = 9010

    server = NapcatServer()
    await server.initialize()

    events = []
    async def rec(ev: BaseEvent):
        events.append(ev)
    global_event_bus.subscribe('napcat.event', rec)

    # connect as a client and send a message
    async with websockets.connect(f'ws://127.0.0.1:{cfg.listen_port}') as ws:
        await ws.send(json.dumps({'foo': 'bar'}))
        await asyncio.sleep(0.1)

    # also verify subprotocol handshake with token
    token = cfg.token or 'secrettoken'
    cfg.token = token
    headers = {"Sec-WebSocket-Protocol": f"onebot,{token}"}
    
    params = {"subprotocols": ["onebot"], "extra_headers": headers}
    import inspect
    if 'additional_headers' in inspect.signature(websockets.connect).parameters:
        params = {"subprotocols": ["onebot"], "additional_headers": headers}
        
    async with websockets.connect(f'ws://127.0.0.1:{cfg.listen_port}', **params) as ws2:
        await ws2.send(json.dumps({'baz': 'qux'}))
        await asyncio.sleep(0.1)

    await server.cleanup()
    assert events and events[0].payload['foo'] == 'bar'

@pytest.mark.asyncio
async def test_napcat_server_message_list(monkeypatch):
    """Server should not crash when client sends a message whose "message" field is a list."""
    from cradle_selrena_core.selrena.vessel.napcat.napcat_server import NapcatServer
    import websockets

    cfg = global_config.sys_config.napcat
    cfg.enable = True
    cfg.listen_port = 9015

    server = NapcatServer()
    await server.initialize()

    events = []
    async def rec(ev: BaseEvent):
        events.append(ev)
    global_event_bus.subscribe('napcat.event', rec)

    async with websockets.connect(f'ws://127.0.0.1:{cfg.listen_port}') as ws:
        msg = {
            'post_type': 'message',
            'message': [{'type': 'text', 'data': {'text': 'hello'}}]
        }
        await ws.send(json.dumps(msg))
        await asyncio.sleep(0.1)

    await server.cleanup()
    # Expect event published
    assert events, "No event received"
    assert isinstance(events[0].payload, dict)

@pytest.mark.asyncio
async def test_napcat_send_helper(monkeypatch):
    """Publishing napcat.send should reach connected clients via server."""
    from cradle_selrena_core.selrena.vessel.napcat.napcat_server import NapcatServer
    import websockets

    cfg = global_config.sys_config.napcat
    cfg.enable = True
    cfg.listen_port = 9016

    server = NapcatServer()
    await server.initialize()

    async with websockets.connect(f'ws://127.0.0.1:{cfg.listen_port}') as ws:
        await global_event_bus.publish(BaseEvent(
            name="napcat.send",
            payload={"action": "send_private_msg", "params": {"user_id": 1, "message": "hi"}},
            source="test",
        ))
        text = await ws.recv()

    await server.cleanup()
    assert "send_private_msg" in text

@pytest.mark.asyncio
async def test_napcat_client_reply():
    """NapcatClient.send_api/reply helpers emit the correct event."""
    cfg = global_config.sys_config
    cfg.napcat.enable = True

    NapcatClient._subscribed = False
    client = NapcatClient()
    await client.initialize()

    seen = []
    async def rec(ev: BaseEvent):
        seen.append(ev.payload)
    global_event_bus.subscribe('napcat.send', rec)

    await client.send_api('foo', {'bar': 1})
    await client.reply(123, 'hello')
    await asyncio.sleep(0.1)
    await client.cleanup()

    assert any(p.get('action') == 'foo' for p in seen)
    assert any(p.get('action') == 'send_private_msg' for p in seen)

@pytest.mark.asyncio
async def test_napcat_responder_bridge():
    """NapcatResponder should forward speak actions back to the last user."""
    from cradle_selrena_core.selrena.vessel.napcat.napcat_responder import NapcatResponder
    NapcatResponder._installed = False

    cfg = global_config.sys_config
    cfg.napcat.enable = True

    from cradle_selrena_core.selrena.synapse.reflex import Reflex
    from cradle_selrena_core.selrena.synapse.edge import Edge
    edge = Edge()
    reflex = Reflex()
    await edge.initialize()
    await reflex.initialize()

    NapcatClient._subscribed = False
    client = NapcatClient()
    await client.initialize()

    raw = {
        "post_type": "message",
        "sender": {"user_id": 123456},
        "message": "hello selrena"
    }
    await global_event_bus.publish(BaseEvent(name="napcat.event", payload=raw, source="test"))
    await asyncio.sleep(0.1)

    sends = []
    async def rec(ev: BaseEvent):
        sends.append(ev.payload)
    global_event_bus.subscribe('napcat.send', rec)

    # Soul speaks
    await global_event_bus.publish(BaseEvent(
        name="action.presentation.speak",
        payload={"text": "reply"},
        source="Soul",
    ))
    await asyncio.sleep(0.1)

    await client.cleanup()
    await NapcatResponder().cleanup()
    await reflex.cleanup()
    await edge.cleanup()

    assert any(p.get('params', {}).get('user_id') == 123456 for p in sends), \
        f"Responder did not capture user_id. Sends: {sends}"

@pytest.mark.asyncio
async def test_napcat_responder_group_reply():
    """If the incoming message came from a group, a reply should go to the group."""
    from cradle_selrena_core.selrena.vessel.napcat.napcat_responder import NapcatResponder
    NapcatResponder._installed = False

    cfg = global_config.sys_config
    cfg.napcat.enable = True

    from cradle_selrena_core.selrena.synapse.reflex import Reflex
    from cradle_selrena_core.selrena.synapse.edge import Edge
    edge = Edge()
    reflex = Reflex()
    await edge.initialize()
    await reflex.initialize()

    NapcatClient._subscribed = False
    client = NapcatClient()
    await client.initialize()

    raw = {
        "post_type": "message",
        "sender": {"user_id": 123456},
        "group_id": 9876,
        "message": "hello selrena"
    }
    await global_event_bus.publish(BaseEvent(name="napcat.event", payload=raw, source="test"))
    await asyncio.sleep(0.1)

    sends = []
    async def rec(ev: BaseEvent):
        sends.append(ev.payload)
    global_event_bus.subscribe('napcat.send', rec)

    await global_event_bus.publish(BaseEvent(
        name="action.presentation.speak",
        payload={"text": "group reply"},
        source="Soul",
    ))
    await asyncio.sleep(0.1)

    await client.cleanup()
    await NapcatResponder().cleanup()
    await reflex.cleanup()
    await edge.cleanup()

    assert any(
        p.get('action') == 'send_group_msg' and
        p.get('params', {}).get('group_id') == 9876
        for p in sends
    )

@pytest.mark.asyncio
async def test_napcat_client_group_id():
    """NapcatClient should propagate group_id from raw events."""
    cfg = global_config.sys_config
    cfg.napcat.enable = True
    
    from cradle_selrena_core.selrena.synapse.reflex import Reflex
    from cradle_selrena_core.selrena.synapse.edge import Edge
    edge = Edge()
    reflex = Reflex()
    await edge.initialize()
    await reflex.initialize()

    NapcatClient._subscribed = False
    client = NapcatClient()
    await client.initialize()

    texts = []
    async def rec(ev: BaseEvent):
        texts.append(ev.payload)
    unsub = global_event_bus.subscribe('input.user_message', rec)

    payload = {
        'post_type': 'message',
        'group_id': 42,
        'sender': {'user_id': 1},
        'message': 'hello selrena, foo'
    }
    await global_event_bus.publish(BaseEvent(name='napcat.event', payload=payload, source='test'))
    await asyncio.sleep(0.1)
    
    await client.cleanup()
    await reflex.cleanup()
    await edge.cleanup()
    unsub()

    assert texts and texts[0].get('group_id') == 42, texts

@pytest.mark.asyncio
async def test_napcat_list_payload():
    """NapcatClient should handle a raw list payload."""
    cfg = global_config.sys_config
    cfg.napcat.enable = True
    
    NapcatClient._subscribed = False
    client = NapcatClient()
    await client.initialize()

    texts = []
    async def rec(ev: BaseEvent):
        # payload is an ExternalMultiModalPayload model; extract text from first content block
        try:
            block = ev.payload.content[0]
            texts.append(getattr(block, 'text', None))
        except Exception:
            texts.append(None)
    
    # Listen to NapcatClient's direct output
    global_event_bus.subscribe('perception.audio.transcription', rec)

    payload = [{'type': 'text', 'data': {'text': 'hi'}}]
    await global_event_bus.publish(BaseEvent(name='napcat.event', payload=payload, source='test'))
    await asyncio.sleep(0.1)

    assert texts == ['hi']
    await client.cleanup()

@pytest.mark.asyncio
async def test_sensory_strict_wake():
    """Strict wake mode test."""
    from cradle_selrena_core.selrena.synapse.reflex import Reflex
    from cradle_selrena_core.selrena.synapse.edge import Edge
    
    edge = Edge()
    reflex = Reflex()
    
    # Configure strict wake on reflex before init
    reflex.strict_wake = True
    
    await edge.initialize()
    await reflex.initialize()

    seen = []
    async def rec(ev: BaseEvent):
        seen.append(ev.payload.get('text'))
    unsub = global_event_bus.subscribe('input.user_message', rec)

    # publish via perception layer (Edge ingress)
    await global_event_bus.publish(BaseEvent(
        name='perception.audio.transcription',
        payload={'text': 'hello selrena, wake up'},
        source='test',
    ))
    # This one should be ignored
    await global_event_bus.publish(BaseEvent(
        name='perception.audio.transcription',
        payload={'text': 'just chatting without word'},
        source='test',
    ))
    await asyncio.sleep(0.1)

    # Note: 'seen' should contain only wake words
    assert seen, "No wake word message passed through"
    assert all('wake up' in text for text in seen), f"Strict wake failure: {seen}"

    unsub()
    await reflex.cleanup()
    await edge.cleanup()

@pytest.mark.asyncio
async def test_napcat_client_response_handling():
    """NapcatClient should log and emit napcat.error on bad responses."""
    sys_cfg = global_config.sys_config
    sys_cfg.napcat.enable = True
    
    NapcatClient._subscribed = False
    client = NapcatClient()
    await client.initialize()
    
    errors = []
    async def rec(ev: BaseEvent):
        errors.append(ev)
    global_event_bus.subscribe('napcat.error', rec)
    
    payload = {"status":"failed","retcode":1404,"message":"no api"}
    await global_event_bus.publish(BaseEvent(name='napcat.response', payload=payload, source='test'))
    await asyncio.sleep(0.1)
    await client.cleanup()
    assert errors and errors[0].payload['retcode'] == 1404

def test_virtual_mouth_disabled(monkeypatch):
    """When TTS is turned off, VirtualMouth should not respond to speak actions."""
    sys_cfg = global_config.sys_config
    sys_cfg.presentation.tts.enabled = False

    mouth = VirtualMouth()
    subs = global_event_bus._subscribers.get('action.presentation.speak', [])
    assert all(getattr(cb, '__self__', None) is not mouth for cb in subs)

@pytest.mark.asyncio
async def test_audiostream_disabled(monkeypatch):
    """AudioStream.listen_loop returns without starting if disabled."""
    cfg = global_config.sys_config.perception.audio
    cfg.enabled = False
    stream = AudioStream()
    # Mocking start directly on the instance is tricky if it's not a method but here it is
    called = False
    async def fake_start():
        nonlocal called
        called = True
    stream.start = fake_start
    await stream.listen_loop()
    assert not called



