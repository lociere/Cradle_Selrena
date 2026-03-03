"""
Napcat 客户端 (OneBot 协议适配器)。

本模块负责接入基于 OneBot v11 协议的消息源（如 QQ），将其转换为系统内部标准事件。
它充当了外部即时通讯软件与 SELRENA 核心系统之间的桥梁。

主要职责：
1. 监听 OneBot 事件（消息、通知等）。
2. 将非结构化的 OneBot 数据清洗为标准的 `MultiModalPayload`。
3. 发布感知层事件 (`perception.*`) 供上游模块消费。

注意：
文本消息目前统一发布为 `perception.audio.transcription` 事件，
以便复用音频转录后的处理链路（即视为"来自外部的语言输入"）。
"""

import asyncio
from typing import Any

from cradle.core.config_manager import global_config
from cradle.schemas.domain.multimodal import (AudioContent, ContentBlock,
                                              ImageContent, TextContent,
                                              VideoContent)
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.schemas.protocol.events.perception import (Modality,
                                                       MultiModalPayload,
                                                       PerceptionEvent)
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.event_payload import extract_fields
from cradle.utils.logger import logger


NAPCAT_SOURCE_ID_KEYS: dict[str, tuple[str, ...]] = {
    "user_id": ("user_id", "qq"),
    "group_id": ("group_id",),
}


class NapcatClient:
    """
    Napcat 客户端核心类。

    维护与 OneBot 兼容客户端的通信状态，并负责事件分发。
    实现了单例订阅模式，避免多实例同时监听同一总线事件导致的消息重复。
    """

    # 类级别标记：是否已有某个实例完成订阅
    _subscribed: bool = False

    def __init__(self):
        self.bus = global_event_bus
        self._did_subscribe = False

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
        
        Args:
            event (BaseEvent): 总线传递的原始事件对象。
        
        Logic:
            1. 递归解析事件载荷 (payload)，兼容 OneBot 各种嵌套格式。
            2. 提取文本内容 -> 发布 `perception.audio.transcription` (模拟语音转录输入)。
            3. 提取多模态内容 (图片/语音等) -> 发布 `perception.visual.snapshot` (模拟视觉输入)。
        """
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
            data_obj = node.get("data") if isinstance(
                node.get("data"), dict) else {}
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

        if isinstance(data, (list, dict)):
            texts = _extract_texts(data)
            media_inputs = _extract_non_text_inputs(data)
            if texts:
                # 在原始结构中提取可能存在的用户/群 ID。
                ids = extract_fields(
                    data,
                    field_keys=NAPCAT_SOURCE_ID_KEYS,
                    value_type=int,
                    allow_zero=False,
                )
                user_id = ids.get("user_id")
                group_id = ids.get("group_id")
                if user_id is not None:
                    logger.debug(f"[NapcatClient] 从原始数据提取到 user_id={user_id}")
                if group_id is not None:
                    logger.debug(
                        f"[NapcatClient] 从原始数据提取到 group_id={group_id}")
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
                ids = extract_fields(
                    data,
                    field_keys=NAPCAT_SOURCE_ID_KEYS,
                    value_type=int,
                    allow_zero=False,
                )
                user_id = ids.get("user_id")
                group_id = ids.get("group_id")
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
        """
        发布纯文本消息到感知层 (模拟为语音转录)。
        
        Args:
            text (str): 提取出的文本内容。
            raw (Any): 原始 OneBot 负载（仅做调试保留）。
            user_id (int | None): 发送者 QQ 号。
            group_id (int | None): QQ 群号。
        """
        if not text:
            return
        if not isinstance(text, str):
            text = str(text)

        # [Standardization] 仅用于日志，payload 中不保留冗余字段
        logger.debug(f"[NapcatClient] 收到消息: {text[:50]}...")
        
        # [Strict Mode] 严格使用 Pydantic Model 构建载荷
        payload_obj = MultiModalPayload(
            content=[TextContent(text=text)],
            raw=raw,
            user_id=user_id,
            group_id=group_id
        )

        await self.bus.publish(PerceptionEvent(
            name="perception.audio.transcription", # Generic text/audio input
            modality=Modality.TEXT,
            payload=payload_obj, # 自动 validate
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
        """
        发布多模态消息 (图片/语音/视频/未知) 到感知层。
        
        Args:
            kind (str): 原始消息类型 (如 "image", "record", "video")。
            summary (str): 文本摘要或简述 (例如 "[图片]" 或 OCR 结果)。
            file_ref (str): 资源地址 (URL 或文件路径)。
            raw (Any): 原始 OneBot 消息负载。
            user_id (int | None): 发送者 QQ 号。
            group_id (int | None): QQ 群号。
        """
        # [Strict Structure] 重新组织 payload，移除所有非标字段
        content_blocks: list[ContentBlock] = []
        try:
            if file_ref:
                if kind == "image":
                    content_blocks.append(
                        ImageContent(image_url={"url": file_ref}))
                elif kind == "record":
                    content_blocks.append(
                        AudioContent(audio_url={"url": file_ref}))
                elif kind == "video":
                    content_blocks.append(
                        VideoContent(video_url={"url": file_ref}))
            
            # 如果还有附带文本（如summary或caption），也作为 TextContent 加入
            if summary:
                 content_blocks.append(TextContent(text=summary))

        except Exception as e:
            logger.error(f"[NapcatClient] 构建多模态 content 失败: {e}")
            # 出错时构建一个纯文本错误提示，确保数据链不断
            content_blocks.append(TextContent(text=f"[System Error: {kind} content build failed]"))

        payload_obj = MultiModalPayload(
            content=content_blocks,
            user_id=user_id,
            group_id=group_id,
            raw=raw
        )

        file_size = None
        if isinstance(raw, dict):
            data_obj = raw.get("data")
            if isinstance(data_obj, dict):
                file_size = data_obj.get("file_size")
        
        logger.debug(
            f"[NapcatClient] 非文本上行: kind={kind}, file_size={file_size}, content_len={len(content_blocks)}"
        )

        await self.bus.publish(PerceptionEvent(
            name="perception.visual.snapshot", # Or generic multimodal event
            modality=Modality.MULTIMODAL,
            payload=payload_obj,
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
