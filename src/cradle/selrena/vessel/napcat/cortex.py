from typing import Any, Dict, List, Optional
import asyncio

from cradle.core.config_manager import global_config
from cradle.schemas.domain.chat import Message
from cradle.schemas.domain.multimodal import ImageContent, TextContent
from cradle.utils.logger import logger

from .memory.short_term import napcat_memory
from .tools.parser import NapcatMessageCleaner, NapcatMessageParser
from .schemas.napcat import NapcatArtifact

class NapcatCortex:
    """
    Napcat 神经皮层 (Processing Center)
    
    Acts as the 'Frontal Lobe' for the Napcat Vessel.
    Responsible for:
    1. Ingress Processing: Cleaning raw data, parsing complex message types.
    2. Perception: Calling Vision/Audio experts *before* Soul sees it.
    3. Memory Management: Storing session-specific context.
    4. Prompt Assembly: Preparing the final context for the Soul.
    5. Egress Formatting: Converting Soul's response back to Napcat format.
    """

    def __init__(self, brain_factory=None):
        """
        :param brain_factory: 大脑接口工厂引用，用于调用视觉模型等能力。
                              为避免循环引用，通常应通过服务定位器获取或延迟注入。
        """
        self.brain_factory = brain_factory 
        # 注意: 依赖于调用者 (通常是 Vessel) 注入 brain_factory

    async def proccess_ingress(self, raw_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        主处理管线: 将原始 Napcat 事件 转换为 适用于 Soul 的标准感知事件
        
        流程:
        1. 解析基础信息 (用户/群组 ID, 发送者身份)
        2. 高级消息解析 (CQ码, 图片提取, At解析)
        3. 上下文与记忆更新 (回复引用解析, 短时记忆存储)
        4. 唤醒与注意力判定 (是否触发强唤醒)
        5. 专家模型处理 (视觉理解, 仅在强唤醒时触发)
        6. 组装最终提示词 (Prompt Engineering)
        7. 构建标准载荷 (Payload Construction)
        """
        if raw_event.get("post_type") != "message":
            return None # 仅处理消息类型事件，忽略通知等

        # --- 1. Basic Info Parsing (基础信息解析) ---
        user_id = raw_event.get("user_id")
        group_id = raw_event.get("group_id")
        raw_msg = raw_event.get("raw_message", "")
        msg_chain = raw_event.get("message", []) # 数组格式的消息链
        
        # [Identity] Parse Sender Info (发送者身份解析)
        sender = raw_event.get("sender", {})
        # 优先使用群名片 (card)，其次是昵称 (nickname)，最后兜底ID
        user_name = sender.get("card") or sender.get("nickname") or f"User{user_id}"

        # --- 2. Advanced Message Parsing (高级消息解析) ---
        if isinstance(msg_chain, list):
            parsed = NapcatMessageParser.normalize_message_chain(msg_chain)
        else:
            # 兼容纯字符串格式 (虽然 Napcat 通常返回数组)
            parsed = NapcatMessageParser.parse_cq_codes(raw_msg)
        
        # [Clean Text] Resolve At placeholders (文本清洗与 At 解析)
        raw_clean_text = parsed["text"]
        # 将内部占位符 [HQ:at] 替换为标准 @ID 格式
        import re
        clean_text = re.sub(r' \[HQ:at,qq=(\d+)\] ', r'[@\1]', raw_clean_text)

        images = parsed["images"]
        reply_id = parsed["reply_to"]
        
        # --- 3. Memory & Context Updates (记忆与上下文更新) ---
        # 存储用户发送的原始内容 (包含图片URL)，用于后续上下文回溯
        msg_id = raw_event.get("message_id")

        
        # [Reply Context Resolution] (回复上下文解析)
        # 尝试查找被引用的消息，以便为 AI 提供对话上下文
        prefix = f"[{user_name}]"
        
        if reply_id:
            history = await napcat_memory.get_artifacts_async(group_id, user_id)
            reply_target_name = "某人"
            reply_summary = ""

            # 在短时记忆中倒序查找被引用的消息
            for msg in reversed(history):
                if msg.get("msg_id") == reply_id:  # 命中!
                    reply_target_name = msg.get("sender_name", "User")
                    # 提取简短摘要
                    reply_text = msg.get("text") or msg.get("display_text") or ""
                    if isinstance(reply_text, str):
                        reply_summary = reply_text[:10] + "..."
                    break

            prefix = f"{prefix} (回复 @{reply_target_name} \"{reply_summary}\")"

        # [Display Text Formatting] (展示文本格式化)
        display_text = f"{prefix}: {clean_text}" if clean_text else f"{prefix}: (Imageless)"
        if not clean_text and images:
             display_text = f"{prefix}: "

        msg_content = display_text
        if images:
             msg_content = []
             if display_text.strip():
                  msg_content.append({"type": "text", "text": display_text})
             for img in images:
                  msg_content.append({"type": "image_url", "image_url": {"url": img}})

        # --- 4. Configuration Load (配置加载) ---
        # 提前加载配置，供注意力门控使用
        should_record = True
        if group_id:
             should_record = global_config.get("napcat.enable_silent_record", True)
        
        strategy_cfg = global_config.get_soul().strategy
        routing_mode = strategy_cfg.routing_mode

        # --- 5. Wake Word & Attention Logic (唤醒与注意力逻辑) ---
        # 私聊默认始终活跃，群聊需要 @Bot 或 关键词
        is_strong_wake = False
        if group_id:
             self_id = raw_event.get("self_id")
             is_at_me = False
             
             # 检查 @Bot
             if self_id and str(self_id) in str(parsed.get("at_users", [])):
                  is_at_me = True
             
             # 检查唤醒词
             WAKE_WORDS = global_config.get("napcat.wake_words", ["月见"])
             is_wake_word = any(clean_text.lstrip().startswith(w) for w in WAKE_WORDS)
             
             if is_at_me or is_wake_word:
                  is_strong_wake = True
        else:
             is_strong_wake = True

        # --- 5.5 Active-session Check (活跃会话检测) ---
        from cradle.selrena.synapse.attention import global_attention, AttentionTarget
        target = AttentionTarget(
            vessel_id="napcat",
            context_type="group" if group_id else "private",
            subject_id=str(group_id) if group_id else str(user_id),
        )
        is_active_session = global_attention.is_active(target)

        # --- 6. Attention Gate (注意力门控) ---
        # 非唤醒且非活跃会话时，只静默记录
        if not is_strong_wake and not is_active_session:
            # 静默模式：只记录最基础的占位文本，不调用任何专家模型
            if images:
                silent_text = f"[{user_name}]发送了一张图片" if group_id else "用户发送了一张图片"
            elif clean_text:
                silent_text = f"[{user_name}]: {clean_text}" if group_id else clean_text
            else:
                silent_text = "(无内容)"
            
            logger.debug(f"[NapcatCortex] 非唤醒+非活跃 会话，静默记录：{silent_text}")
            
            # 构建最小化返回内容
            silent_content = [{"type": "text", "text": silent_text}]
            
            # 静默记录到记忆
            if should_record:
                await napcat_memory.append_async(group_id, user_id, {
                    "role": "user",
                    "content": silent_content,
                })
                await napcat_memory.append_artifact_async(group_id, user_id, {
                    "role": "user",
                    "msg_id": msg_id,
                    "reply_to": reply_id,
                    "sender_name": user_name,
                    "text": clean_text,
                    "display_text": display_text,
                    "images": images,
                    "routing_mode": routing_mode,
                    "is_silent_record": True,
                })
            
            # 返回 payload（Reflex 会接收并根据 attention 决定是否上行）
            return {
                "content": silent_content,
                "vessel_id": "napcat",
                "source_type": "group" if group_id else "private",
                "source_id": str(group_id) if group_id else str(user_id),
                "is_strong_wake": False,
                "is_external_source": True,
                "name": user_name,
                "preprocessed": True,
                "metadata": {
                    "user_id": user_id,
                    "group_id": group_id,
                    "is_silent_record": True,
                },
                "external_history": None
            }

        # --- 7. Content Assembly (内容组装与多模态分发) ---
        # 唤醒状态下，进入完整处理流程
        if clean_text:
            base_text = clean_text
            if group_id:
                base_text = f"[{user_name}]: {base_text}"
        elif images:
            base_text = f"[{user_name}]发送了一张图片" if group_id else "用户发送了一张图片"
        else:
            base_text = "(无文本)"
            if group_id:
                base_text = f"[{user_name}]: {base_text}"

        # 注意：strategy_cfg 和 routing_mode 已在第 4 步加载

        final_content_blocks = []
        if routing_mode == "split_tasks":
            # 专家分工：先在 Napcat 层做视觉转述，确保主记忆记录语义文本
            final_content_blocks = await self._process_expert_mode(
                base_text=base_text, 
                images=images, 
                is_wake=is_strong_wake
            )
        else:
            # 全能单体：保留原始多模态块，交给核心模型直接处理
            final_content_blocks = self._process_monolithic_mode(
                base_text=base_text, 
                images=images
            )
            
        # --- 7. Validation (校验) ---
        if not final_content_blocks:
            logger.debug("[NapcatCortex] 清洗后无有效内容，忽略。")
            return None

        # [Silent Recorder] (静默记录器)
        # 即使机器人未被唤醒，也需要记录上下文以便回答"上一句 xx 说了什么"。
        # 记录的是"模式处理后的最终内容"，避免 experts 模式泄漏原始 URL。
        # 主记忆仅存储纯语义内容，所有协议细节存入 artifacts。
        user_message_entry = {
            "role": "user",
            "content": final_content_blocks,
        }

        should_record = True
        if group_id:
             should_record = global_config.get("napcat.enable_silent_record", True)

        if should_record:
            # 主记忆：纯语义内容（无 metadata）
            await napcat_memory.append_async(group_id, user_id, user_message_entry)
            
            # Artifacts：使用标准 NapcatArtifact schema 存储协议细节
            strategy_cfg = global_config.get_soul().strategy
            routing_mode = strategy_cfg.routing_mode
            
            artifact = NapcatArtifact(
                role="user",
                content=final_content_blocks,  # 标准化后的多模态内容
                msg_id=msg_id,
                reply_to=reply_id,
                sender_name=user_name,
                text=clean_text,
                display_text=display_text,
                images=images,
                routing_mode=routing_mode,
            )
            
            # 仅在非 split_tasks 模式下保留原始图片 URL（供后续回溯）
            if routing_mode != "split_tasks" and images:
                artifact.original_images = images
            
            await napcat_memory.append_artifact_async(group_id, user_id, artifact.model_dump())

        external_history = await napcat_memory.get_context_async(
            group_id,
            user_id,
            for_soul=True,
        )
            
        # --- 7. Payload Construction (Standardized) (标准载荷构建) ---
        return {
            # 0. Preprocessed Marker
            "preprocessed": True,
            # 1. Core Content (核心内容 - 多模态结构)
            "content": final_content_blocks,

            # 2. Attention Protocol (注意力协议)
            "vessel_id": "napcat",                                     
            "source_type": "group" if group_id else "private",         
            "source_id": str(group_id) if group_id else str(user_id),  
            "is_strong_wake": is_strong_wake,                          
            "is_external_source": True,

            # 3. Context Metadata (上下文元数据)
            "name": user_name,            
            "metadata": {                 
                "user_id": user_id,
                "group_id": group_id,
                "reply_to": reply_id,
                **({"original_images": images} if routing_mode != "split_tasks" else {})
            },
            
            # 4. Memory Bridge (记忆桥接)
            "external_history": external_history
        }


    async def _process_expert_mode(self, base_text: str, images: list[str], is_wake: bool) -> list[dict]:
        """
        [Expert Mode] 处理逻辑:
        1. 若有图片，始终调用视觉专家生成 caption（注意力机制：图片即关注点）。
        2. 若无 brain，生成占位提示。
        3. 最终只返回纯文本块 (TextContent)，丢弃原始 Image URL。
        
        注意力管理机制：
        - 图片本身即强注意力信号，无论是否 @Bot 或触发唤醒词
        - 静默记录模式下也会进行视觉转述，确保记忆完整性
        """
        context_notes = []
        vision_caption = ""

        # A. Vision Expert Invocation (注意力机制：有图必处理)
        if images and self.brain_factory:
            try:
                # 暂时只处理第一张图
                img_url = images[0]
                # 构建临时消息请求 Brain 感知
                temp_msg = Message(
                    role="user",
                    content=[
                        TextContent(text="简要描述图片内容，突出关键信息，50 字以内。"),
                        ImageContent(image_url={"url": img_url})
                    ]
                )
                
                if hasattr(self.brain_factory, "perceive"):
                     vision_caption = await self.brain_factory.perceive(temp_msg)
                     if vision_caption:
                         logger.info(f"[NapcatCortex] 视觉感知结果：{vision_caption[:30]}...")

            except Exception as e:
                logger.error(f"[NapcatCortex] 视觉处理失败：{e}")

        # B. Caption Injection
        if vision_caption:
            context_notes.append(f"[系统视觉批注: 图片内容描述 - {vision_caption}]")
        elif images:
            # Fallback for un-captioned images in expert mode
            context_notes.append("[系统提示: 用户发送了一张图片，但视觉中枢未响应，内容未知]")
            
        # C. Text Assembly
        final_text = base_text
        if context_notes:
            final_text = f"{final_text}\n" + "\n".join(context_notes)
            
        return [{"type": "text", "text": final_text}]

    def _process_monolithic_mode(self, base_text: str, images: list[str]) -> list[dict]:
        """
        [Monolithic Mode] 处理逻辑:
        1. 直接保留原始文本块。
        2. 直接附加原始 Image URL 块。
        3. 不做任何本地视觉处理，完全依赖下游 Soul 的多模态能力。
        """
        blocks = [{"type": "text", "text": base_text}]
        
        if images:
            for img_url in images:
                blocks.append({"type": "image_url", "image_url": {"url": img_url}})
                
        return blocks


# Singleton instance
napcat_cortex = NapcatCortex()
