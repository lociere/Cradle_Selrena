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
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4
from datetime import datetime
from typing import List, Dict
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("knowledge_base")


# ======================================
# 知识库类型枚举
# ======================================
class KnowledgeBaseType(StrEnum):
    PERSONA = "persona"   # 人设固定知识库：月见的背景故事、设定、规则，终身固定，不可被记忆修改
    GENERAL = "general"   # 通用知识库：通用知识、技能、常识，和个人记忆完全分离


# ======================================
# 知识条目实体
# ======================================
@dataclass
class KnowledgeEntry:
    """知识条目，和记忆完全分离"""
    # 知识内容
    content: str
    # 知识库类型
    kb_type: KnowledgeBaseType
    # 知识唯一ID
    entry_id: str = field(default_factory=lambda: str(uuid4()))
    # 创建时间
    timestamp: datetime = field(default_factory=datetime.now)
    # 知识标签，用于检索
    tags: List[str] = field(default_factory=list)
    # 优先级，越高越优先注入prompt
    priority: int = 1


# ======================================
# 独立知识库管理器（全局单例）
# ======================================
class KnowledgeBase:
    """
    独立知识库管理器，全局单例
    核心规则：和个人记忆完全物理隔离，绝对避免记忆污染人设/知识
    真人逻辑对齐：对应人脑的常识库，和个人经历记忆完全分开
    """
    _instance = None

    def __new__(cls):
        """单例模式，保证整个进程只有一个知识库管理器"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        """初始化，仅在单例创建时执行一次"""
        # 知识库存储：key=知识库类型，value=知识条目字典
        self._kb: Dict[KnowledgeBaseType, Dict[str, KnowledgeEntry]] = {
            KnowledgeBaseType.PERSONA: {},
            KnowledgeBaseType.GENERAL: {}
        }
        logger.info("独立知识库初始化完成")

    def init_from_kernel(self, persona_knowledge: List[dict], general_knowledge: List[dict]) -> None:
        """
        内核启动时注入知识库，AI层绝对不读本地文件
        参数：
            persona_knowledge: 人设固定知识库内容
            general_knowledge: 通用知识库内容
        """
        # 注入人设知识库
        for entry in persona_knowledge:
            self.add(KnowledgeEntry(
                content=entry["content"],
                kb_type=KnowledgeBaseType.PERSONA,
                tags=entry.get("tags", []),
                priority=entry.get("priority", 1)
            ))
        # 注入通用知识库
        for entry in general_knowledge:
            self.add(KnowledgeEntry(
                content=entry["content"],
                kb_type=KnowledgeBaseType.GENERAL,
                tags=entry.get("tags", []),
                priority=entry.get("priority", 1)
            ))
        logger.info(
            "知识库注入完成",
            persona_count=len(self._kb[KnowledgeBaseType.PERSONA]),
            general_count=len(self._kb[KnowledgeBaseType.GENERAL])
        )

    def add(self, entry: KnowledgeEntry) -> None:
        """
        新增知识条目
        参数：
            entry: 知识条目
        """
        self._kb[entry.kb_type][entry.entry_id] = entry
        logger.debug(
            "新增知识条目完成",
            entry_id=entry.entry_id,
            kb_type=entry.kb_type.value
        )

    def get_persona_knowledge(self) -> List[KnowledgeEntry]:
        """
        获取所有人设知识库内容，每次prompt必须注入
        核心作用：固定人设，避免对话记忆污染人设
        返回：按优先级倒序排序的人设知识条目列表
        """
        entries = list(self._kb[KnowledgeBaseType.PERSONA].values())
        # 按优先级倒序排序
        entries.sort(key=lambda x: x.priority, reverse=True)
        return entries

    def retrieve_general_knowledge(self, query: str, limit: int = 3) -> List[KnowledgeEntry]:
        """
        检索和查询相关的通用知识库内容
        参数：
            query: 查询内容
            limit: 返回的条目数量
        返回：按相关度排序的知识条目列表
        """
        query_keywords = set(query.lower().split())
        scored_entries = []

        for entry in self._kb[KnowledgeBaseType.GENERAL].values():
            match_count = len(query_keywords & set(entry.content.lower().split()))
            # 最终得分 = 匹配数 * 优先级
            score = match_count * entry.priority
            if score > 0:
                scored_entries.append((score, entry))

        # 按得分倒序排序，返回topN
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        result = [entry for score, entry in scored_entries[:limit]]
        logger.debug(
            "通用知识库检索完成",
            query=query[:20],
            result_count=len(result)
        )
        return result

    def get_all_entries(self, kb_type: KnowledgeBaseType = None) -> List[KnowledgeEntry]:
        """获取所有知识条目，用于内核同步"""
        if kb_type:
            return list(self._kb[kb_type].values())
        all_entries = []
        for kb in self._kb.values():
            all_entries.extend(list(kb.values()))
        return all_entries