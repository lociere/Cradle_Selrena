"""月见用的高级 Napcat 客户端（负责 QQ 消息处理）。

本模块从总线消费原始 OneBot 事件（无论是通过适配器还是
服务器组件传入），并将消息推送转换成框架内部信号。为了
保持与音频输入相同的处理路径，我们将提取到的文本作为
``perception.audio.transcription`` 发送，而不是直接进入
意识层。

目前仅处理文本消息；其它 OneBot 事件类型以后可以扩展。

主要发布 ``perception.audio.transcription`` 事件，载荷结构：

```python
{
    "text": "...",
    "source": "qq",          # 固定值，用于标记 QQ 来源
    "raw": <original payload>,# 保留原始负载，便于调试/扩展
    "user_id": 12345,         # 提取到的发送者（如果有）
    "group_id": 67890,        # 若消息来自群聊则包含该字段
}
```

该组件通常在系统启动时初始化并注册。
"""

from typing import Any

from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.core.config_manager import global_config
from cradle.schemas.protocol.events import BaseEvent
from cradle.utils.logger import logger


class NapcatClient:
    """处理 Napcat 上报的 OneBot 事件并转发消息。

    由于测试和自动装载流程可能会创建多个实例，为避免重复消费
    同一事件，类级别维护一个订阅标记，只有首个实例会注册监听。
    """

    # 类级别标记：是否已有某个实例完成订阅
    _subscribed: bool = False

    def __init__(self):
        self.bus = global_event_bus
        self._did_subscribe = False

    async def initialize(self):
        """订阅 Napcat 事件。

        高级客户端在事件总线收到 OneBot 事件时才有用，当前
        只有服务器模式才会产生此类事件。如果 napcat 被禁用或
        非服务器模式，则跳过订阅以避免冗余。

        以前我们直接把文本发布为 ``input.user_message``，绕过了
        Layer2/Reflex 两层。现在会先发 ``perception.audio.transcription``
        以遵循架构，让脊髓反射与注意力机制起作用。
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
            from cradle.selrena.synapse.napcat_responder import NapcatResponder
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
        data = event.payload

        # 辅助函数：递归提取可处理的文本片段。
        # Napcat 的负载形态并不稳定，常见情况包括“列表嵌列表”、
        # “对象混入数组”等，因此这里采用递归遍历而非固定模板匹配。
        # 返回值统一为扁平字符串列表。
        def _extract_texts(node: Any) -> list[str]:
            texts: list[str] = []
            if isinstance(node, list):
                for element in node:
                    texts.extend(_extract_texts(element))
            elif isinstance(node, dict):
                # 直连消息场景：仅当字段本身是字符串时才直接收集。
                # Napcat 经常把 ``message`` 提供为分段列表，此时应递归
                # 处理其内容，避免把原始列表直接拼进文本。
                if node.get("post_type") == "message":
                    msg = node.get("message") or node.get("raw_message")
                    if isinstance(msg, str):
                        texts.append(msg)
                    elif isinstance(msg, list):
                        texts.extend(_extract_texts(msg))
                # 判断如果是 OneBot 标准的消息段类型：
                msg_type = node.get("type")
                if msg_type == "text":
                    txt = node.get("data", {}).get("text")
                    if isinstance(txt, str):
                        texts.append(txt)
                elif msg_type == "image":
                    # 可以提取 URL 但一般模型只接受文本描述，所以预留占位符
                    texts.append("[图片]")
                elif msg_type == "record":
                    texts.append("[语音]")
                elif msg_type == "video":
                    texts.append("[视频]")
                elif msg_type == "face":
                    texts.append("[表情]")
                elif msg_type == "file":
                    texts.append("[文件]")
                elif msg_type == "json":
                    texts.append("[应用卡片]")
                elif msg_type == "forward":
                    texts.append("[合并转发]")
                elif msg_type == "reply":
                    # 返回的是回复引用的段落，一般会跟在原消息前面或包含在上下文中
                    texts.append("[回复]")

                # 同时向下遍历所有值，兼容额外包裹层（例如某些版本会把
                # 真实对象塞到额外键中）。但 ``message``/``raw_message``
                # 已在上面做过特殊处理，若其为列表再递归会造成重复，因此
                # 在统一遍历时跳过这两个键。
                for k, v in node.items():
                    if k in ("message", "raw_message") and isinstance(v, list):
                        continue
                    if isinstance(v, (list, dict)):
                        texts.extend(_extract_texts(v))
            return texts

        def _extract_non_text_inputs(node: Any) -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            if isinstance(node, list):
                for element in node:
                    items.extend(_extract_non_text_inputs(element))
                return items

            if not isinstance(node, dict):
                return items

            msg_type = node.get("type")
            data_obj = node.get("data") if isinstance(node.get("data"), dict) else {}
            if msg_type in {"image", "video", "record", "file", "json", "forward", "face", "reply"}:
                file_ref = (
                    data_obj.get("url")
                    or data_obj.get("file")
                    or data_obj.get("path")
                    or data_obj.get("name")
                    or data_obj.get("id")
                )
                summary = {
                    "image": "[图片]",
                    "video": "[视频]",
                    "record": "[语音]",
                    "file": "[文件]",
                    "json": "[应用卡片]",
                    "forward": "[合并转发]",
                    "face": "[表情]",
                    "reply": "[回复]",
                }.get(msg_type, "[非文本]")
                if isinstance(file_ref, str) and file_ref.strip():
                    summary = f"{summary} {file_ref.strip()}"
                items.append({
                    "kind": msg_type,
                    "summary": summary,
                    "file": file_ref if isinstance(file_ref, str) else "",
                    "raw": node,
                })

            for v in node.values():
                if isinstance(v, (list, dict)):
                    items.extend(_extract_non_text_inputs(v))
            return items

        # 收集我们能找到的所有文本片段，并尝试提取发送者 ID 和群组 ID
        user_id = None
        group_id = None
        def _extract_user_id(node: Any) -> int | None:
            if isinstance(node, dict):
                if isinstance(node.get("user_id"), int):
                    return node.get("user_id")
                # some payloads nest sender info
                if isinstance(node.get("sender"), dict):
                    return _extract_user_id(node.get("sender"))
                for v in node.values():
                    if isinstance(v, (list, dict)):
                        uid = _extract_user_id(v)
                        if uid is not None:
                            return uid
            elif isinstance(node, list):
                for element in node:
                    uid = _extract_user_id(element)
                    if uid is not None:
                        return uid
            return None

        def _extract_group_id(node: Any) -> int | None:
            if isinstance(node, dict):
                if isinstance(node.get("group_id"), int) and node.get("group_id") != 0:
                    return node.get("group_id")
                for v in node.values():
                    if isinstance(v, (list, dict)):
                        gid = _extract_group_id(v)
                        if gid is not None:
                            return gid
            elif isinstance(node, list):
                for element in node:
                    gid = _extract_group_id(element)
                    if gid is not None:
                        return gid
            return None

        if isinstance(data, (list, dict)):
            texts = _extract_texts(data)
            media_inputs = _extract_non_text_inputs(data)
            if texts:
                # 在原始结构中提取可能存在的用户/群 ID。
                user_id = _extract_user_id(data)
                group_id = _extract_group_id(data)
                if user_id is not None:
                    logger.debug(f"[NapcatClient] 从原始数据提取到 user_id={user_id}")
                if group_id is not None:
                    logger.debug(f"[NapcatClient] 从原始数据提取到 group_id={group_id}")
                await self._publish_text("".join(texts), raw=data, user_id=user_id, group_id=group_id)
                for media in media_inputs:
                    await self._publish_non_text(
                        kind=str(media.get("kind", "non_text")),
                        summary=str(media.get("summary", "[非文本]")),
                        file_ref=str(media.get("file", "")),
                        raw=media.get("raw", data),
                        user_id=user_id,
                        group_id=group_id,
                    )
                # 到这里已完成消息提取和转发，后续兜底分支无需再执行，
                # 否则可能导致重复转发或错误处理。
                return
            if media_inputs:
                user_id = _extract_user_id(data)
                group_id = _extract_group_id(data)
                for media in media_inputs:
                    await self._publish_non_text(
                        kind=str(media.get("kind", "non_text")),
                        summary=str(media.get("summary", "[非文本]")),
                        file_ref=str(media.get("file", "")),
                        raw=media.get("raw", data),
                        user_id=user_id,
                        group_id=group_id,
                    )
                return
        # 其余类型暂不处理；无法保证可安全转换为文本消息。

        # 规范化任何上游组件可能产生的数组格式
        if isinstance(data, dict) and "_array" in data:
            arr = data.get("_array", [])
            if arr and arr[0] == "message":
                # 常见数组格式：["message", {...meta...}, "text", ...]
                text = self._extract_text_from_array(arr)
                await self._publish_text(text, raw=data)
            return

        # 处理对象风格事件
        if isinstance(data, dict) and data.get("post_type") == "message":
            text = data.get("message") or data.get("raw_message") or ""
            await self._publish_text(text, raw=data)

    def _extract_text_from_array(self, arr: list) -> str:
        # 从头部与元信息之后，提取首个字符串作为文本。
        for item in arr[1:]:
            if isinstance(item, str):
                return item
        return ""

    async def _publish_text(self, text: str, raw: Any, user_id: int | None = None, group_id: int | None = None):
        # 避免将非字符串直接交给上层；历史上 SoulIntellect 对列表
        # 执行正则会触发异常，这里统一兜底为字符串。
        if not text:
            return
        if not isinstance(text, str):
            text = str(text)
        logger.debug(f"[NapcatClient] 收到消息: {text}")
        payload: dict = {"text": text, "source": "qq", "raw": raw}
        if isinstance(user_id, int):
            payload["user_id"] = user_id
        if isinstance(group_id, int):
            payload["group_id"] = group_id
        # 提取完文本与用户/群 ID 后，统一送入常规感知管线，
        # 不再直接跳到 ``input.user_message``。
        # 后续由 Layer2(Edge) 做外围规整，
        # 再由 Reflex 完成门控与意识流编排。
        # 再按架构发布到意识层。
        await self.bus.publish(BaseEvent(
            name="perception.audio.transcription",
            payload=payload,
            source="NapcatClient"
        ))

    async def _publish_non_text(
        self,
        kind: str,
        summary: str,
        file_ref: str,
        raw: Any,
        user_id: int | None = None,
        group_id: int | None = None,
    ):
        payload: dict[str, Any] = {
            "caption": summary,
            "source": "qq",
            "raw": raw,
            "kind": kind,
        }
        if file_ref:
            payload["file"] = file_ref
            payload["url"] = file_ref
        if isinstance(user_id, int):
            payload["user_id"] = user_id
        if isinstance(group_id, int):
            payload["group_id"] = group_id

        await self.bus.publish(BaseEvent(
            name="perception.visual.snapshot",
            payload=payload,
            source="NapcatClient"
        ))
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

    async def reply(self, user_id: int, text: str):
        """简单私聊回复的快捷包装。"""
        logger.debug(f"[NapcatClient] reply to {user_id} with text={text!r}")
        await self.send_api(
            "send_private_msg", {"user_id": user_id, "message": text}
        )

    async def reply_group(self, group_id: int, text: str):
        """在群聊中发送回复。"""
        logger.debug(f"[NapcatClient] reply_group to {group_id} with text={text!r}")
        await self.send_api(
            "send_group_msg", {"group_id": group_id, "message": text}
        )
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
                payload={"text": f"Napcat API error: {data.get('message')}", "raw": data},
                source="NapcatClient"
            ))
