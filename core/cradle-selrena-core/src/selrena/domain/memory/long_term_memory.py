"""
文件名称：long_term_memory.py
所属层级：领域层-记忆模块
核心作用：长期终身记忆，对应人脑的「长期记忆」，分类型管理，内核负责持久化
设计原则：
1. 分类型管理，避免记忆混乱：情景记忆、偏好记忆、事实记忆
2. 和短期记忆、知识库完全分离，不会互相污染
3. 有自然的遗忘、权重衰减、检索规则，符合人脑逻辑
4. 绝对不碰本地持久化，仅通过事件通知内核同步持久化
"""
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Optional
from selrena.domain.multimodal.multimodal_content import MultimodalContent
from selrena.core.event_bus import DomainEvent, DomainEventBus
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("long_term_memory")


# ======================================
# 长期记忆类型枚举
# ======================================
class LongTermMemoryType(StrEnum):
    EPISODIC = "episodic"     # 情景记忆：和用户的互动事件、对话内容
    PREFERENCE = "preference" # 偏好记忆：用户的喜好、习惯、禁忌，终身保留
    FACT = "fact"             # 事实记忆：学到的知识、事实，和知识库分离
    MULTIMODAL = "multimodal" # 多模态记忆：图片/语音/视频相关的记忆


# ======================================
# 记忆同步事件（用于通知内核持久化）
# ======================================
@dataclass
class MemorySyncEvent(DomainEvent):
    """记忆同步事件，新增/修改记忆时发布，通知内核持久化"""
    # NOTE: DomainEvent declares fields with defaults, so subclass fields must also have defaults
    # to keep dataclass field ordering valid.
    memory_fragment: Optional["LongTermMemoryFragment"] = None


# ======================================
# 长期记忆片段实体
# ======================================
@dataclass
class LongTermMemoryFragment:
    """长期记忆片段，终身存储"""
    # 记忆内容
    content: str
    # 记忆类型
    memory_type: LongTermMemoryType
    # 记忆权重 0~1，越高越不容易被遗忘，检索优先级越高
    weight: float = 1.0
    # 记忆标签，用于检索分类
    tags: List[str] = field(default_factory=list)
    # 绑定的场景ID（可选）
    scene_id: str = ""
    # 多模态内容（可选）
    multimodal: MultimodalContent = None
    # 记忆唯一ID
    memory_id: str = field(default_factory=lambda: str(uuid4()))
    # 创建时间
    timestamp: datetime = field(default_factory=datetime.now)

    def decay_weight(self, decay_rate: float = 0.02) -> None:
        """
        记忆权重自然衰减，符合人脑遗忘曲线，每天衰减2%
        规则：偏好记忆永久保留，不衰减
        """
        # 偏好记忆永久保留，不衰减
        if self.memory_type != LongTermMemoryType.PREFERENCE:
            self.weight = max(0.1, self.weight - decay_rate)


# ======================================
# 长期记忆管理器（全局单例）
# ======================================
class LongTermMemory:
    """
    长期记忆管理器，全局单例
    核心作用：管理终身记忆，分类型存储、检索、遗忘
    真人逻辑对齐：对应人脑的长期记忆，会记住重要的事情，不重要的会慢慢遗忘
    """
    _instance = None

    def __new__(cls):
        """单例模式，保证整个进程只有一个长期记忆管理器"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        """初始化，仅在单例创建时执行一次"""
        # 记忆存储：key=memory_id，value=LongTermMemoryFragment
        self._memories: Dict[str, LongTermMemoryFragment] = {}
        # 事件总线
        self._event_bus = DomainEventBus()
        logger.info("长期记忆系统初始化完成")

    def init_from_kernel(self, memories: List[dict]) -> None:
        """
        内核启动时注入历史长期记忆，AI层绝对不读本地文件
        参数：
            memories: 内核从本地数据库加载的历史记忆列表
        """
        for mem in memories:
            fragment = LongTermMemoryFragment(
                content=mem["content"],
                memory_type=LongTermMemoryType(mem["memory_type"]),
                weight=mem["weight"],
                tags=mem["tags"],
                scene_id=mem.get("scene_id", ""),
                memory_id=mem["memory_id"],
                timestamp=datetime.fromisoformat(mem["timestamp"])
            )
            self._memories[fragment.memory_id] = fragment
        logger.info("历史长期记忆注入完成", memory_count=len(self._memories))

    def add(self, fragment: LongTermMemoryFragment) -> None:
        """
        新增长期记忆，同时发布同步事件通知内核持久化
        参数：
            fragment: 长期记忆片段
        """
        self._memories[fragment.memory_id] = fragment
        # 发布同步事件，通知内核持久化
        self._event_bus.publish(MemorySyncEvent(memory_fragment=fragment))
        logger.info(
            "新增长期记忆完成",
            memory_id=fragment.memory_id,
            memory_type=fragment.memory_type.value
        )

    def retrieve_relevant(
        self,
        query: str,
        memory_type: LongTermMemoryType = None,
        limit: int = 5
    ) -> List[LongTermMemoryFragment]:
        """
        检索和查询内容相关的长期记忆
        参数：
            query: 查询内容
            memory_type: 可选，指定记忆类型过滤
            limit: 返回的记忆数量
        返回：按相关度排序的记忆列表
        """
        query_keywords = set(query.lower().split())
        scored_memories = []

        for mem in self._memories.values():
            # 过滤指定类型
            if memory_type and mem.memory_type != memory_type:
                continue
            # 关键词匹配
            match_count = len(query_keywords & set(mem.content.lower().split()))
            # 最终得分 = 匹配数 * 记忆权重
            score = match_count * mem.weight
            if score > 0:
                scored_memories.append((score, mem))

        # 按得分倒序排序，返回topN
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        result = [mem for score, mem in scored_memories[:limit]]
        logger.debug(
            "长期记忆检索完成",
            query=query[:20],
            result_count=len(result)
        )
        return result

    def get_preference_memory(self) -> List[LongTermMemoryFragment]:
        """
        获取所有偏好记忆，永久保留，每次prompt都注入
        返回：所有偏好记忆片段列表
        """
        return [mem for mem in self._memories.values() if mem.memory_type == LongTermMemoryType.PREFERENCE]

    def decay_all(self) -> None:
        """所有记忆权重自然衰减，每天执行一次"""
        for mem in self._memories.values():
            mem.decay_weight()
        logger.info("全量记忆权重衰减完成")

    def get_all_memories(self) -> List[LongTermMemoryFragment]:
        """获取所有记忆，用于内核全量同步"""
        return list(self._memories.values())