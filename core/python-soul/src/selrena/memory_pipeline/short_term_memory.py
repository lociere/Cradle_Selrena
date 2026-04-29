"""
文件名称：short_term_memory.py
所属层级：领域层-记忆模块
核心作用：短期工作记忆，对应人脑的「工作记忆」，存储会话内上下文，按scene_id完全隔离
设计原则：
1. 每个场景（scene_id）有独立的短期记忆，完全隔离，绝对不会串线
2. 仅存储当前会话的上下文，会话结束后筛选重要内容沉淀到长期记忆
3. 有自动遗忘机制，超过最大长度自动遗忘最早的内容
4. 绝对不碰本地持久化，持久化由TS内核负责
"""
from dataclasses import dataclass, field
from uuid import uuid4
from datetime import datetime
from typing import List, Optional
import asyncio
from selrena.multimodal.multimodal_content import MultimodalContent
from selrena.core.event_bus import DomainEvent, DomainEventBus
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("short_term_memory")


@dataclass
class ShortTermMemorySyncEvent(DomainEvent):
    """短期记忆同步事件，用于通知内核进行持久化。"""
    scene_id: str = ""
    fragment: Optional["ShortTermMemoryFragment"] = None


# ======================================
# 短期记忆片段实体
# ======================================
@dataclass
class ShortTermMemoryFragment:
    """短期记忆片段，存储单条会话内容"""
    # 角色：user（用户）/ selrena（月见）
    role: str
    # 文本内容
    content: str
    # 多模态内容（可选，内核预处理后传入）
    multimodal: Optional[MultimodalContent] = None
    # 记忆唯一ID
    memory_id: str = field(default_factory=lambda: str(uuid4()))
    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)
    # 重要度 0~1，越高越容易沉淀到长期记忆
    importance: float = 0.5

    def get_full_content(self) -> str:
        """
        获取完整内容，用于prompt注入
        返回：格式化后的完整记忆文本
        """
        content = f"{self.role}: {self.content}"
        if self.multimodal:
            content += f" {self.multimodal.get_full_text()}"
        return content


# ======================================
# 短期记忆管理器（按场景隔离）
# ======================================
class ShortTermMemory:
    """
    短期工作记忆管理器，每个场景（scene_id）对应一个独立实例
    核心作用：存储当前会话的上下文，和场景完全绑定隔离，彻底避免串线
    真人逻辑对齐：对应人脑的工作记忆，只记得当前聊天的上下文，换个聊天对象就会重置
    """
    def __init__(self, scene_id: str, max_length: int = 20):
        """
        初始化短期记忆
        参数：
            scene_id: 场景唯一ID，由内核传入，AI层仅用来隔离记忆，不处理场景规则
            max_length: 最大记忆长度，超过自动遗忘最早的内容
        """
        # 绑定的场景ID，保证隔离
        self.scene_id = scene_id
        # 最大记忆长度，超过自动遗忘最早的内容
        self.max_length = max_length
        # 记忆存储
        self._fragments: List[ShortTermMemoryFragment] = []
        # 事件总线（用于异步同步到内核）
        self._event_bus = DomainEventBus()
        logger.info("短期记忆初始化完成", scene_id=scene_id, max_length=max_length)

    def add(
        self,
        role: str,
        content: str,
        multimodal: MultimodalContent = None,
        importance: float = 0.5
    ) -> None:
        """
        新增短期记忆
        参数：
            role: 角色 user/selrena
            content: 文本内容
            multimodal: 多模态内容（可选）
            importance: 重要度 0~1，越高越容易沉淀到长期记忆
        """
        fragment = ShortTermMemoryFragment(
            role=role,
            content=content,
            multimodal=multimodal,
            importance=importance
        )
        self._fragments.append(fragment)

        # 超过最大长度，自动遗忘最早的内容
        if len(self._fragments) > self.max_length:
            forgotten = self._fragments.pop(0)
            logger.debug(
                "自动遗忘最早的短期记忆",
                scene_id=self.scene_id,
                memory_id=forgotten.memory_id
            )

        logger.debug(
            "新增短期记忆完成",
            scene_id=self.scene_id,
            role=role,
            memory_id=fragment.memory_id
        )

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._event_bus.publish(
                    ShortTermMemorySyncEvent(scene_id=self.scene_id, fragment=fragment)
                )
            )
        except RuntimeError:
            # 无事件循环（如单元测试）时跳过异步发布
            pass

    def get_context(self, limit: int = 10) -> List[ShortTermMemoryFragment]:
        """
        获取会话上下文，用于prompt注入
        参数：
            limit: 返回的记忆数量
        返回：按时间正序排列的记忆片段列表
        """
        return self._fragments[-limit:]

    def get_context_text(self, limit: int = 10) -> str:
        """
        获取上下文文本，直接用于prompt注入
        参数：
            limit: 返回的记忆数量
        返回：格式化后的上下文文本
        """
        fragments = self.get_context(limit)
        return "\n".join([frag.get_full_content() for frag in fragments])

    def get_important_fragments(self, threshold: float = 0.7) -> List[ShortTermMemoryFragment]:
        """
        获取重要度超过阈值的记忆片段，用于沉淀到长期记忆
        参数：
            threshold: 重要度阈值
        返回：符合条件的记忆片段列表
        """
        return [frag for frag in self._fragments if frag.importance >= threshold]

    def clear(self) -> None:
        """清空短期记忆，会话结束时由内核触发"""
        self._fragments = []
        logger.info("短期记忆已清空", scene_id=self.scene_id)