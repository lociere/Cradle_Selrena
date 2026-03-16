"""
文件名称：kernel_event_adapter.py
所属层级：适配器层-出站适配器
核心作用：实现出站端口的抽象接口，把AI层的事件转换为IPC消息发送给内核
设计原则：
1. 仅做协议转换，不碰业务逻辑
2. 把AI层的领域事件，转换为内核能理解的标准化IPC消息
3. 不做任何流程编排，仅做消息转发
"""
from selrena.ports.outbound.kernel_event_port import KernelEventPort
from selrena.domain.memory.long_term_memory import LongTermMemoryFragment
from selrena.bridge.kernel_bridge import KernelBridge
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("outbound_adapter")


class KernelEventOutboundAdapter(KernelEventPort):
    """
    内核事件出站适配器
    核心作用：把AI层的领域事件，转换为标准化IPC消息发送给内核
    设计规范：仅做协议转换和消息发送，不碰任何业务逻辑
    """
    def __init__(self, kernel_bridge: KernelBridge):
        self.kernel_bridge = kernel_bridge
        logger.info("内核出站适配器初始化完成")

    async def send_memory_sync(self, fragment: LongTermMemoryFragment) -> None:
        """发送记忆同步事件给内核"""
        logger.debug(
            "发送记忆同步事件给内核",
            memory_id=fragment.memory_id
        )
        # 转换为标准化消息格式
        message = {
            "type": "memory_sync",
            "memory": {
                "memory_id": fragment.memory_id,
                "content": fragment.content,
                "memory_type": fragment.memory_type.value,
                "weight": fragment.weight,
                "tags": fragment.tags,
                "scene_id": fragment.scene_id,
                "timestamp": fragment.timestamp.isoformat()
            }
        }
        # 通过桥接层发送给内核
        await self.kernel_bridge.send_message(message)

    async def send_state_sync(self, state: dict) -> None:
        """发送状态同步事件给内核"""
        logger.debug(
            "发送状态同步事件给内核",
            state=state
        )
        message = {
            "type": "state_sync",
            "state": state
        }
        await self.kernel_bridge.send_message(message)

    async def send_log(self, level: str, message: str, extra: dict = None) -> None:
        """发送日志事件给内核"""
        log_message = {
            "type": "log",
            "level": level,
            "message": message,
            "extra": extra or {}
        }
        await self.kernel_bridge.send_message(log_message)