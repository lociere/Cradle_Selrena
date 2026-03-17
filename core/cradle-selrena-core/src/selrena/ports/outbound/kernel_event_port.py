"""
文件名称：kernel_event_port.py
所属层级：端口层-出站端口
核心作用：定义出站事件的抽象接口，遵循依赖倒置原则
设计原则：
1. 仅定义抽象接口，不做实现
2. 所有发送给内核的事件，必须通过此接口定义
3. 完全屏蔽底层通信细节，领域层/应用层仅依赖此接口
"""
from abc import ABC, abstractmethod
from selrena.domain.memory.long_term_memory import LongTermMemoryFragment
from selrena.domain.memory.short_term_memory import ShortTermMemoryFragment


class KernelEventPort(ABC):
    """
    内核事件出站端口抽象接口
    核心作用：定义AI层能发送给内核的所有事件，完全屏蔽底层通信细节
    真人逻辑对齐：对应人脑的动作输出接口，仅定义能发送什么信号，不关心信号到哪里去
    """

    @abstractmethod
    async def send_memory_sync(self, fragment: LongTermMemoryFragment) -> None:
        """
        发送记忆同步事件给内核，触发持久化
        参数：
            fragment: 要同步的长期记忆片段
        """
        pass

    @abstractmethod
    async def send_state_sync(self, state: dict) -> None:
        """
        发送状态同步事件给内核，同步给渲染层
        参数：
            state: 月见当前状态字典
        """
        pass

    @abstractmethod
    async def send_log(self, level: str, message: str, extra: dict = None) -> None:
        """
        发送日志事件给内核，统一日志管理
        参数：
            level: 日志级别
            message: 日志内容
            extra: 额外参数
        """
        pass

    @abstractmethod
    async def send_short_term_memory_sync(self, scene_id: str, fragment: ShortTermMemoryFragment) -> None:
        """
        发送短期记忆同步事件给内核，写入短期记忆存储。
        参数：
            scene_id: 场景ID
            fragment: 短期记忆片段
        """
        pass