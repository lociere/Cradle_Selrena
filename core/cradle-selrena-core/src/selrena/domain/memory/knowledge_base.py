"""
文件名称：knowledge_base.py
所属层级：领域层-记忆模块
核心作用：独立知识库，和个人记忆完全物理隔离，彻底解决记忆污染人设/知识的问题
设计原则：
1. 和长期记忆、短期记忆完全分离，独立存储、独立检索、独立注入prompt
2. 分库管理：人设固定知识库、通用知识库，绝对避免个人记忆污染人设知识
3. 仅做知识的存储和检索，不碰业务逻辑
4. 绝对不碰本地持久化，所有知识由内核启动时注入
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Dict, Iterable, List

from selrena.core.contracts.kernel_ingress_contracts import KnowledgeBaseInitPayloadModel
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("knowledge_base")

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


class KnowledgeBaseType(StrEnum):
    """知识库域类型。"""

    PERSONA = "persona"
    GENERAL = "general"


@dataclass
class KnowledgeRetrievalPolicy:
    """知识检索策略。"""

    persona_top_k: int = 12
    general_top_k: int = 4
    min_score: float = 0.15
    keyword_weight: float = 1.0
    tag_weight: float = 0.7
    priority_weight: float = 0.2


@dataclass
class KnowledgeEntry:
    """知识条目实体。"""

    entry_id: str
    content: str
    kb_type: KnowledgeBaseType
    tags: List[str] = field(default_factory=list)
    priority: int = 1
    source: str = "manual"
    updated_at: str = ""
    enabled: bool = True


class KnowledgeBase:
    """独立知识库管理器，全局单例。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._kb: Dict[KnowledgeBaseType, Dict[str, KnowledgeEntry]] = {
            KnowledgeBaseType.PERSONA: {},
            KnowledgeBaseType.GENERAL: {},
        }
        self._policy = KnowledgeRetrievalPolicy()
        logger.info("独立知识库初始化完成")

    def init_from_kernel(self, payload: KnowledgeBaseInitPayloadModel) -> None:
        """用内核注入的完整知识载荷重建知识库。"""
        self._kb[KnowledgeBaseType.PERSONA].clear()
        self._kb[KnowledgeBaseType.GENERAL].clear()
        self._policy = KnowledgeRetrievalPolicy(
            persona_top_k=payload.retrieval.persona_top_k,
            general_top_k=payload.retrieval.general_top_k,
            min_score=payload.retrieval.min_score,
            keyword_weight=payload.retrieval.keyword_weight,
            tag_weight=payload.retrieval.tag_weight,
            priority_weight=payload.retrieval.priority_weight,
        )

        for record in payload.entries:
            if record.scope not in (KnowledgeBaseType.PERSONA.value, KnowledgeBaseType.GENERAL.value):
                logger.warn("跳过非法知识 scope", entry_id=record.entry_id, scope=record.scope)
                continue
            if not record.enabled:
                continue

            self.add(
                KnowledgeEntry(
                    entry_id=record.entry_id,
                    content=record.content,
                    kb_type=KnowledgeBaseType(record.scope),
                    tags=record.tags,
                    priority=record.priority,
                    source=record.source,
                    updated_at=record.updated_at,
                    enabled=record.enabled,
                )
            )

        logger.info(
            "知识库注入完成",
            version=payload.version,
            persona_count=len(self._kb[KnowledgeBaseType.PERSONA]),
            general_count=len(self._kb[KnowledgeBaseType.GENERAL]),
        )

    def add(self, entry: KnowledgeEntry) -> None:
        self._kb[entry.kb_type][entry.entry_id] = entry

    def get_persona_knowledge(self, limit: int | None = None) -> List[KnowledgeEntry]:
        """获取人设知识，默认按策略限制数量。"""
        resolved_limit = limit if limit is not None else self._policy.persona_top_k
        entries = list(self._kb[KnowledgeBaseType.PERSONA].values())
        entries.sort(key=lambda item: item.priority, reverse=True)
        return entries[: max(1, resolved_limit)]

    def retrieve_general_knowledge(self, query: str, limit: int | None = None) -> List[KnowledgeEntry]:
        """按关键词/标签/优先级综合打分检索通用知识。"""
        resolved_limit = limit if limit is not None else self._policy.general_top_k
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scored_entries: List[tuple[float, KnowledgeEntry]] = []
        for entry in self._kb[KnowledgeBaseType.GENERAL].values():
            score = self._score_entry(entry, query_tokens)
            if score >= self._policy.min_score:
                scored_entries.append((score, entry))

        scored_entries.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored_entries[: max(1, resolved_limit)]]

    def get_all_entries(self, kb_type: KnowledgeBaseType | None = None) -> List[KnowledgeEntry]:
        """获取全部知识条目。"""
        if kb_type is not None:
            return list(self._kb[kb_type].values())
        result: List[KnowledgeEntry] = []
        for knowledge_dict in self._kb.values():
            result.extend(list(knowledge_dict.values()))
        return result

    def _score_entry(self, entry: KnowledgeEntry, query_tokens: set[str]) -> float:
        content_tokens = self._tokenize(entry.content)
        if not content_tokens:
            return 0.0

        tag_tokens = {token for token in self._normalize_tokens(entry.tags)}
        keyword_ratio = len(query_tokens & content_tokens) / len(query_tokens)
        tag_ratio = len(query_tokens & tag_tokens) / len(query_tokens) if tag_tokens else 0.0
        priority_ratio = min(max(entry.priority, 1), 100) / 100.0

        return (
            keyword_ratio * self._policy.keyword_weight
            + tag_ratio * self._policy.tag_weight
            + priority_ratio * self._policy.priority_weight
        )

    def _tokenize(self, text: str) -> set[str]:
        return {token.lower() for token in _TOKEN_RE.findall(text or "")}

    def _normalize_tokens(self, values: Iterable[str]) -> set[str]:
        joined = " ".join(value for value in values if value)
        return self._tokenize(joined)