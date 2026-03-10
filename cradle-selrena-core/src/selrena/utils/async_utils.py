"""异步工具：协程/任务/超时控制。"""

import asyncio


def timeout(coro, seconds: float):
    return asyncio.wait_for(coro, seconds)
