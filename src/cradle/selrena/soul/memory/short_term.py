import json
import os
from typing import List, Dict, Any
from cradle.utils.path import ProjectPath
from cradle.utils.logger import logger
from cradle.schemas import Message

class ShortTermMemory:
    """
    短期记忆管理器 (持久化 + 滑动窗口)
    负责存储当前对话上下文，并在系统重启时恢复记忆。
    """
    def __init__(self, max_history_len: int = 20):
        self.max_history_len = max_history_len  # 只保留最近 N 轮对话
        self.file_path = ProjectPath.DATA_MEMORY / "short_term.json"
        self.messages: List[Message] = []
        
        # 初始化时尝试加载现有记忆
        self.load()

    def add(self, role: str, content: str):
        """添加一条新记忆"""
        msg = Message(role=role, content=content)
        self.messages.append(msg)
        
        # 触发自动修剪和保存
        self._trim()
        self.save()

    def get_messages(self, include_system: bool = False, system_prompt: str = "") -> List[Dict[str, str]]:
        """
        获取用于 LLM 调用的消息列表
        :param include_system: 是否临时在头部拼接 System Prompt
        """
        payload = [msg.model_dump(include={'role', 'content'}) for msg in self.messages]
        
        if include_system and system_prompt:
            # System Prompt 永远在最前，且不算在滑动窗口内
            system_msg = {"role": "system", "content": system_prompt}
            return [system_msg] + payload
            
        return payload

    def save(self):
        """持久化到磁盘"""
        try:
            data = [msg.model_dump() for msg in self.messages]
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"记忆保存失败: {e}")

    def load(self):
        """从磁盘恢复记忆"""
        if not self.file_path.exists():
            return

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 反序列化为 Message 对象
                self.messages = [Message(**item) for item in data]
            logger.info(f"成功恢复短期记忆: {len(self.messages)} 条记录")
        except Exception as e:
            logger.error(f"记忆文件损坏，已重置: {e}")
            self.messages = []

    def clear(self):
        """清空记忆 (用于重置人格或开始新话题)"""
        self.messages = []
        self.save()
        logger.info("短期记忆已擦除。")

    def _trim(self):
        """修剪记忆，保持上下文在窗口范围内"""
        if len(self.messages) > self.max_history_len:
            # 移除最早的记忆 (保留最新的 max_history_len 条)
            removed_count = len(self.messages) - self.max_history_len
            self.messages = self.messages[removed_count:]
            # logger.debug(f"记忆修剪: 遗忘了早期的 {removed_count} 条对话")
