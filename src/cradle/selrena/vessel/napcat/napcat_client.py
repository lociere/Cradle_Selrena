"""
Napcat 客户端 (OneBot 协议适配器)。

本模块负责接入基于 OneBot v11 协议的消息源（如 QQ），将其转换为系统内部标准事件。
它充当了外部即时通讯软件与 SELRENA 核心系统之间的桥梁。

主要职责：
1. 监听 OneBot 事件（消息、通知等）。
2. 将非结构化的 OneBot 数据清洗为标准的 `ExternalMultiModalPayload`。
3. 发布感知层事件 (`perception.*`) 供上游模块消费。

注意：
文本消息统一发布为 `perception.message` 事件，
通过 Edge 路由进入标准处理链路。
"""

import asyncio
from typing import Any

from cradle.core.config_manager import global_config
from cradle.schemas.domain.multimodal import TextContent
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.schemas.protocol.events.perception import (Modality,
                                                       ExternalMultiModalPayload,
                                                       PerceptionEvent)
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger
from .cortex import NapcatCortex


class NapcatClient:
    """
    Napcat 客户端核心类。

    维护与 OneBot 兼容客户端的通信状态，并负责事件分发。
    实现了单例订阅模式，避免多实例同时监听同一总线事件导致的消息重复。
    """

    # 类级别标记：是否已有某个实例完成订阅
    _subscribed: bool = False

    def __init__(self, brain=None):
        self.bus = global_event_bus
        self._did_subscribe = False
        # 将大脑实例注入给 Napcat 皮层，使其具备本地多模态感知能力
        self.cortex = NapcatCortex(brain_factory=brain)

    async def initialize(self):
        """
        初始化客户端并注册事件监听。
        
        流程说明：
        1. 检查配置是否启用 napcat。
        2. 若未订阅过，则向全局总线注册 `napcat.event` 和 `napcat.response` 监听器。
        3. 注册到全局生命周期管理器 (`global_lifecycle`)。
        4. 尝试启动 `NapcatResponder` 以支持反向通信。
        """
        cfg = global_config.get_system().napcat
        if not cfg.enable:
            logger.info("[NapcatClient] 未激活（napcat 已禁用）")
            return

        # 若已有实例完成订阅，本实例仅作为辅助对象使用，不再重复注册。
        if not NapcatClient._subscribed:
            self.bus.subscribe("napcat.event", self.on_napcat_event)
            self.bus.subscribe("napcat.response", self.on_napcat_response)
            self._did_subscribe = True
            NapcatClient._subscribed = True
            logger.info("[NapcatClient] 已初始化并开始监听事件")
        else:
            logger.debug("[NapcatClient] 额外实例创建，不重复订阅事件")

        # 注册到生命周期，便于统一 cleanup。
        try:
            from cradle.core.lifecycle import global_lifecycle
            global_lifecycle.register(self)
        except ImportError:
            pass

        # 自动安装 NapcatResponder（主要用于服务器模式回包）。
        try:
            from cradle.selrena.vessel.napcat.napcat_responder import \
                NapcatResponder
            await NapcatResponder().initialize()
        except Exception:
            # 模块不可用或已初始化时忽略，不影响主流程。
            pass

    async def cleanup(self):
        # 只有真正完成订阅的实例才需要注销；其他实例调用本方法
        # 不应影响事件总线状态。
        if self._did_subscribe:
            self.bus.unsubscribe_receiver(self)
            # 标记未订阅，方便后续实例继续注册
            NapcatClient._subscribed = False
        logger.info("[NapcatClient] 已清理")

    async def on_napcat_event(self, event: BaseEvent):
        """
        处理 Napcat (OneBot) 原始事件。
        
        [Processing Delegation] 逻辑委托:
        由 NapcatCortex 负责所有复杂的解析、感知和记忆更新逻辑。
        Client 仅作为协议网关，负责将 Cortex 生成的标准感知载荷发布到系统总线。
        """
        # [Cortex Processing] 调用皮层处理管线
        processed = await self.cortex.proccess_ingress(event.payload)
        
        if processed is None:
            return

        # [Event Construction] 构建标准感知事件
        # 提取 content 字段并根据类型统一处理
        # (Content blocks are passed through directly if they are already Pydantic-ready dicts or objects)
        content_data = processed.pop("content", [])
        content_blocks = []
        
        if isinstance(content_data, list):
             # 假设 Cortex 返回的是 List[dict] (ContentBlock like)，需确保 Schema 兼容
             content_blocks = content_data
        elif isinstance(content_data, str):
             content_blocks = [TextContent(text=content_data)]
        
        # 实例化 Pydantic 模型
        # ExternalMultiModalPayload 会自动递归验证 content_blocks 中的字典
        payload_obj = ExternalMultiModalPayload(
            content=content_blocks,
            **processed
        )

        # [Event Publishing] 发布标准感知事件
        event_out = PerceptionEvent(
            name="perception.message", 
            modality=Modality.TEXT, # 即使含图片，主交互模态仍视为文本对话
            payload=payload_obj,
            source="NapcatClient"
        )
        await self.bus.publish(event_out)


    # ------------------------------------------------------------------
    # 对外发送辅助方法
    # ------------------------------------------------------------------

    async def send_api(self, api: str, params: dict):
        """辅助方法：发出一个 *napcat.send* 事件，连接的客户端
        会帮忙转发。

        载荷需遵循 Napcat 期待的 OneBot API 形状；目前已知
        实际客户端解析字段名为 ``action`` 而非 ``api``，因此
        两者都会同时提供以保持兼容。

            await client.send_api("send_private_msg", {
                "user_id": 12345, "message": "hello"})
        """
        payload = {"action": api, "params": params, "api": api}
        await self.bus.publish(BaseEvent(
            name="napcat.send",
            payload=payload,
            source="NapcatClient",
        ))

    def _split_message(self, text: str, max_len: int = 1500) -> list[str]:
        """按最大长度及标点符号智能分段消息"""
        if len(text) <= max_len:
            return [text]

        chunks = []
        current_chunk = ""

        # 优先按换行符分割
        lines = text.split('\n')
        for line in lines:
            if len(current_chunk) + len(line) + 1 <= max_len:
                current_chunk += (line + '\n')
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'

        if current_chunk:
            chunks.append(current_chunk.strip())

        # 如果还有单段超长的（比如无换行符长文本），硬切分
        final_chunks = []
        for chunk in chunks:
            while len(chunk) > max_len:
                final_chunks.append(chunk[:max_len])
                chunk = chunk[max_len:]
            if chunk:
                final_chunks.append(chunk)

        return final_chunks

    async def reply(self, user_id: int, text: str):
        """简单私聊回复的快捷包装。"""
        logger.debug(
            f"[NapcatClient] reply to {user_id} with text={text[:50]}...")
        for chunk in self._split_message(text):
            if chunk.strip():
                await self.send_api(
                    "send_private_msg", {"user_id": user_id, "message": chunk}
                )
                # 稍微延时避免刷屏风控
                await asyncio.sleep(0.5)

    async def reply_group(self, group_id: int, text: str):
        """在群聊中发送回复。"""
        logger.debug(
            f"[NapcatClient] reply_group to {group_id} with text={text[:50]}...")
        for chunk in self._split_message(text):
            if chunk.strip():
                await self.send_api(
                    "send_group_msg", {"group_id": group_id, "message": chunk}
                )
                await asyncio.sleep(0.8)

    async def on_napcat_response(self, event: BaseEvent):
        data = event.payload or {}
        status = data.get("status")
        if status != "ok":
            # retcode 1404 通常表示“不支持的 API”，可忽略。
            ret = data.get("retcode")
            if ret == 1404:
                logger.debug(f"[NapcatClient] 忽略不支持的 API 错误: {data}")
            else:
                logger.warning(f"[NapcatClient] API 响应错误: {data}")
            # 发布错误事件，便于其他模块按需处理。
            await self.bus.publish(BaseEvent(
                name="napcat.error",
                payload=data,
                source="NapcatClient"
            ))
            # 同时作为系统消息反馈给上层。
            await self.bus.publish(BaseEvent(
                name="input.system_message",
                payload={
                    "text": f"Napcat API error: {data.get('message')}", "raw": data},
                source="NapcatClient"
            ))
