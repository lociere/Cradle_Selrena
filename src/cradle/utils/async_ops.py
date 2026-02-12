import asyncio
import functools
from typing import Type, Tuple, Union, Callable
from cradle.utils.logger import logger

def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,)
):
    """
    异步重试装饰器
    :param retries: 最大重试次数
    :param delay: 初始延迟时间 (秒)
    :param backoff: 延迟倍数
    :param exceptions: 需要捕获的异常类型
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < retries:
                        logger.warning(
                            f"Execution of {func.__name__} failed: {e}. "
                            f"Retrying in {current_delay:.2f}s... ({attempt + 1}/{retries})"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Max retries reached for {func.__name__}. Error: {e}")
            
            if last_exception:
                raise last_exception
        return wrapper
    return decorator

async def run_in_background(coro):
    """
    Fire-and-forget: 在后台运行协程，不阻塞当前流程
    会自动捕获异常并记入日志，防止 Task 销毁时的警告
    """
    async def wrapper():
        try:
            await coro
        except Exception as e:
            logger.exception(f"Background task failed: {e}")
            
    asyncio.create_task(wrapper())

class Timer:
    """
    上下文管理器：用于测量代码块执行耗时
    with Timer("LLM Inference"):
        await llm.generate()
    """
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start = 0

    def __enter__(self):
        import time
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        elapsed = (time.perf_counter() - self.start) * 1000
        logger.debug(f"[{self.name}] took {elapsed:.2f}ms")
