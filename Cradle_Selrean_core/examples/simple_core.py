"""Simple example showing how to start/stop the Python AI core."""

import asyncio
from selrena import PythonAICore


async def main():
    core = PythonAICore(config_dir="./config", data_dir="./data")
    await core.start()
    print("core started")
    await core.send_event("ai_response", {"text": "hello world"})
    await asyncio.sleep(0.1)
    await core.stop()
    print("core stopped")


if __name__ == "__main__":
    asyncio.run(main())
