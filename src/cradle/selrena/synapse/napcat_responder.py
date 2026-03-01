from typing import Optional, Any

from cradle.schemas.protocol.events import BaseEvent
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.selrena.vessel.napcat.napcat_client import NapcatClient
from cradle.utils.logger import logger


class NapcatResponder:
    """桥接模块：让 Soul 生成的讲话通过 napcat 发回 QQ。

    该类使用单例标记，重复初始化时会自动忽略，以便我们可以
    不必在配置中显式列出组件，只要有 NapcatClient 存在就会
    自动装载。

    它监听两类信号：
    1. ``input.user_message``：保存最新的发信人 ID（如果存在于负载）。
    2. ``action.presentation.speak``：当灵魂发出说话动作时，将该文本
       封装成 napcat.send 事件并发布出去。

    之所以单独成模块，是为了让 SoulIntellect 保持纯粹，只负责思考。
    """
    _installed = False

    def __init__(self):
        # 保存最近一次接收到的用户／群组信息，用于后续回应。
        self._last_user: Optional[int] = None
        self._last_group: Optional[int] = None
        self._client = NapcatClient()

    async def initialize(self):
        # 防止重复初始化。
        if NapcatResponder._installed:
            return
        NapcatResponder._installed = True

        # NapcatClient 会在必要时自行订阅，这里仅保证其已就绪。
        await self._client.initialize()
        global_event_bus.subscribe("input.user_message", self._on_user_message)
        global_event_bus.subscribe("action.presentation.speak", self._on_speak)
        logger.debug("[NapcatResponder] 已初始化")

    async def cleanup(self):
        global_event_bus.unsubscribe_receiver(self)
        await self._client.cleanup()
        logger.debug("[NapcatResponder] 已完成清理")

    async def _on_user_message(self, event: BaseEvent):
        payload = event.payload or {}
        # 优先从当前 payload 直接提取用户 ID。
        uid = payload.get("user_id") or payload.get("qq")
        # 若未命中，再从 raw 原始负载中递归查找。
        if uid is None:
            raw = payload.get("raw")
            def _find_uid(node: Any) -> int | None:
                if isinstance(node, dict):
                    if isinstance(node.get("user_id"), int):
                        return node.get("user_id")
                    if isinstance(node.get("sender"), dict):
                        return _find_uid(node.get("sender"))
                    for v in node.values():
                        uid2 = _find_uid(v)
                        if uid2 is not None:
                            return uid2
                elif isinstance(node, list):
                    for el in node:
                        uid2 = _find_uid(el)
                        if uid2 is not None:
                            return uid2
                return None
            uid = _find_uid(raw)
        if isinstance(uid, int):
            self._last_user = uid
        # 同步记录群 ID（如存在）。
        gid = payload.get("group_id")
        if not isinstance(gid, int):
            # 兜底：从 raw 原始负载继续查找。
            raw = payload.get("raw")
            if isinstance(raw, dict):
                gid = raw.get("group_id")
        if isinstance(gid, int) and gid != 0:
            self._last_group = gid

    async def _on_speak(self, event: BaseEvent):
        if self._last_user is None:
            return
        # ``event.payload`` 可能有多种形态：
        #
        # 1) 普通 dict，包含 ``text`` 字段（测试中常见）
        # 2) ``SpeakAction`` 直接作为事件对象，此时 ``payload`` 可能为 ``None``
        # 3) ``BaseEvent`` 的 ``payload`` 中再包一层 ``SpeakAction``
        # 4) 少数情况下 ``payload`` 就是 ``None``，通常表示空确认信号，不应转发
        #
        # 按“最明确 → 最兜底”的顺序提取文本，避免把 ``None`` 转成字面量
        # "None" 后误发到 QQ。
        text: str | None = None
        payload = event.payload

        if isinstance(payload, dict):
            text = payload.get("text")

        # 情况 2：SpeakAction 直接挂在事件对象上。
        if text is None:
            text = getattr(event, "text", None)

        # 情况 3：SpeakAction 被包在 BaseEvent.payload 中。
        if text is None and hasattr(payload, "text"):
            text = getattr(payload, "text")

        # 最后兜底：仅在 payload 非 None 时转字符串，
        # 避免生成不期望的字面量 "None"。
        if text is None and payload is not None:
            text = str(payload)

        logger.debug(
            f"[NapcatResponder] _on_speak 收到 event={event!r} text={text!r} "
            f"last_user={self._last_user} last_group={self._last_group}"
        )

        # 仍可能是 None 或空串，这两种情况都无需回发。
        if not text:
            return

        # 优先按群聊上下文回复，否则回私聊。
        if self._last_group is not None:
            await self._client.reply_group(self._last_group, text)
        elif self._last_user is not None:
            await self._client.reply(self._last_user, text)
