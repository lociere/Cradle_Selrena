# 该文件已使用黑色格式化，内部备注/注释请使用中文说明
"""向量记忆适配器。

本适配器提供可选的向量存储能力，适用于安装了
chromadb 与 sentence-transformers 的环境；
若相关包不可用，则降级为简单的 JSON 文件存储。
"""

import logging
import os
from typing import Any, Dict, List
from pathlib import Path

from selrena._internal.ports import MemoryPort
from selrena._internal.domain.memory import Memory

logger = logging.getLogger(__name__)


class VectorMemoryAdapter(MemoryPort):
    """向量记忆适配器实现。

    持久化目录由 ``persist_dir`` 指定。初始化时会尝试
    导入 chromadb 和 sentence-transformers；如失败则切换
    至普通文件存储。
    """

    def __init__(self, persist_dir: Path, embed_model: str = "all-MiniLM-L6-v2"):
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._embed_model_name = embed_model
        self._client = None
        self._collection = None
        self._model = None
        self._initialized = False
        logger.info(f"VectorMemoryAdapter persist_dir={persist_dir} 初始化")

    def _setup(self):
        try:
            import chromadb
            from chromadb.config import Settings
            from sentence_transformers import SentenceTransformer
        except ImportError:
            # 未安装向量库，后续操作退回到文本文件存储
            logger.warning("chromadb 或 sentence-transformers 未安装，降级为文件存储")
            return

        if self._initialized:
            return

        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name="memory", metadata={"hnsw:space": "cosine"}
        )
        self._model = SentenceTransformer(self._embed_model_name, device="cpu")
        self._initialized = True
        logger.info("VectorMemoryAdapter 已初始化向量后端")

    def _embed(self, text: str) -> List[float]:
        if not self._initialized:
            self._setup()
        if self._model:
            return self._model.encode(text, convert_to_numpy=True).tolist()
        return []

    async def save_memory(self, memory: Memory) -> None:
        """保存一条记忆。

        如果有向量支持则同时存入 embedding。
        否则写为 JSON 文件。
        """
        emb = self._embed(memory.content)
        if self._collection is not None and emb:
            doc_id = f"mem_{os.urandom(4).hex()}"
            self._collection.add(
                ids=[doc_id],
                embeddings=[emb],
                documents=[memory.content],
                metadatas=[memory.to_dict()],
            )
        else:
            file = (
                self.persist_dir / f"{memory.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            )
            import json

            await __import__("asyncio").to_thread(
                file.write_text,
                json.dumps(memory.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    async def retrieve_memories(self, query: str, n_results: int = 5) -> List[Memory]:
        """检索与查询文本相似的记忆。

        优先使用向量检索；无向量时做简单文本匹配。
        """
        if self._collection is not None and self._model:
            emb = self._embed(query)
            results = self._collection.query(
                query_embeddings=[emb], n_results=n_results
            )
            docs = results.get("documents", [[]])[0]
            return [Memory(content=d) for d in docs]

        memories = []
        for f in self.persist_dir.glob("*.json"):
            import json

            data = json.loads(
                await __import__("asyncio").to_thread(f.read_text, encoding="utf-8")
            )
            mem = Memory.from_dict(data)
            if query.lower() in mem.content.lower():
                memories.append(mem)
        return memories[:n_results]

    async def delete_memory(self, memory_id: str) -> None:
        """删除指定 id 的记忆文件。"""
        file = self.persist_dir / f"{memory_id}.json"
        if file.exists():
            await __import__("asyncio").to_thread(file.unlink)


__all__ = ["VectorMemoryAdapter"]
