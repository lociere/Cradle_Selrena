from typing import Dict, Optional, Set, Union
from dataclasses import dataclass
import time
from cradle.utils.logger import logger
from cradle.schemas.protocol.events.perception import PerceptionPayload

@dataclass
class AttentionTarget:
    """
    标准注意力目标 (Standard Attention Target)

    作为系统通用的注意力焦点描述符，解耦具体 Vessel 实现。
    """
    vessel_id: str
    context_type: str  # 对应 source_type (e.g. 'group', 'private')
    subject_id: str    # 对应 source_id (e.g. '123456')

    @classmethod
    def from_payload(cls, payload: Union[PerceptionPayload, dict]) -> Optional["AttentionTarget"]:
        """从标准多模态载荷提取注意力目标"""
        if isinstance(payload, dict):
            # 兼容字典格式 (Legacy Support)
            v_id = payload.get("vessel_id")
            c_type = payload.get("source_type")
            s_id = payload.get("source_id")
        else:
            # 标准 Pydantic 模型
            v_id = payload.vessel_id
            c_type = payload.source_type
            s_id = payload.source_id

        if v_id and c_type and s_id:
            return cls(vessel_id=v_id, context_type=c_type, subject_id=s_id)
        return None

    def __str__(self):
        return f"{self.vessel_id}:{self.context_type}:{self.subject_id}"


class AttentionContext:
    """
    单个注意力上下文分支 (Attention Branch/Context)
    
    管理特定类型对象的状态集合。
    例如: "group_chats" (群聊), "private_chats" (私聊), "tasks" (任务)
    """
    def __init__(self, name: str, parent: str, default_ttl: float = 30.0):
        self.name = name
        self.parent = parent
        self.default_ttl = default_ttl
        self._states: Dict[str, float] = {}   # id -> expire_timestamp
        self._pinned: Set[str] = set()

    def focus(self, obj_id: str, duration: Optional[float] = None):
        """
        激活/刷新该分支下的某个对象状态
        :param obj_id: 对象ID (如群号 "12345")
        :param duration: 持续时间(秒)。若不传则使用分支默认TTL。
        """
        ttl = duration if duration is not None else self.default_ttl
        if ttl <= 0:
            self.release(obj_id)
            return
            
        self._states[obj_id] = time.time() + ttl
        logger.debug(f"[Attention:{self.parent}/{self.name}] Focus '{obj_id}' for {ttl}s")

    def release(self, obj_id: str):
        if obj_id in self._states:
            del self._states[obj_id]
            logger.debug(f"[Attention:{self.parent}/{self.name}] Release '{obj_id}'")

    def is_active(self, obj_id: str) -> bool:
        if obj_id in self._pinned:
            return True
        expiry = self._states.get(obj_id)
        if expiry and time.time() < expiry:
            return True
        return False
        
    def pin(self, obj_id: str, active: bool = True):
        if active:
            self._pinned.add(obj_id)
        else:
            self._pinned.discard(obj_id)

    def cleanup(self):
        now = time.time()
        expired = [k for k, v in self._states.items() if v < now]
        for k in expired:
            del self._states[k]

class VesselAttention:
    """
    模块级注意力管理器 (Vessel Module Attention)
    
    对应系统架构中的一级 Vessel 模块 (e.g. Napcat, Vision, Voice)。
    作为命名空间，下辖多个 AttentionContext 分支。
    """
    def __init__(self, name: str):
        self.name = name
        self._contexts: Dict[str, AttentionContext] = {}

    def get_context(self, context_name: str, default_ttl: float = 30.0) -> AttentionContext:
        """
        获取或创建下级状态分支 (State Branch)
        :param context_name: 分支名 (e.g. 'group', 'private', 'task')
        """
        if context_name not in self._contexts:
            self._contexts[context_name] = AttentionContext(name=context_name, parent=self.name, default_ttl=default_ttl)
        return self._contexts[context_name]
    
    def cleanup(self):
        for ctx in self._contexts.values():
            ctx.cleanup()


class AttentionManager:
    """
    中央注意力状态管理器 (Central Attention Registry)
    
    Hierarchy:
      Manager -> Vessel (Module) -> Branch (Context) -> Item (State)
    
    Usage (Standard):
      target = AttentionTarget(vessel_id="napcat", context_type="group", subject_id="123")
      global_attention.focus(target, ttl=60)
    """
    def __init__(self):
        self._vessels: Dict[str, VesselAttention] = {}

    def get_vessel(self, name: str) -> VesselAttention:
        """
        获取 Vessel 模块的注意力控制器 (底层 API)
        """
        if name not in self._vessels:
            self._vessels[name] = VesselAttention(name)
        return self._vessels[name]

    def focus(self, target: AttentionTarget, ttl: Optional[float] = None):
        """
        [标准接口] 激活指定目标的注意力
        """
        vessel = self.get_vessel(target.vessel_id)
        # 默认 TTL 由 Branch 管理，这里传递 None 表示使用默认值，或者是具体数值
        ctx = vessel.get_context(target.context_type)
        ctx.focus(target.subject_id, duration=ttl)

    def is_active(self, target: AttentionTarget) -> bool:
        """
        [标准接口] 检查目标是否处于活跃状态
        """
        if target.vessel_id not in self._vessels:
            return False
        vessel = self._vessels[target.vessel_id]
        if target.context_type not in vessel._contexts:
            return False
        return vessel.get_context(target.context_type).is_active(target.subject_id)
        
    def cleanup_all(self):
        for vessel in self._vessels.values():
            vessel.cleanup()

# 全局单例
global_attention = AttentionManager()
