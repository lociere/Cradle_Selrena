import time
from typing import Any

from cradle.core.config_manager import global_config
from cradle.core.lifecycle import global_lifecycle
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.schemas.protocol.events.perception import (
    ExternalMultiModalPayload,
    InternalMultiModalPayload,
)
from cradle.schemas.protocol.events.reflex import ReflexSignal, ReflexType
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger

from .attention import global_attention, AttentionTarget

class Reflex:
    """
    脊髓层 (Layer 1): 负责快速反射、生存本能、唤醒机制与意识流编排。
    不经过深度思考，直接拦截或触发行为，并决定哪些输入可上行到意识层。
    
    【架构升级】：
    引入 AttentionManager 管理多会话活跃状态 (Continuous Conversation)。
    """

    def __init__(self):
        self.bus = global_event_bus
        perception_cfg = global_config.get_system().perception
        
        # [Config]
        # strict_wake_word:
        #   True  -> 每一句话都必须带唤醒词才能上行
        #   False -> 宽松模式，唤醒后维持一段时间的活跃窗口
        self.strict_wake = False # Default to Relaxed Mode for chat continuity
        
        self.wake_timeout = float(getattr(perception_cfg, "wake_timeout_sec", 30.0))
        
        self.stop_keywords = ["别说", "闭嘴", "停下", "stop", "shutup", "quiet"]
        self.exit_keywords = ["休眠", "shutdown", "sleep"]
        
        logger.info(f"[Reflex] 脊髓反射中枢初始化 | 唤醒窗口: {self.wake_timeout}s | 严格模式: {self.strict_wake}")

    async def initialize(self):
        # 订阅 Layer2 规整后的外围输入
        self.bus.subscribe("synapse.layer2.ingress", self.on_layer2_ingress)
        global_lifecycle.register(self)

    async def cleanup(self):
        if hasattr(global_lifecycle, "unregister"):
            pass
        self.bus.unsubscribe_receiver(self)

    def _parse_perception_payload(
        self,
        payload: dict[str, Any],
    ) -> ExternalMultiModalPayload | InternalMultiModalPayload | None:
        if not isinstance(payload, dict):
            return None

        try:
            if payload.get("is_external_source") is True:
                return ExternalMultiModalPayload.model_validate(payload)
            return InternalMultiModalPayload.model_validate(payload)
        except Exception as e:
            logger.warning(f"[Reflex] 感知载荷校验失败，丢弃本次输入: {e}")
            return None

    @staticmethod
    def _extract_text_content(content: list[Any]) -> str:
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
                continue

            block_type = getattr(block, "type", None)
            block_text = getattr(block, "text", None)
            if block_type == "text" and isinstance(block_text, str):
                text_parts.append(block_text)

        return "".join(text_parts)

    async def on_layer2_ingress(self, event: BaseEvent):
        payload = event.payload if hasattr(event, "payload") else {}
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not isinstance(payload, dict):
            return

        typed_payload = self._parse_perception_payload(payload)
        if typed_payload is None:
            return

        # 1. 提取元数据
        content = typed_payload.content
        text_content = self._extract_text_content(content)
        
        text_match = text_content.strip().lower()
        
        # 2. 紧急停止反射 (Immediate Halt)
        if any(w in text_match for w in self.stop_keywords):
            logger.warning(f"[Reflex] 🔔 收到停止指令: {text_match}")
            signal = ReflexSignal(reflex_type=ReflexType.MUTE, source="Reflex")
            await self.bus.publish(signal)
            # 停止指令本身不上行
            return

        # 3. 注意力与唤醒决策 (The Gating Logic)
        # [Decoupled Architecture]
        # Reflex 只负责处理通过 Vessel 标准协议头传递的 Attention 信息
        # 不再尝试解析 payload 内部的业务字段 (如 user_id, group_id)
        
        # 1. 构建标准注意力目标 (AttentionTarget)
        target = AttentionTarget.from_payload(payload)
        
        # 如果缺少 Attention 元数据，则视为不需要唤醒管理的普通事件或异常
        # 但为了避免静默失败，我们可以选择放行无唤醒管理的事件，或者直接丢弃
        # 在强唤醒机制下，没有 ID 的事件无法被追踪状态，理应丢弃或作为系统噪音处理
        if not target:
             # 尝试兼容旧代码：如果 payload 里没有标准头，但有 content，可能是一个裸消息？
             # 暂时策略：Fail safe -> ignore
             # logger.debug(f"[Reflex] 忽略无上下文标识的事件: keys={list(payload.keys())}")
             return

        full_context_path = str(target)
        
        # 2. 检查唤醒状态 (Check Wake Status)
        # a) 强唤醒 (Strong Wake): 明确包含唤醒词或提到机器人名字
        # b) 活跃窗口 (Active Window): 最近有交互，处于持续对话中
        
        is_strong_wake = bool(payload.get("is_strong_wake", False))
        
        # 使用标准接口检查活跃状态
        is_active_session = global_attention.is_active(target)
        
        should_process = False

        if is_strong_wake:
            logger.info(f"[Reflex] 🔥 强唤醒触发: {full_context_path}")
            should_process = True
            # 激活/刷新注意力窗口
            global_attention.focus(target, ttl=self.wake_timeout)
            
        elif is_active_session:
            logger.info(f"[Reflex] 🟢 持续对话窗口活跃: {full_context_path}")
            should_process = True
            # 延续窗口 (Reset TTL)
            global_attention.focus(target, ttl=self.wake_timeout)
            
        elif not self.strict_wake:
             # 非严格模式下，也许允许通过？但在新架构下，通常默认 strict_wake=True 或者依靠 is_active_session
             # 这里保持保守策略: 如果既不是强唤醒也不是活跃会话，则忽略
             # 除非配置允许 loose mode
             logger.debug(f"[Reflex] 💤 忽略非唤醒消息: {text_match[:20]}...")
             pass
             
        if not should_process:
            return

        # 4. 上行至意识层 (Conscious Stream)
        # 完完全全透传 Payload，Reflex 不做任何业务修改，只负责打上 Session 标记
        
        conscious_payload = payload.copy()
        conscious_payload.update({
            "session_id": full_context_path,  # 全局唯一会话 ID
            "timestamp": time.time(),
            "reflex_checked": True            # 标记已通过反射层校验
        })
        
        logger.info(f"[Reflex] >>> 意识流推送 (至 Soul): {full_context_path}")
        await self.bus.publish(BaseEvent(
            name="input.user_message",
            payload=conscious_payload,
            source="Reflex"
        ))
