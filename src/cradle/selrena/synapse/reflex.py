import re
import time
from typing import Any, List, Optional, Dict

from cradle.core.config_manager import global_config
from cradle.core.lifecycle import global_lifecycle
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.schemas.protocol.events.reflex import ReflexSignal, ReflexType
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger

from .attention import global_attention

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

    async def on_layer2_ingress(self, event: BaseEvent):
        # 兼容 Event 对象或 Pydantic 对象
        payload = event.payload if hasattr(event, "payload") else {}
        if not isinstance(payload, dict):
             return

        # 1. 提取元数据
        content = payload.get("content", []) # Standardized content list
        text_content = ""
        
        # 简易文本提取用于关键词匹配
        if isinstance(content, str):
             text_content = content
        elif isinstance(content, list):
             for block in content:
                  if isinstance(block, dict) and block.get("type") == "text":
                       text_content += block.get("text", "")
        
        text_match = text_content.strip().lower()
        
        # 2. 紧急停止反射 (Immediate Halt)
        if any(w in text_match for w in self.stop_keywords):
            logger.warning(f"[Reflex] 🔔 收到停止指令: {text_match}")
            signal = ReflexSignal(reflex_type=ReflexType.MUTE, source="Reflex")
            await self.bus.publish(signal)
            # 停止指令本身不上行
            return

        # 3. 注意力与唤醒决策 (The Gating Logic)
        source = event.source or "unknown"
        
        # [Decoupled Architecture]
        # Reflex 只负责处理通过 Vessel 标准协议头传递的 Attention 信息
        # 不再尝试解析 payload 内部的业务字段 (如 user_id, group_id)
        
        # 1. Vessel Origin & Context (Identity)
        vessel_name = payload.get("vessel_id")
        branch_name = payload.get("source_type")       # e.g. 'group', 'private', 'task'
        item_id     = payload.get("source_id")         # e.g. '123456'
        
        # 如果缺少 Attention 元数据，则视为不需要唤醒管理的普通事件或异常
        # 但为了避免静默失败，我们可以选择放行无唤醒管理的事件，或者直接丢弃
        # 在强唤醒机制下，没有 ID 的事件无法被追踪状态，理应丢弃或作为系统噪音处理
        if not (vessel_name and branch_name and item_id):
             # 尝试兼容旧代码：如果 payload 里没有标准头，但有 content，可能是一个裸消息？
             # 暂时策略：Fail safe -> ignore
             # logger.debug(f"[Reflex] 忽略无上下文标识的事件: keys={list(payload.keys())}")
             return

        full_context_path = f"{vessel_name}:{branch_name}:{item_id}"
        
        # 2. Get Attention Context: 获取注意力分支上下文
        vessel_mgr = global_attention.get_vessel(vessel_name)
        
        # [Configuration]: TTL 策略应由 Cortex 指定或使用系统默认
        # 简化版：统一使用配置的 wake_timeout
        branch_ttl = self.wake_timeout
             
        # 获取或创建注意力上下文
        attn_context = vessel_mgr.get_context(branch_name, default_ttl=branch_ttl)
        
        # [Input Signals]: 输入信号
        # 仅依赖 Cortex 明确给出的布尔信号 (是否强唤醒)
        is_strong_wake = payload.get("is_strong_wake", False)

        # [State Machine]: 状态机决策
        should_forward = False
        
        try:
            if is_strong_wake:
                 # 强唤醒 (关键词/@Bot) -> 激活并放行
                 attn_context.focus(item_id, duration=branch_ttl)
                 should_forward = True
                 logger.info(f"[Reflex] ⚡ 强唤醒激活: {full_context_path}")
                 
            elif not self.strict_wake and attn_context.is_active(item_id):
                 # 弱输入 (连续对话中) -> 续期并放行
                 attn_context.focus(item_id, duration=branch_ttl)
                 should_forward = True
                 logger.debug(f"[Reflex] 🔗 连续对话续期: {full_context_path}")
            
            else:
                 # 既没唤醒，也不在活跃期 -> 拦截为背景噪音
                 pass
                 
        except Exception as e:
            logger.error(f"[Reflex] 状态机异常: {e}")
            return

        if not should_forward:
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
