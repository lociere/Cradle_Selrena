import asyncio
import sys, os
# make package importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from selrena import PythonAICore
from selrena._internal.core.event_bus import SimpleEventBusClient

# ensure ZMQ works on Windows for other tests
try:
    from asyncio import windows_events
    asyncio.set_event_loop_policy(windows_events.WindowsSelectorEventLoopPolicy())
except ImportError:
    pass


def test_python_ai_core_lifecycle(tmp_path):
    async def inner():
        bus = SimpleEventBusClient()
        core = PythonAICore(config_dir=str(tmp_path / "cfg"), data_dir=str(tmp_path / "data"), event_bus=bus)
        # start with empty config should use DummyLLM
        await core.start(llm_config={}, use_local_llm=False)
        assert core._started
        # register a dummy handler and send event
        called = False
        def handler(evt):
            nonlocal called
            called = True
        core.register_handler("test_event", handler)
        await core.send_event("test_event", {"foo": "bar"})
        # small sleep to allow processing
        await asyncio.sleep(0.1)
        assert called
        await core.stop()
        assert not core._started
    asyncio.run(inner())
