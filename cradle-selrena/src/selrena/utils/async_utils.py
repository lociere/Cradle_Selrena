import asyncio
from typing import Callable, Any


def run_in_background(coro: Callable[..., Any]) -> asyncio.Task:
    """启动一个协程并返回 Task，自动处理异常日志。"""
    task = asyncio.create_task(coro)

    def _done_callback(t: asyncio.Task):
        try:
            t.result()
        except Exception as e:
            from cradle_selrena.utils.logger import logger
            logger.exception(f"后台任务异常: {e}")

    task.add_done_callback(_done_callback)
    return task
