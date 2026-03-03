import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath
from cradle.core.config_manager import global_config

class NapcatShortTermMemory:
    """
    Napcat 专用的短时记忆模块 (Session-Based Memory)
    
    用于存储不同会话 (Group/Private) 的上下文历史。
    仅在 Napcat 内部闭环使用，不与 Soul 的全局记忆混淆。
    
    【持久化升级】：
    现在将每个会话的历史记录持久化到文件系统：
    - 私聊: data/memory/napcat/users/{user_id}.json
    - 群聊: data/memory/napcat/groups/{group_id}.json
    """
    def __init__(self, max_history: int = 50):
        # 基础存储路径
        try:
             self.base_dir = ProjectPath.DATA_DIR / "memory" / "napcat"
             self.groups_dir = self.base_dir / "groups"
             self.users_dir = self.base_dir / "users"
        
             # 确保目录存在
             self.groups_dir.mkdir(parents=True, exist_ok=True)
             self.users_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
             # Fallback if ProjectPath is not fully initialized or path issue
             logger.error(f"[NapcatMemory] Path Init Failed: {e}")
             self.base_dir = Path("data/memory/napcat")
             self.groups_dir = self.base_dir / "groups"
             self.users_dir = self.base_dir / "users"
        
        # Load from config or use default of 50
        self.max_history = global_config.get("napcat.silent_record_window", max_history)

    def _get_file_path(self, group_id: Optional[int], user_id: int) -> Path:
        """根据会话类型生成文件路径"""
        if group_id:
            return self.groups_dir / f"{group_id}.json"
        
        # 确保 private chat 的 user_id 是有效的
        if not user_id:
            return self.base_dir / "system.json"
            
        return self.users_dir / f"{user_id}.json"

    def _load(self, path: Path) -> List[Dict[str, Any]]:
        """从文件加载历史记录"""
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"[NapcatMemory] 加载记忆失败 {path}: {e}")
            return []

    def _save(self, path: Path, data: List[Dict[str, Any]]):
        """保存历史记录到文件"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NapcatMemory] 保存记忆失败 {path}: {e}")

    def append(self, group_id: Optional[int], user_id: int, message: Dict[str, Any]):
        """
        追加一条消息到对应的会话文件
        
        :param group_id: 群号
        :param user_id: 用户号
        :param message: 消息字典对象
        """
        path = self._get_file_path(group_id, user_id)
        
        # 加载现有记录
        history = self._load(path)
        
        # 确保消息包含时间戳
        if "timestamp" not in message:
            message["timestamp"] = time.time()
            
        # 补充 Bot 信息
        if message.get("role") == "assistant":
            if "name" not in message:
                message["name"] = "Selrena"
        
        history.append(message)
        
        # 裁剪 (FIFO)
        if len(history) > self.max_history:
            history = history[-self.max_history:]
            
        self._save(path, history)

    def get_context(self, group_id: Optional[int], user_id: int) -> List[Dict[str, Any]]:
        """获取完整上下文"""
        path = self._get_file_path(group_id, user_id)
        return self._load(path)

# 全局单例
napcat_memory = NapcatShortTermMemory()
