"""可观测性事件输出接口。"""

from typing import Protocol, Any


class ObservabilityPort(Protocol):
    def log(self, message: str, **kwargs: Any) -> None:
        ...

    def emit_metric(self, name: str, value: float) -> None:
        ...
