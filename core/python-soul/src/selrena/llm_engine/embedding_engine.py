"""
向量嵌入引擎 — 为知识库提供语义检索能力

设计原则：
1. 懒加载：不在 import 时加载模型，仅在 load() 被显式调用后才初始化
2. 优雅降级：sentence-transformers 未安装或模型加载失败时，is_available() 返回 False，
   知识库自动退化为纯关键词检索，不影响系统启动
3. 线程安全：encode / cosine_similarities 本身无状态副作用，可在 asyncio.to_thread 中调用
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

import numpy as np

from selrena.core.observability.logger import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger("embedding_engine")


class EmbeddingEngine:
    """基于 sentence-transformers 的向量嵌入引擎。"""

    def __init__(self) -> None:
        self._model: Optional[SentenceTransformer] = None
        self._available: bool = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def load(self, model_path: str, device: str = "cpu") -> bool:
        """加载嵌入模型，返回是否加载成功。"""
        resolved = Path(model_path)
        if not resolved.exists():
            logger.warning("嵌入模型路径不存在，向量引擎不可用", path=str(resolved))
            return False

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.warning("sentence-transformers 未安装，向量引擎不可用")
            return False

        try:
            self._model = SentenceTransformer(str(resolved), device=device)
            self._available = True
            logger.info("向量嵌入引擎加载成功", model=str(resolved), device=device)
            return True
        except Exception as exc:
            logger.warning("嵌入模型加载失败", error=str(exc))
            self._model = None
            self._available = False
            return False

    def is_available(self) -> bool:
        """引擎是否就绪。"""
        return self._available and self._model is not None

    # ------------------------------------------------------------------
    # 编码
    # ------------------------------------------------------------------

    def encode(self, texts: List[str]) -> np.ndarray:
        """批量编码文本，返回 shape=(N, dim) 的向量矩阵。"""
        assert self._model is not None, "EmbeddingEngine 未加载"
        vectors: np.ndarray = self._model.encode(
            texts, show_progress_bar=False, convert_to_numpy=True
        )
        return vectors

    def encode_single(self, text: str) -> np.ndarray:
        """编码单条文本，返回 shape=(dim,) 的一维向量。"""
        return self.encode([text])[0]

    # ------------------------------------------------------------------
    # 相似度
    # ------------------------------------------------------------------

    @staticmethod
    def cosine_similarities(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """计算 query_vec 与 matrix 中每行的余弦相似度。

        参数:
            query_vec: shape=(dim,)
            matrix: shape=(N, dim)
        返回:
            shape=(N,) 的相似度数组，值域 [-1, 1]
        """
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return np.zeros(matrix.shape[0])
        row_norms = np.linalg.norm(matrix, axis=1)
        # 避免除以零
        row_norms = np.where(row_norms == 0, 1.0, row_norms)
        return (matrix @ query_vec) / (row_norms * query_norm)
