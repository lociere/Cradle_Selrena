"""弹性能力：重试/熔断/限流占位。"""

async def retry(func, *args, **kwargs):
    return await func(*args, **kwargs)
