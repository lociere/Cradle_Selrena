"""
文件名称：long_term_memory.py
所属层级：领域层-记忆模块
核心作用：长期终身记忆，对应人脑的「长期记忆」，分类型管理，内核负责持久化
设计原则：
1. 分类型管理，避免记忆混乱：情景记忆、偏好记忆、事实记忆
2. 和短期记忆、知识库完全分离，不会互相污染
3. 有自然的遗忘、权重衰减、检索规则，符合人脑逻辑
4. 绝对不碰本地持久化，仅通过事件通知内核同步持久化
5. EmbeddingEngine 是主要消费者——对持续增长的记忆做语义检索
"""
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Optional
import re
import asyncio

import numpy as np

from selrena.ipc_server.contracts.kernel_ingress_contracts import KernelLongTermMemoryRecord
from selrena.multimodal.multimodal_content import MultimodalContent
from selrena.core.event_bus import DomainEvent, DomainEventBus
from selrena.core.observability.logger import get_logger
from selrena.llm_engine.embedding_engine import EmbeddingEngine

# 初始化模块日志器
logger = get_logger("long_term_memory")

# bigram 分词正则（与 knowledge_base.py 共用逻辑）
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def _bigram_tokenize(text: str) -> set:
    """Bigram 分词：逐字 + 相邻汉字双字组合。"""
    chars = _TOKEN_RE.findall(text or "")
    tokens: set = {c.lower() for c in chars}
    for i in range(len(chars) - 1):
        if len(chars[i]) == 1 and len(chars[i + 1]) == 1:
            tokens.add(chars[i] + chars[i + 1])
    return tokens


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
    # 语义向量缓存（由 EmbeddingEngine 计算）
    _embedding: Optional[np.ndarray] = field(default=None, repr=False, compare=False)

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
    核心作用：管理终身记忆，分类型存储、语义检索、遗忘
    EmbeddingEngine 的主要消费者——对持续增长的记忆做向量语义检索
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
        # 向量引擎（由 container.py 注入）
        self._embedding_engine: Optional[EmbeddingEngine] = None
        logger.info("长期记忆系统初始化完成")

    # ------------------------------------------------------------------
    # 向量引擎注入
    # ------------------------------------------------------------------

    def set_embedding_engine(self, engine: EmbeddingEngine) -> None:
        """由 container.py 在推理层初始化后注入。注入后对已有记忆建立向量索引。"""
        self._embedding_engine = engine if engine.is_available() else None
        if self._embedding_engine:
            self._reindex_all()
            logger.info("长期记忆已接入向量引擎，语义检索可用")

    def _reindex_all(self) -> None:
        """批量计算所有已有记忆的语义向量。"""
        assert self._embedding_engine is not None
        fragments = [m for m in self._memories.values() if m._embedding is None]
        if not fragments:
            return
        try:
            texts = [f.content for f in fragments]
            vectors = self._embedding_engine.encode(texts)
            for frag, vec in zip(fragments, vectors):
                frag._embedding = vec
            logger.info("长期记忆向量索引构建完成", count=len(fragments))
        except Exception as exc:
            logger.warning("长期记忆向量索引失败，退化为 bigram 检索", error=str(exc))
            self._embedding_engine = None

    # ------------------------------------------------------------------
    # 内核注入
    # ------------------------------------------------------------------

    def init_from_kernel(self, memories: List[KernelLongTermMemoryRecord]) -> None:
        """
        内核启动时注入历史长期记忆，AI层绝对不读本地文件
        参数：
            memories: 内核从本地数据库加载的历史记忆列表
        """
        for mem in memories:
            fragment = LongTermMemoryFragment(
                content=mem.content,
                memory_type=LongTermMemoryType(mem.memory_type),
                weight=mem.weight,
                tags=mem.tags,
                scene_id=mem.scene_id,
                memory_id=mem.memory_id,
                timestamp=datetime.fromisoformat(mem.timestamp),
            )
            self._memories[fragment.memory_id] = fragment
        logger.info("历史长期记忆注入完成", memory_count=len(self._memories))

    # ------------------------------------------------------------------
    # 新增记忆
    # ------------------------------------------------------------------

    def add(self, fragment: LongTermMemoryFragment) -> None:
        """
        新增长期记忆。新增时立即计算语义向量，同时发布同步事件通知内核持久化。
        """
        # 计算语义向量
        if self._embedding_engine and self._embedding_engine.is_available():
            try:
                fragment._embedding = self._embedding_engine.encode_single(fragment.content)
            except Exception as exc:
                logger.warning("记忆向量计算失败", memory_id=fragment.memory_id, error=str(exc))

        self._memories[fragment.memory_id] = fragment

        # 发布同步事件，通知内核持久化
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._event_bus.publish(MemorySyncEvent(memory_fragment=fragment)))
        except RuntimeError:
            pass
        logger.info(
            "新增长期记忆完成",
            memory_id=fragment.memory_id,
            memory_type=fragment.memory_type.value,
        )

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def retrieve_relevant(
        self,
        query: str,
        memory_type: LongTermMemoryType = None,
        limit: int = 5,
    ) -> List[LongTermMemoryFragment]:
        """
        检索和查询内容相关的长期记忆。
        有向量引擎 → 语义检索；无向量引擎 → bigram 退化。
        """
        candidates = [
            m for m in self._memories.values()
            if (not memory_type or m.memory_type == memory_type)
        ]
        if not candidates or not query.strip():
            return []

        if self._embedding_engine and self._embedding_engine.is_available():
            result = self._semantic_retrieve(query, candidates, limit)
        else:
            result = self._bigram_retrieve(query, candidates, limit)

        logger.debug("长期记忆检索完成", query=query[:20], result_count=len(result))
        return result

    def _semantic_retrieve(
        self,
        query: str,
        candidates: List[LongTermMemoryFragment],
        limit: int,
    ) -> List[LongTermMemoryFragment]:
        """向量语义检索：cosine_similarity * weight 综合打分。"""
        assert self._embedding_engine is not None
        has_embedding = [m for m in candidates if m._embedding is not None]
        if not has_embedding:
            return self._bigram_retrieve(query, candidates, limit)

        try:
            query_vec = self._embedding_engine.encode_single(query)
            matrix = np.stack([m._embedding for m in has_embedding])
            sims = self._embedding_engine.cosine_similarities(query_vec, matrix)
            scored = [
                (float(sim) * m.weight, m)
                for sim, m in zip(sims, has_embedding)
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            return [m for score, m in scored[:limit] if score > 0.1]
        except Exception as exc:
            logger.warning("语义检索异常，退化为 bigram", error=str(exc))
            return self._bigram_retrieve(query, candidates, limit)

    def _bigram_retrieve(
        self,
        query: str,
        candidates: List[LongTermMemoryFragment],
        limit: int,
    ) -> List[LongTermMemoryFragment]:
        """bigram 关键词退化检索（中文友好）。"""
        query_tokens = _bigram_tokenize(query)
        if not query_tokens:
            return []

        scored = []
        for mem in candidates:
            content_tokens = _bigram_tokenize(mem.content)
            overlap = len(query_tokens & content_tokens)
            if overlap > 0:
                score = (overlap / len(query_tokens)) * mem.weight
                scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    # ------------------------------------------------------------------
    # 偏好记忆（全量注入）
    # ------------------------------------------------------------------

    def get_preference_memory(self) -> List[LongTermMemoryFragment]:
        """
        获取所有偏好记忆，永久保留，每次prompt都注入
        返回：所有偏好记忆片段列表
        """
        return [mem for mem in self._memories.values() if mem.memory_type == LongTermMemoryType.PREFERENCE]

    # ------------------------------------------------------------------
    # 衰减 & 导出
    # ------------------------------------------------------------------

    def decay_all(self) -> None:
        """所有记忆权重自然衰减，每天执行一次"""
        for mem in self._memories.values():
            mem.decay_weight()
        logger.info("全量记忆权重衰减完成")

    def get_all_memories(self) -> List[LongTermMemoryFragment]:
        """获取所有记忆，用于内核全量同步"""
        return list(self._memories.values())