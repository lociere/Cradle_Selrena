"""用例基类：统一 TraceID/异常处理/日志。"""

class BaseUseCase:
    def execute(self, *args, **kwargs):
        raise NotImplementedError
