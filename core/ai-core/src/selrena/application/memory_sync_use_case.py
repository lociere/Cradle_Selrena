"""
文件名称：memory_sync_use_case.py
所属层级：应用层
核心作用：统一处理记忆同步事件，将领域记忆事件转发到内核持久化链路
设计原则：
1. 仅做流程编排，不在此实现业务规则
2. 所有跨进程同步由出站端口完成，避免直接依赖基础设施
3. 长短期记忆同步逻辑统一集中，便于后续扩展
"""
from dataclasses import dataclass

from selrena.memory_pipeline.long_term_memory import MemorySyncEvent
from selrena.memory_pipeline.short_term_memory import ShortTermMemorySyncEvent
from selrena.ipc_server.outbound.kernel_event_port import KernelEventPort
from selrena.core.observability.logger import get_logger

logger = get_logger("memory_sync_use_case")


@dataclass
class MemorySyncUseCase:
	"""记忆同步用例：把领域层记忆事件转发到内核。"""
	kernel_event_port: KernelEventPort

	async def on_long_term_memory_sync(self, event: MemorySyncEvent) -> None:
		if not event.memory_fragment:
			logger.warning("收到空的长期记忆同步事件，已忽略")
			return
		await self.kernel_event_port.send_memory_sync(event.memory_fragment)

	async def on_short_term_memory_sync(self, event: ShortTermMemorySyncEvent) -> None:
		if not event.fragment:
			logger.warning("收到空的短期记忆同步事件，已忽略", scene_id=event.scene_id)
			return
		await self.kernel_event_port.send_short_term_memory_sync(event.scene_id, event.fragment)
