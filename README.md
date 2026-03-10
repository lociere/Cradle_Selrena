# Cradle_Selrena (摇篮·月见)

<!-- NOTE: Path for new Python AI layer 'cradle-selrena-core' has been added as part of architectural upgrade. -->

A Python AI subsystem packaged as a single `selrena` module. The
external interface is the `PythonAICore` class; callers should never
reach into `_internal` unless they are writing tests or are part of the
framework itself.

```python
from selrena import PythonAICore
import asyncio

core = PythonAICore(config_dir="./config", data_dir="./data")
async def run():
    await core.start()
    await core.send_event("ai_response", {"text": "hello"})
    await core.stop()

asyncio.run(run())
```

```bash
# install in editable mode
pip install -e cradle-selrena
```
