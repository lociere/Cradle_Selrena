"""可观测性适配器：将领域事件发送至日志/指标系统。"""

class ObservabilityAdapter:
    def log(self, msg: str) -> None:
        pass
    def emit(self, name: str, value: float) -> None:
        pass
