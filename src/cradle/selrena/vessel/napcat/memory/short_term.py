import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath
from cradle.core.config_manager import global_config
from cradle.schemas.domain.chat import Message
from cradle.schemas.domain.multimodal import ContentBlock

class NapcatShortTermMemory:
    """
    Napcat 会话级短时记忆。

    职责：
    1) 按会话维度持久化消息历史（群聊 / 私聊）。
    2) 提供原始历史读取（供协议层内部使用）。
    3) 提供面向 Soul 的“去噪历史视图”（仅保留语义必要信息）。

    存储布局：
    - 私聊：data/memory/napcat/users/{user_id}.json
    - 群聊：data/memory/napcat/groups/{group_id}.json
    """
    def __init__(self, max_history: int = 50):
        self.max_history = int(global_config.get("napcat.silent_record_window", max_history))
        self.base_dir, self.groups_dir, self.users_dir = self._init_storage_paths()
        self.artifacts_dir, self.artifact_groups_dir, self.artifact_users_dir = self._init_artifact_paths()

    def _init_storage_paths(self) -> tuple[Path, Path, Path]:
        try:
            base_dir = ProjectPath.DATA_DIR / "memory" / "napcat"
        except Exception as e:
            logger.error(f"[NapcatMemory] Path Init Failed: {e}")
            base_dir = Path("data/memory/napcat")

        groups_dir = base_dir / "groups"
        users_dir = base_dir / "users"
        groups_dir.mkdir(parents=True, exist_ok=True)
        users_dir.mkdir(parents=True, exist_ok=True)
        return base_dir, groups_dir, users_dir

    def _init_artifact_paths(self) -> tuple[Path, Path, Path]:
        artifacts_dir = self.base_dir / "artifacts"
        artifact_groups_dir = artifacts_dir / "groups"
        artifact_users_dir = artifacts_dir / "users"
        artifact_groups_dir.mkdir(parents=True, exist_ok=True)
        artifact_users_dir.mkdir(parents=True, exist_ok=True)
        return artifacts_dir, artifact_groups_dir, artifact_users_dir

    def _get_file_path(self, group_id: Optional[int], user_id: int) -> Path:
        """根据会话标识解析持久化文件路径。"""
        if group_id:
            return self.groups_dir / f"{group_id}.json"

        if not user_id:
            return self.base_dir / "system.json"

        return self.users_dir / f"{user_id}.json"

    def _get_artifact_file_path(self, group_id: Optional[int], user_id: int) -> Path:
        if group_id:
            return self.artifact_groups_dir / f"{group_id}.json"
        if not user_id:
            return self.artifacts_dir / "system.json"
        return self.artifact_users_dir / f"{user_id}.json"

    def _load(self, path: Path) -> List[Dict[str, Any]]:
        """读取历史文件。读取失败时返回空列表并记录日志。"""
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"[NapcatMemory] 加载记忆失败 {path}: {e}")
            return []

    def _save(self, path: Path, data: List[Dict[str, Any]]) -> None:
        """
        原子写入历史文件。

        先写入 .tmp 再替换目标文件，降低写入中断导致文件损坏的风险。
        """
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp_path.replace(path)
        except Exception as e:
            logger.error(f"[NapcatMemory] 保存记忆失败 {path}: {e}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _normalize_message_for_store(message: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化待存储消息（使用标准 Message schema 验证）。
        
        注意：metadata 字段已被移除，所有协议细节应存入 artifacts。
        """
        try:
            # 使用标准 Message schema 进行验证和标准化
            msg_model = Message(**message)
            return {
                "role": msg_model.role,
                "content": msg_model.content,
                "timestamp": msg_model.timestamp,
            }
        except Exception as e:
            logger.warning(f"[NapcatMemory] Message validation failed: {e}, falling back to dict normalization")
            # Fallback: 手动标准化
            msg = dict(message)
            role = msg.get("role")
            content = msg.get("content")
            return {
                "role": role,
                "content": content,
                "timestamp": msg.get("timestamp", time.time()),
            }

    @staticmethod
    def _normalize_artifact_message(message: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化 Artifact 消息（使用标准 Message schema 验证基础字段）。
        
        NapcatArtifact 继承自 Message，因此可以使用 Message 进行基础验证。
        额外字段（msg_id, reply_to 等）保留在 dict 中。
        """
        try:
            # 提取 Message 标准字段进行验证
            msg_data = {
                "role": message.get("role", "user"),
                "content": message.get("content", ""),
                "timestamp": message.get("timestamp", time.time()),
            }
            msg_model = Message(**msg_data)
            
            # 保留所有额外字段（Napcat 专用协议字段）
            normalized = msg_model.model_dump()
            for key, value in message.items():
                if key not in normalized:
                    normalized[key] = value
            
            return normalized
        except Exception as e:
            logger.warning(f"[NapcatMemory] Artifact validation failed: {e}, falling back to dict normalization")
            msg = dict(message)
            if "timestamp" not in msg:
                msg["timestamp"] = time.time()
            return msg

    def _trim_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按 max_history 做 FIFO 裁剪。"""
        if self.max_history <= 0:
            return history
        if len(history) <= self.max_history:
            return history
        return history[-self.max_history:]

    @staticmethod
    def _extract_text_from_content(content: Any) -> str:
        """
        从 content 中提取可用于上下文构建的文本语义。

        - str: 直接返回。
        - list[ContentBlock-like]: 聚合 text 块。
        - 仅媒体无文本: 返回统一占位语义，避免传递原始 URL。
        """
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            texts: list[str] = []
            has_media = False
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type")
                    if block_type == "text":
                        text = block.get("text")
                        if isinstance(text, str) and text.strip():
                            texts.append(text.strip())
                    elif block_type in ("image_url", "video_url", "audio_url"):
                        has_media = True
                else:
                    block_type = getattr(block, "type", None)
                    block_text = getattr(block, "text", None)
                    if block_type == "text" and isinstance(block_text, str) and block_text.strip():
                        texts.append(block_text.strip())
                    elif block_type in ("image_url", "video_url", "audio_url"):
                        has_media = True

            merged = " ".join(texts).strip()
            if merged:
                return merged
            if has_media:
                return "[用户发送了媒体内容]"

        return ""

    def _sanitize_for_soul(self, history: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """
        生成给 Soul 的精简历史视图（仅保留纯会话语义，不含任何 metadata）。

        规则：
        1) 仅保留 user/assistant/system。
        2) 仅保留语义文本内容。
        3) 去除连续重复消息。
        4) 按 limit 截断最近窗口。
        """
        compact: List[Dict[str, Any]] = []

        for item in history:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            if role not in ("user", "assistant", "system"):
                continue

            text = self._extract_text_from_content(item.get("content"))
            if not text:
                continue

            normalized = {
                "role": role,
                "content": text,
            }

            # 连续重复去重（同角色 + 同文本）
            if compact and compact[-1].get("role") == normalized["role"] and compact[-1].get("content") == normalized["content"]:
                continue

            compact.append(normalized)

        if limit > 0:
            compact = compact[-limit:]

        return compact

    def append(self, group_id: Optional[int], user_id: int, message: Dict[str, Any]) -> None:
        """同步追加一条消息到会话历史。"""
        path = self._get_file_path(group_id, user_id)
        history = self._load(path)
        normalized_message = self._normalize_message_for_store(message)
        normalized_message["content"] = self._extract_text_from_content(normalized_message.get("content"))
        if not normalized_message["content"]:
            return

        history.append(normalized_message)
        history = self._trim_history(history)
        self._save(path, history)

    async def append_async(self, group_id: Optional[int], user_id: int, message: Dict[str, Any]) -> None:
        """异步追加消息（通过线程池封装同步文件 IO）。"""
        await asyncio.to_thread(self.append, group_id, user_id, message)

    def append_artifact(self, group_id: Optional[int], user_id: int, message: Dict[str, Any]) -> None:
        path = self._get_artifact_file_path(group_id, user_id)
        history = self._load(path)
        history.append(self._normalize_artifact_message(message))

        artifact_limit = int(global_config.get("napcat.artifact_window", max(self.max_history, 200)))
        if artifact_limit > 0 and len(history) > artifact_limit:
            history = history[-artifact_limit:]

        self._save(path, history)

    async def append_artifact_async(self, group_id: Optional[int], user_id: int, message: Dict[str, Any]) -> None:
        await asyncio.to_thread(self.append_artifact, group_id, user_id, message)

    def get_context(
        self,
        group_id: Optional[int],
        user_id: int,
        *,
        for_soul: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        读取会话历史。

        Args:
            for_soul: True 返回去噪后的精简视图；False 返回原始存储历史。
        """
        path = self._get_file_path(group_id, user_id)
        history = self._load(path)

        if not for_soul:
            return history

        window = int(global_config.get("napcat.external_history_window", 20))
        return self._sanitize_for_soul(history, limit=window)

    async def get_context_async(
        self,
        group_id: Optional[int],
        user_id: int,
        *,
        for_soul: bool = False,
    ) -> List[Dict[str, Any]]:
        """异步读取会话历史。"""
        return await asyncio.to_thread(
            self.get_context,
            group_id,
            user_id,
            for_soul=for_soul,
        )

    def get_artifacts(self, group_id: Optional[int], user_id: int) -> List[Dict[str, Any]]:
        path = self._get_artifact_file_path(group_id, user_id)
        return self._load(path)

    async def get_artifacts_async(self, group_id: Optional[int], user_id: int) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.get_artifacts, group_id, user_id)

# 全局单例
napcat_memory = NapcatShortTermMemory()
