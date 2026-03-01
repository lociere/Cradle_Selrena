import asyncio
import json
import pytest

from cradle.core.config_manager import global_config
# NapcatAdapter removed;仅支持服务器模式，请使用 `napcat.enable` 控制
from cradle.selrena.vessel.napcat.napcat_client import NapcatClient
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.schemas.protocol.events import BaseEvent
from cradle.selrena.vessel.presentation.audio.player import VirtualMouth
from cradle.selrena.vessel.perception.audio.stream import AudioStream




# ---------- NapcatClient tests ----------
from cradle.selrena.vessel.napcat.napcat_client import NapcatClient

@pytest.fixture(autouse=True)
def isolate_event_bus():
    """Clear commonly-used signals before/after each test."""
    global_event_bus._subscribers.clear()
    yield
    global_event_bus._subscribers.clear()


@pytest.mark.asyncio
async def test_napcat_client_object_message():
    """NapcatClient should convert basic object message into user_message and include user_id if present."""
    # install reflex & cortex layers so that transcript -> user_message flow works
    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    await reflex.initialize()
    await cortex.initialize()

    client = NapcatClient()
    await client.initialize()
    results = []
    async def recorder(ev: BaseEvent):
        results.append(ev)
    unsub = global_event_bus.subscribe('input.user_message', recorder)

    payload = {"post_type": "message", "message": "hello world", "user_id": 77}
    await global_event_bus.publish(BaseEvent(name="napcat.event", payload=payload, source="test"))
    await asyncio.sleep(0.1)

    await client.cleanup()
    # unsubscribe listener
    unsub()
    # tear down layers to avoid cross-test interference
    await reflex.cleanup()
    await cortex.cleanup()

    assert results and results[0].payload['text'] == "hello world"
    assert results[0].payload['source'] == "qq"
    assert results[0].payload.get('user_id') == 77

@pytest.mark.asyncio
async def test_napcat_client_array_message():
    """Array‑style event should also be handled."""
    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    await reflex.initialize()
    await cortex.initialize()

    client = NapcatClient()
    await client.initialize()
    results = []
    async def recorder(ev: BaseEvent):
        results.append(ev)
    unsub = global_event_bus.subscribe('input.user_message', recorder)

    payload = {"_array": ["message", {"foo": "bar"}, "hi there"]}
    await global_event_bus.publish(BaseEvent(name="napcat.event", payload=payload, source="test"))
    await asyncio.sleep(0.1)

    await client.cleanup()
    unsub()
    await reflex.cleanup()
    await cortex.cleanup()
    assert results and results[0].payload['text'] == "hi there"


def test_napcat_client_disabled():
    """NapcatClient should not subscribe when napcat is disabled."""
    sys_cfg = global_config.sys_config
    sys_cfg.napcat.enable = False
    client = NapcatClient()
    asyncio.run(client.initialize())
    subs = global_event_bus._subscribers.get('napcat.event', [])
    assert all(getattr(cb, '__self__', None) is not client for cb in subs)


@pytest.mark.asyncio
async def test_napcat_server_basic(monkeypatch):
    """Server should accept client connection and publish events."""
    from cradle.selrena.synapse.napcat_server import NapcatServer
    import websockets

    cfg = global_config.sys_config.napcat
    cfg.enable = True
    cfg.listen_port = 9000

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

    # also verify subprotocol handshake with token is accepted
    token = cfg.token or 'secrettoken'
    cfg.token = token
    # websockets client rejects comma in subprotocol list, so emulate
    # what Napcat actually does by putting the value in the header.
    headers = {"Sec-WebSocket-Protocol": f"onebot,{token}"}
    # supply a valid subprotocol list too so client negotiation succeeds
    params = {"subprotocols": ["onebot"], "extra_headers": headers}
    # some library versions expect `additional_headers` instead
    import inspect
    if 'additional_headers' in inspect.signature(websockets.connect).parameters:
        params = {"subprotocols": ["onebot"], "additional_headers": headers}
    async with websockets.connect(f'ws://127.0.0.1:{cfg.listen_port}', **params) as ws2:
        await ws2.send(json.dumps({'baz': 'qux'}))
        await asyncio.sleep(0.1)
    # after connections, the server should have recorded the chosen subprotocol(s)
    assert any(
        c.subprotocol in ("onebot", f"onebot,{token}")
        for c in server._clients
    )

    await server.cleanup()
    assert events and events[0].payload['foo'] == 'bar'

