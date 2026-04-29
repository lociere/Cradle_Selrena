"""
知识库模块 — 世界知识管理器

职责：管理 scope=knowledge 的事实知识条目（天气、时间、食物等）。
人设条目（scope=persona）由 PersonaInjector 独占消费，不经过此模块。

检索策略（由 retrieval.mode 决定）：
- full_injection：全量注入所有已启用条目（条目 <50 时推荐）
- semantic_rag ：向量语义检索 Top-K（条目 ≥50 时切换）
  · 有向量引擎 → cosine similarity 排序
  · 无向量引擎 → bigram 关键词退化
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from selrena.ipc_server.contracts.kernel_ingress_contracts import KnowledgeBaseInitPayloadModel
from selrena.core.observability.logger import get_logger
from selrena.llm_engine.embedding_engine import EmbeddingEngine

logger = get_logger("knowledge_base")

# 英文单词 / 汉字逐字分词（bigram 在 _tokenize 中生成）
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


@dataclass
class KnowledgeRetrievalPolicy:
    mode: str = "full_injection"  # "full_injection" | "semantic_rag"
    top_k: int = 5
    min_score: float = 0.3
    semantic_weight: float = 0.6


@dataclass
class KnowledgeEntry:
    entry_id: str
    content: str
    priority: int = 1
    enabled: bool = True
    _embedding: Optional[np.ndarray] = field(default=None, repr=False, compare=False)


class KnowledgeBase:
    """世界知识管理器，全局单例。

    初始化流程：
      1. TS 内核发送 knowledge_init IPC
      2. adapter 分流：scope=persona → PersonaInjector；scope=knowledge → 此处
      3. init_from_kernel() 注册条目，按 mode 决定检索策略
    """

    _instance: Optional["KnowledgeBase"] = None

    def __new__(cls) -> "KnowledgeBase":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._policy = KnowledgeRetrievalPolicy()
        self._embedding_engine: Optional[EmbeddingEngine] = None
        logger.info("世界知识库初始化完成")

    def set_embedding_engine(self, engine: EmbeddingEngine) -> None:
        """由 container.py 在推理层初始化后注入。"""
        self._embedding_engine = engine if engine.is_available() else None
        if self._embedding_engine:
            logger.info("知识库已接入向量引擎，semantic_rag 模式可用")

    def init_from_kernel(self, payload: KnowledgeBaseInitPayloadModel) -> None:
        """从内核 IPC 载荷初始化。只接收 scope=knowledge 条目。"""
        self._entries.clear()

        retrieval = payload.retrieval
        self._policy = KnowledgeRetrievalPolicy(
            mode=retrieval.mode,
            top_k=retrieval.top_k,
            min_score=retrieval.min_score,
            semantic_weight=retrieval.semantic_weight,
        )

        for record in payload.entries:
            if record.scope != "knowledge":
                continue
            if not record.enabled:
                continue
            self._entries[record.entry_id] = KnowledgeEntry(
                entry_id=record.entry_id,
                content=record.content,
                priority=record.priority,
                enabled=record.enabled,
            )

        # semantic_rag 模式下预计算向量
        if self._policy.mode == "semantic_rag" and self._embedding_engine:
            self._precompute_embeddings()

        logger.info(
            "知识库注入完成",
            version=payload.version,
            mode=self._policy.mode,
            entry_count=len(self._entries),
        )

    def _precompute_embeddings(self) -> None:
        """批量计算所有条目向量并缓存。"""
        assert self._embedding_engine is not None
        entries = list(self._entries.values())
        if not entries:
            return
        try:
            vectors = self._embedding_engine.encode([e.content for e in entries])
            for entry, vec in zip(entries, vectors):
                entry._embedding = vec
            logger.info("知识库向量预计算完成", count=len(entries))
        except Exception as exc:
            logger.warning("向量预计算失败，退化为 bigram", error=str(exc))
            self._embedding_engine = None

    # ------------------------------------------------------------------
    # 对外检索接口
    # ------------------------------------------------------------------

    def get_knowledge(self, query: str = "") -> List[KnowledgeEntry]:
        """统一对外接口。

        full_injection 模式：返回所有已启用条目（按优先级排序）。
        semantic_rag  模式：向量检索 Top-K，无引擎时 bigram 退化。
        """
        if self._policy.mode == "full_injection":
            return sorted(
                [e for e in self._entries.values() if e.enabled],
                key=lambda e: e.priority,
                reverse=True,
            )
        return self._retrieve(query)

    def get_all_entries(self) -> List[KnowledgeEntry]:
        """获取所有条目（用于调试/导出）。"""
        return list(self._entries.values())

    # ------------------------------------------------------------------
    # 内部检索实现（semantic_rag 模式）
    # ------------------------------------------------------------------

    def _retrieve(self, query: str) -> List[KnowledgeEntry]:
        """semantic_rag 模式下的检索。"""
        entries = [e for e in self._entries.values() if e.enabled]
        if not entries or not query.strip():
            return entries[:self._policy.top_k]

        # 尝试语义检索
        if self._embedding_engine and self._embedding_engine.is_available():
            has_embedding = [e for e in entries if e._embedding is not None]
            if has_embedding:
                try:
                    return self._semantic_retrieve(query, has_embedding)
                except Exception as exc:
                    logger.warning("语义检索异常，退化为 bigram", error=str(exc))

        # 退化为 bigram
        return self._bigram_retrieve(query, entries)

    def _semantic_retrieve(self, query: str, entries: List[KnowledgeEntry]) -> List[KnowledgeEntry]:
        """向量余弦相似度检索。"""
        assert self._embedding_engine is not None
        query_vec = self._embedding_engine.encode_single(query)
        matrix = np.stack([e._embedding for e in entries])
        sims = self._embedding_engine.cosine_similarities(query_vec, matrix)
        scored = sorted(zip(sims, entries), key=lambda x: float(x[0]), reverse=True)
        return [e for sim, e in scored[:self._policy.top_k] if float(sim) >= self._policy.min_score]

    def _bigram_retrieve(self, query: str, entries: List[KnowledgeEntry]) -> List[KnowledgeEntry]:
        """bigram 关键词退化检索。"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return entries[:self._policy.top_k]

        scored = []
        for entry in entries:
            content_tokens = self._tokenize(entry.content)
            overlap = len(query_tokens & content_tokens)
            if overlap > 0:
                score = overlap / len(query_tokens)
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for score, e in scored[:self._policy.top_k] if score >= self._policy.min_score]

    @staticmethod
    def _tokenize(text: str) -> set:
        """Bigram 分词：逐字 + 相邻汉字双字组合。"""
        chars = _TOKEN_RE.findall(text or "")
        tokens: set = {c.lower() for c in chars}
        for i in range(len(chars) - 1):
            if len(chars[i]) == 1 and len(chars[i + 1]) == 1:
                tokens.add(chars[i] + chars[i + 1])
        return tokens
