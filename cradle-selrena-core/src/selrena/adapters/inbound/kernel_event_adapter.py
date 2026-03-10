"""通用内核事件适配占位。"""

class KernelEventAdapter:
    def adapt(self, proto_msg: bytes) -> object:
        return {}
