from typing import Optional, Any

from cradle.schemas.protocol.events.base import BaseEvent
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.selrena.vessel.napcat.napcat_client import NapcatClient
from cradle.selrena.vessel.napcat.memory.short_term import napcat_memory
from cradle.utils.logger import logger

class NapcatResponder:
    """桥接模块：让 Soul 生成的讲话通过 napcat 发回 QQ。

    职责：
    1. 监听感知事件，维护会话上下文 (Last Active User/Group)。
    2. 监听渠道回写动作，将回复文本通过 NapcatClient 发送。
    """
    _installed = False

    def __init__(self):
        # 保存最近一次接收到的用户/群组信息，用于后续回应。
        self._last_user: Optional[int] = None
        self._last_group: Optional[int] = None
        self._client = NapcatClient()

    async def initialize(self):
        if NapcatResponder._installed:
            return
        NapcatResponder._installed = True

        await self._client.initialize()
        
        # 监听感知事件以确立上下文 (主要来源)
        global_event_bus.subscribe("perception.message", self._on_perception)
        
        # 监听渠道回写动作（避免与本地 TTS 的 SpeakAction 耦合）
        global_event_bus.subscribe("action.channel.reply", self._on_speak)
        
        logger.debug("[NapcatResponder] 已初始化")

    async def cleanup(self):
        global_event_bus.unsubscribe_receiver(self)
        await self._client.cleanup()
        logger.debug("[NapcatResponder] 已完成清理")

    async def _on_perception(self, event: BaseEvent):
        """
        处理感知事件，更新最后活跃的联系人信息。
        """
        payload = event.payload
        if not payload:
            return
            
        uid = None
        gid = None
        
        # 1. 从标准载荷对象提取
        if hasattr(payload, "metadata") and isinstance(payload.metadata, dict):
            # Pydantic Model access
            uid = payload.metadata.get("user_id")
            gid = payload.metadata.get("group_id")
            
        # 2. 尝试从字典提取
        elif isinstance(payload, dict):
            # Check metadata dict inside payload dict
            meta = payload.get("metadata")
            if isinstance(meta, dict):
                uid = meta.get("user_id")
                gid = meta.get("group_id")
            
        if isinstance(uid, (int, str)):
            try:
                self._last_user = int(uid)
            except (ValueError, TypeError):
                pass
        
        if isinstance(gid, (int, str)):
            try:
                self._last_group = int(gid)
            except (ValueError, TypeError):
                pass
        
        logger.debug(f"[NapcatResponder] 更新上下文: LastUser={self._last_user}, LastGroup={self._last_group}")

    async def _on_speak(self, event: BaseEvent):
        """
        处理说话动作 (Action: Speak)。
        """
        payload = event.payload
        payload_source = payload if payload is not None else event

        # --- Text Extraction ---
        text = None
        # 1. Direct text field (Dict or Object)
        if isinstance(payload_source, dict):
            text = payload_source.get("text")
        elif hasattr(payload_source, "text"):
            text = getattr(payload_source, "text")
        
        # 2. String Payload
        if text is None and isinstance(payload_source, str):
            text = payload_source

        # 3. Fallback to event.text
        if text is None:
            text = getattr(event, "text", None)

        if not text:
            return

        # --- Target Resolution ---
        target_uid = None
        target_gid = None
        
        # 1. Standard Target Object (AttentionTarget)
        target = None
        if isinstance(payload_source, dict):
            target = payload_source.get("target")
        elif hasattr(payload_source, "target"):
            target = getattr(payload_source, "target")
            
        if target:
            # target 可能是 dict 或 AttentionTarget 对象
            t_meta = getattr(target, "metadata", {}) if hasattr(target, "metadata") else target.get("metadata", {})
            
            # 优先使用显式的 Napcat ID
            if isinstance(t_meta, dict):
                target_uid = t_meta.get("user_id")
                target_gid = t_meta.get("group_id")
            
            # 其次尝试 source_id (需判断 vessel_id)
            t_vessel = getattr(target, "vessel_id", None) if hasattr(target, "vessel_id") else target.get("vessel_id")
            t_src_type = getattr(target, "source_type", None) if hasattr(target, "source_type") else target.get("source_type")
            t_src_id = getattr(target, "source_id", None) if hasattr(target, "source_id") else target.get("source_id")
            
            if (not t_vessel or t_vessel == "napcat") and t_src_id:
                 try:
                     sid_int = int(t_src_id)
                     if t_src_type == "group":
                         target_gid = sid_int
                     elif t_src_type == "private" or t_src_type == "user":
                         target_uid = sid_int
                     elif not target_gid and not target_uid:
                         # Ambiguous ID, defaulting to group usually safer for bots or last context?
                         pass
                 except (ValueError, TypeError):
                     pass

        # 2. Standard Flat Route Fields (Preferred Fallback)
        if target_uid is None and target_gid is None:
            if isinstance(payload_source, dict):
                route_vessel = payload_source.get("vessel_id")
                route_type = payload_source.get("source_type")
                route_id = payload_source.get("source_id")
            else:
                route_vessel = getattr(payload_source, "vessel_id", None)
                route_type = getattr(payload_source, "source_type", None)
                route_id = getattr(payload_source, "source_id", None)

            if (not route_vessel or route_vessel == "napcat") and route_id:
                try:
                    rid = int(route_id)
                    if route_type == "group":
                        target_gid = rid
                    elif route_type in ("private", "user"):
                        target_uid = rid
                except (ValueError, TypeError):
                    pass

        # 3. Context State (Final Fallback)
        if target_uid is None and target_gid is None:
            if self._last_group:
                target_gid = self._last_group
            elif self._last_user:
                target_uid = self._last_user
            else:
                logger.debug("[NapcatResponder] 无可用发送目标")
                return

        # --- Execution ---
        logger.debug(
            f"[NapcatResponder] 发送: '{text[:15]}...' -> U:{target_uid} G:{target_gid}"
        )

        try:
            if target_gid:
                await self._client.reply_group(target_gid, text)
                await napcat_memory.append_async(target_gid, 0, {
                    "role": "assistant", 
                    "content": text, 
                    "metadata": {"source": "Soul", "action": "reply"}
                })
                await napcat_memory.append_artifact_async(target_gid, 0, {
                    "role": "assistant",
                    "text": text,
                    "target_group": target_gid,
                    "source": "Soul",
                })
            elif target_uid:
                await self._client.reply(target_uid, text)
                await napcat_memory.append_async(None, target_uid, {
                    "role": "assistant", 
                    "content": text, 
                    "metadata": {"source": "Soul", "action": "reply"}
                })
                await napcat_memory.append_artifact_async(None, target_uid, {
                    "role": "assistant",
                    "text": text,
                    "target_user": target_uid,
                    "source": "Soul",
                })
        except Exception as e:
            logger.error(f"[NapcatResponder] 发送失败: {e}")