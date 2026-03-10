"""领域模型→内核事件占位。"""

class KernelEventOutboundAdapter:
    def adapt(self, domain_obj: object) -> bytes:
        return b""