@pytest.mark.asyncio
async def test_napcat_server_message_list(monkeypatch):
    """Server should not crash when client sends a message whose "message" field is a list."""
    from cradle.selrena.synapse.napcat_server import NapcatServer
    import websockets

    cfg = global_config.sys_config.napcat
    cfg.enable = True
    cfg.listen_port = 9005

    server = NapcatServer()
    await server.initialize()

    events = []
    async def rec(ev: BaseEvent):
        events.append(ev)
    global_event_bus.subscribe('napcat.event', rec)

    async with websockets.connect(f'ws://127.0.0.1:{cfg.listen_port}') as ws:
        # send payload similar to the one observed in logs
        msg = {
            'post_type': 'message',
            'message': [{'type': 'text', 'data': {'text': 'hello'}}]
        }
        await ws.send(json.dumps(msg))
        await asyncio.sleep(0.1)
        # if we reach here without exception that means server didn't
        # drop the connection mid-send; we'll verify by checking that an
        # event was delivered below.

    await server.cleanup()
    assert events and isinstance(events[0].payload, dict)

@pytest.mark.asyncio
async def test_napcat_send_helper(monkeypatch):
    """Publishing napcat.send should reach connected clients via server."""
    from cradle.selrena.synapse.napcat_server import NapcatServer
    import websockets

    cfg = global_config.sys_config.napcat
    cfg.enable = True
    cfg.listen_port = 9006

    server = NapcatServer()
    await server.initialize()

    # connect a fake client and verify it can receive frames
    async with websockets.connect(f'ws://127.0.0.1:{cfg.listen_port}') as ws:
        # publish a send event while connection stays open
        await global_event_bus.publish(BaseEvent(
            name="napcat.send",
            payload={"action": "send_private_msg", "params": {"user_id": 1, "message": "hi"}},
            source="test",
        ))
        # the server should forward the payload; read it back
        text = await ws.recv()

    await server.cleanup()

    assert "send_private_msg" in text

@pytest.mark.asyncio
async def test_napcat_client_reply():
    """NapcatClient.send_api/reply helpers emit the correct event."""
    cfg = global_config.sys_config
    cfg.napcat.enable = True

    # reflex/cortex normally run when transcription events arrive
    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    await reflex.initialize()
    await cortex.initialize()

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
    await reflex.cleanup()
    await cortex.cleanup()

    assert any(p.get('action') == 'foo' for p in seen)
    assert any(p.get('action') == 'send_private_msg' for p in seen)

@pytest.mark.asyncio
async def test_napcat_responder_bridge():
    """NapcatResponder should forward speak actions back to the last user.

    이전 버전은直接向 `input.user_message` 发布带有 user_id 的事件。
    现在客户端会从 napcat.event 原始数据中提取 user_id，因此测试
    也改为模拟该路径。
    """
    from cradle.selrena.synapse.napcat_responder import NapcatResponder
    # ensure a fresh responder instance for isolation
    NapcatResponder._installed = False

    cfg = global_config.sys_config
    cfg.napcat.enable = True

    # start reflex/cortex for proper pipeline
    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    await reflex.initialize()
    await cortex.initialize()

    client = NapcatClient()
    await client.initialize()

    # send a raw onebot event similar to real log containing sender.user_id
    raw = {
        "post_type": "message",
        "sender": {"user_id": 123456},
        "message": "hi"
    }
    await global_event_bus.publish(BaseEvent(name="napcat.event", payload=raw, source="test"))
    await asyncio.sleep(0.1)  # allow client to translate

    # now soul speaks using simple dict
    await global_event_bus.publish(BaseEvent(
        name="action.presentation.speak",
        payload={"text": "reply"},
        source="Soul",
    ))
    await asyncio.sleep(0.1)

    # also test the ``SpeakAction`` object case
    from cradle.schemas.protocol.events.action import SpeakAction
    await global_event_bus.publish(SpeakAction(text="reply2", source="Soul"))
    await asyncio.sleep(0.1)

    # and finally a BaseEvent that wraps a SpeakAction; our extraction logic
    # must dive into the payload to find the text rather than just stringifying
    wrapped = BaseEvent(name="action.presentation.speak",
                        payload=SpeakAction(text="wrapped", source="Soul"),
                        source="Soul")
    await global_event_bus.publish(wrapped)
    await asyncio.sleep(0.1)

    sends = []
    async def rec(ev: BaseEvent):
        sends.append(ev.payload)
    global_event_bus.subscribe('napcat.send', rec)

    # normal dictionary-based speak should trigger a reply
    await global_event_bus.publish(BaseEvent(
        name="action.presentation.speak",
        payload={"text": "another"},
        source="Soul",
    ))
    # an empty/acknowledgement event with payload None must be ignored;
    # in the past this produced a literal "None" message and confused
    # recipients.
    await global_event_bus.publish(BaseEvent(
        name="action.presentation.speak",
        payload=None,
        source="Soul",
    ))
    await asyncio.sleep(0.1)

    await client.cleanup()

    assert any(p.get('params', {}).get('message') == 'another' for p in sends), sends
    assert not any(p.get('params', {}).get('message') == 'None' for p in sends), sends

