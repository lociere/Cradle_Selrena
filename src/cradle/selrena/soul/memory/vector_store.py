import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import logging
# 引入 transformers 日志控制以屏蔽加载噪音
from transformers import logging as transformers_logging

from cradle.core.config_manager import global_config
from cradle.utils.logger import logger

class MemoryVessel:
    """
    Project Mnemosyne: CPU-Native Vector Store
    
    专为消费级显卡优化的向量记忆容器。
    特点:
    1. 强制 CPU 运行 Embedding 模型，零显存占用。
    2. 使用 ChromaDB 的轻量化本地持久化。
    3. 支持 'm3e-small' 等高效中文小模型。
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryVessel, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logger
        self.persist_dir = os.path.join(os.getcwd(), "data", "memory", "vector_store")
        self._embed_model = None
        self._is_ready = False
        
        # 1. 初始化 ChromaDB (持久化模式) - 轻量级操作
        # moved from init to keep instantiation fast, 
        # but Chroma client init is relatively fast so we can keep it or move it.
        # Let's move it to initialize to be safe.
        self._client = None
        self.episodic_collection = None
        self.skill_collection = None
        
        self.logger.debug("[MemoryVessel] 容器实例已创建 (等待初始化)")
        self._initialized = True

    def initialize(self):
        """【同步阻塞】显式初始化 (加载模型与数据库)"""
        if self._is_ready:
            return

        self.logger.info(f"[MemoryVessel] 正在挂载记忆扇区...")
        
        # 1. 链接数据库
        if not self._client:
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self.episodic_collection = self._get_collection("episodic_memory")
            self.skill_collection = self._get_collection("skill_memory")
        
        # 2. 初始化 Embedding 模型 (CPU Mode)
        # 尝试定位本地模型
        local_model_path = os.path.join(os.getcwd(), "assets", "models", "m3e-small")
        model_name_or_path = local_model_path if os.path.exists(local_model_path) else "moka-ai/m3e-small"
        
        self.logger.info(f"[MemoryVessel] 加载 Embedding 模型: {os.path.basename(model_name_or_path)} (Force CPU)")
        
        try:
            # device="cpu" 是关键!
            # 临时屏蔽 transformers 的警告
            transformers_logging.set_verbosity_error()
            self._embed_model = SentenceTransformer(model_name_or_path, device="cpu")
            transformers_logging.set_verbosity_warning() 
            
            self._is_ready = True
            self.logger.info("[MemoryVessel] 记忆核心就绪 (0MB VRAM)")
        except Exception as e:
            self.logger.critical(f"[MemoryVessel] Embedding 模型加载失败: {e}")
            raise e

    def _get_collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"} # 使用余弦相似度
        )

    def _generate_embedding(self, text: str) -> List[float]:
        """生成向量 (CPU)"""
        if not text:
            return []
        if not self._embed_model:
            self.logger.warning("[MemoryVessel] ⚠️ 尝试在初始化前使用 Embedding 模型! 正触发自动初始化...")
            self.initialize()
            
        # encode 返回 numpy array, 需转 list
        return self._embed_model.encode(text, convert_to_numpy=True).tolist()

    def memorize_episode(self, text: str, metadata: Dict[str, Any] = None):
        """记录情节记忆 (对话摘要)"""
        if not text:
            return
            
        embedding = self._generate_embedding(text)
        doc_id = f"ep_{os.urandom(4).hex()}"
        
        self.episodic_collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}]
        )
        # self.logger.debug(f"[Memory] 已归档情节: {text[:20]}...")

    def recall_episode(self, query: str, n_results: int = 3) -> List[str]:
        """回忆情节 (相关对话)"""
        if not query:
            return []
            
        embedding = self._generate_embedding(query)
        
        results = self.episodic_collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )
        
        # Chroma 返回的是 [[doc1, doc2]] 这种结构
        if results and results["documents"]:
            return results["documents"][0]
        return []

    def memorize_skill(self, description: str, code: str):
        """记录技能 (代码片段)"""
        embedding = self._generate_embedding(description)
        doc_id = f"skill_{os.urandom(4).hex()}"
        
        self.skill_collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[code],
            metadatas={"description": description}
        )
        self.logger.info(f"[Memory] 习得新技能: {description}")

    def recall_skill(self, query: str, n_results: int = 1) -> List[Dict[str, str]]:
        """检索技能"""
        embedding = self._generate_embedding(query)
        results = self.skill_collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )
        
        skills = []
        if results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            for i in range(len(docs)):
                skills.append({
                    "description": metas[i].get("description", ""),
                    "code": docs[i]
                })
        return skills

# 全局单例
global_memory_vessel = MemoryVessel()
