"""生命周期管控接口。"""

from typing import Protocol


class LifecyclePort(Protocol):
    async def wake_up(self) -> None:
        ...

    async def sleep(self) -> None:
        ...