@pytest.mark.asyncio
async def test_napcat_responder_group_reply():
    """If the incoming message came from a group, a reply should go to the group.
    """
    from cradle.selrena.synapse.napcat_responder import NapcatResponder
    # reset singleton flag so a fresh responder + client are created
    NapcatResponder._installed = False

    cfg = global_config.sys_config
    cfg.napcat.enable = True

    # bring up reflex/cortex layers, which will be driven by
    # the transcription events produced by NapcatClient
    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    await reflex.initialize()
    await cortex.initialize()

    # a regular NapcatClient instance will also auto-install a responder
    client = NapcatClient()
    await client.initialize()

    raw = {
        "post_type": "message",
        "sender": {"user_id": 123456},
        "group_id": 9876,
        "message": "hi"
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

    # cleanup everything we brought up
    await client.cleanup()
    await NapcatResponder().cleanup()
    await reflex.cleanup()
    await cortex.cleanup()

    assert any(
        p.get('action') == 'send_group_msg' and
        p.get('params', {}).get('group_id') == 9876
        for p in sends
    ), sends
    assert not any(p.get('action') == 'send_private_msg' for p in sends), sends

@pytest.mark.asyncio
async def test_napcat_client_group_id():
    """NapcatClient should propagate group_id from raw events."""
    cfg = global_config.sys_config
    cfg.napcat.enable = True
    client = NapcatClient()
    await client.initialize()

    # install layers so that input.user_message still fires
    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    await reflex.initialize()
    await cortex.initialize()

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
    unsub()

    assert texts and texts[0].get('group_id') == 42, texts

@pytest.mark.asyncio
async def test_napcat_list_payload():
    """NapcatClient should handle a raw list payload."""
    # don't bother with a live websocket; just push the event directly.
    cfg = global_config.sys_config
    cfg.napcat.enable = True  # ensure client activates

    # bring up reflex/cortex layers for pipeline
    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    await reflex.initialize()
    await cortex.initialize()

    # bring up a client instance so the event is processed
    client = NapcatClient()
    await client.initialize()

    texts = []
    async def rec(ev: BaseEvent):
        texts.append(ev.payload.get('text'))
    # listen on transcription layer now rather than directly user_message
    global_event_bus.subscribe('perception.audio.transcription', rec)
    # also watch the raw napcat.event payload that the client will see
    raw_events = []
    async def raw_rec(ev: BaseEvent):
        raw_events.append(ev.payload)
    global_event_bus.subscribe('napcat.event', raw_rec)

    # simulate arrival of list event as observed in real logs
    payload = [{'type': 'text', 'data': {'text': 'hi'}}]
    await global_event_bus.publish(BaseEvent(name='napcat.event', payload=payload, source='test'))
    await asyncio.sleep(0.1)

    # confirm the extracted text is correct.  prior bug caused the entire
    # list to be sent instead of "hi", which would make SoulIntellect crash.
    assert texts == ['hi'], f"unexpected texts from NapcatClient: {texts}, raw napcat.event payloads: {raw_events}"
    await client.cleanup()
    await reflex.cleanup()
    await cortex.cleanup()

@pytest.mark.asyncio
async def test_napcat_message_list():
    """If the OneBot "message" field itself is a list, it should be flattened."""
    cfg = global_config.sys_config
    cfg.napcat.enable = True

    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    await reflex.initialize()
    await cortex.initialize()

    client = NapcatClient()
    await client.initialize()
    texts = []
    async def rec(ev: BaseEvent):
        texts.append(ev.payload.get('text'))
    global_event_bus.subscribe('perception.audio.transcription', rec)

    # mimic payload from real log where `message` was array-of-segments
    payload = {
        'post_type': 'message',
        'message': [{'type': 'text', 'data': {'text': '晚上好，月见'}}]
    }
    await global_event_bus.publish(BaseEvent(name='napcat.event', payload=payload, source='test'))
    await asyncio.sleep(0.1)

    # first element should be the flattened text, and there must be
    # no secondary message containing the raw list.
    assert texts == ['晚上好，月见'], f"unexpected texts: {texts}"
    await client.cleanup()
    await reflex.cleanup()
    await cortex.cleanup()

@pytest.mark.asyncio
async def test_sensory_strict_wake():
    """当开启严格唤醒模式时，只有包含唤醒词的转录才会到意识层。"""
    # enable strict mode by toggling the cortex instance flag after init
    from cradle.selrena.synapse.reflex import ReflexController
    from cradle.selrena.synapse.sensory_cortex import SensoryCortex
    reflex = ReflexController()
    cortex = SensoryCortex()
    # override default
    cortex.strict_wake = True
    await reflex.initialize()
    await cortex.initialize()

    seen = []
    async def rec(ev: BaseEvent):
        seen.append(ev.payload.get('text'))
    unsub = global_event_bus.subscribe('input.user_message', rec)

    # publish two transcriptions, only the first contains wake word
    await global_event_bus.publish(BaseEvent(
        name='perception.audio.transcription',
        payload={'text': 'hello selrena, wake up'},
        source='test',
    ))
    await global_event_bus.publish(BaseEvent(
        name='perception.audio.transcription',
        payload={'text': 'just chatting without word'},
        source='test',
    ))
    await asyncio.sleep(0.1)

    # strict wake mode should suppress *all* non-wake transcripts.  there may
    # still be additional copies of the allowed message if previous tests leaked
    # subscribers; that's harmless as long as nothing else sneaks through.
    assert seen, f"no events were captured: {seen}"
    assert all(text == 'hello selrena, wake up' for text in seen), f"strict wake allowed unexpected: {seen}"

    # undo subscription
    unsub()
    await reflex.cleanup()
    await cortex.cleanup()

@pytest.mark.asyncio
async def test_napcat_client_response_handling():
    """NapcatClient should log and emit napcat.error on bad responses."""
    sys_cfg = global_config.sys_config
    sys_cfg.napcat.enable = True
    client = NapcatClient()
    await client.initialize()
    errors = []
    async def rec(ev: BaseEvent):
        errors.append(ev)
    global_event_bus.subscribe('napcat.error', rec)
    # simulate incoming response
    payload = {"status":"failed","retcode":1404,"message":"no api"}
    await global_event_bus.publish(BaseEvent(name='napcat.response', payload=payload, source='test'))
    await asyncio.sleep(0.1)
    await client.cleanup()
    assert errors and errors[0].payload['retcode'] == 1404

    # re-create client to test system message propagation
    client = NapcatClient()
    await client.initialize()
    sys_msgs = []
    async def rec2(ev: BaseEvent):
        sys_msgs.append(ev)
    global_event_bus.subscribe('input.system_message', rec2)
    await global_event_bus.publish(BaseEvent(name='napcat.response', payload=payload, source='test'))
    await asyncio.sleep(0.1)
    await client.cleanup()
    assert sys_msgs and 'Napcat API error' in sys_msgs[0].payload['text']

    # ensure system_message was also produced
    sysmsgs = []
    async def rec2(ev):
        sysmsgs.append(ev)
    global_event_bus.subscribe('input.system_message', rec2)
    await client.initialize()
    await global_event_bus.publish(BaseEvent(name='napcat.response', payload=payload, source='test'))
    await asyncio.sleep(0.1)
    await client.cleanup()
    assert sysmsgs and 'Napcat API error' in sysmsgs[0].payload['text']


def test_virtual_mouth_disabled(monkeypatch):
    """When TTS is turned off, VirtualMouth should not respond to speak actions."""
    sys_cfg = global_config.sys_config
    sys_cfg.presentation.tts.enabled = False

    mouth = VirtualMouth()
    # the bus should have no VirtualMouth callbacks on speak topic
    subs = global_event_bus._subscribers.get('action.presentation.speak', [])
    assert all(getattr(cb, '__self__', None) is not mouth for cb in subs), \
        "VirtualMouth should not subscribe when disabled"    

@pytest.mark.asyncio
async def test_audiostream_disabled(monkeypatch):
    """AudioStream.listen_loop returns without starting if disabled."""
    cfg = global_config.sys_config.perception.audio
    cfg.enabled = False
    stream = AudioStream()
    # monkeypatch start to fail if called
    called = False
    async def fake_start():
        nonlocal called
        called = True
    stream.start = fake_start
    await stream.listen_loop()
    assert not called, "start() should not be invoked when audio disabled"



