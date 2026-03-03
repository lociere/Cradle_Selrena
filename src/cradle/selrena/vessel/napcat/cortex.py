from typing import Any, Dict, List, Optional
import asyncio

from cradle.core.config_manager import global_config
from cradle.schemas.domain.chat import Message
from cradle.schemas.domain.multimodal import ImageContent, TextContent
from cradle.utils.logger import logger

from .memory.short_term import napcat_memory
from .tools.parser import NapcatMessageCleaner, NapcatMessageParser

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
        :param brain_factory: Optional reference to BrainFactory for using Vision models.
                              Ideally this should be injected or accessed via a service locator.
        """
        self.brain_factory = brain_factory 
        # Note: We depend on the caller to inject the brain_factory or similar service
        # to avoid circular imports.

    async def proccess_ingress(self, raw_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Main Pipeline: Raw Napcat Event -> Processed Event for Soul
        """
        if raw_event.get("post_type") != "message":
            return None # Ignore non-message events for cognitive processing

        # 1. Parse Basic Info
        user_id = raw_event.get("user_id")
        group_id = raw_event.get("group_id")
        raw_msg = raw_event.get("raw_message", "")
        msg_chain = raw_event.get("message", []) # Array format
        
        # [New] Parse Sender Info (Nickname/Card)
        sender = raw_event.get("sender", {})
        # Prefer group card (card) over global nickname (nickname)
        user_name = sender.get("card") or sender.get("nickname") or f"User{user_id}"

        # 2. Advanced Parsing (At, Reply, Images)
        if isinstance(msg_chain, list):
            parsed = NapcatMessageParser.normalize_message_chain(msg_chain)
        else:
            # Fallback for string format
            parsed = NapcatMessageParser.parse_cq_codes(raw_msg)
        
        # [Enhancement] Resolve At placeholders 
        # (Since we don't have async client here, we use a generic label locally, 
        # relying on Soul to understand context or future client injection)
        raw_clean_text = parsed["text"]
        # TODO: If we had access to group member list cache, we'd replace QQ with Nicknames here.
        # For now, we clean up the marker to be readable.
        import re
        clean_text = re.sub(r' \[HQ:at,qq=(\d+)\] ', r'[@\1]', raw_clean_text)

        images = parsed["images"]
        reply_id = parsed["reply_to"]
        
        # 3. Memory Update (Store Raw Context for *this* session)
        # Store what user actually sent (including image URLs if present)
        # [Standardization]: Store as Message-compatible dict
        # [Enhancement]: Store msg_id for future replies
        msg_id = raw_event.get("message_id")
        
        metadata = {
             "original_images": images,
             "reply_to": reply_id,
             "sender_name": user_name,
             "msg_id": msg_id
        }
        
        # [User Labeling & Reply Context]
        prefix = f"[{user_name}]"
        
        # Try to find reply context
        if reply_id:
             # Search locally in short term memory
             # This is a simple linear scan; for production consider a dict index
             history = napcat_memory.get_context(group_id, user_id)
             reply_target_name = "某人"
             reply_summary = ""
             
             for msg in reversed(history):
                  m_meta = msg.get("metadata", {})
                  if m_meta.get("msg_id") == reply_id:  # Found it!
                       reply_target_name = m_meta.get("sender_name", "User")
                       # Extract text summary
                       content = msg.get("content", "")
                       if isinstance(content, list):
                            # extract first text block
                            for block in content:
                                 if isinstance(block, dict) and block.get("type") == "text":
                                      reply_summary = block.get("text", "")[:10] + "..."
                                      break
                       elif isinstance(content, str):
                            reply_summary = content[:10] + "..."
                       break
             
             prefix = f"{prefix} (回复 @{reply_target_name} \"{reply_summary}\")"

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

        user_message_entry = {
            "role": "user",
            "content": msg_content,
            "metadata": metadata
        }
        
        # [Silent Record Config]: 检查是否开启“群聊静默记录”
        # 即使机器人未被唤醒，也需要记录上下文以便回答“上一句xx说了什么”
        should_record = True
        if group_id:
             should_record = global_config.get("napcat.enable_silent_record", True)
             
        if should_record:
            napcat_memory.append(group_id, user_id, user_message_entry)

        # [Wake Word Logic]: 唤醒判定逻辑
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

        # 4. Expert Processing (Vision): 视觉专家处理
        # [优化]: 为了节省 Token 和费用，仅在“强唤醒”状态下调用昂贵的视觉模型
        vision_caption = ""
        if images and self.brain_factory and is_strong_wake:
            try:
                # 暂时只处理第一张图
                if images:
                    img_url = images[0]
                    # 构建临时消息请求 Brain 感知
                    temp_msg = Message(
                        role="user",
                        content=[
                            TextContent(text="请描述这张图片"),
                            ImageContent(image_url={"url": img_url})
                        ]
                    )
                    
                    if hasattr(self.brain_factory, "perceive"):
                         vision_caption = await self.brain_factory.perceive(temp_msg)
                         if vision_caption:
                             logger.info(f"[NapcatCortex] 视觉感知结果: {vision_caption[:30]}...")

            except Exception as e:
                logger.error(f"[NapcatCortex] 视觉处理失败: {e}")

        # 5. Assemble Final Prompt: 组装最终提示词
        # 将发送者身份、视觉描述、引用文本融合进单一文本流，降低 Soul 层解析成本。
        
        # [System Integration]: 嵌入身份标识
        if group_id:
            final_prompt_text = f"[{user_name}]: {clean_text}"
        else:
            final_prompt_text = clean_text 
        
        # [Context Injection]: 注入视觉描述
        if vision_caption:
            final_prompt_text = f"{final_prompt_text}\n[系统视觉批注: 用户发送了一张图片，内容描述：{vision_caption}]"
        elif images and not vision_caption:
            final_prompt_text = f"{final_prompt_text}\n[系统提示: 用户发送了一张图片]"

        # 6. Validate: 空消息拦截
        if not final_prompt_text.strip() and not images:
            logger.debug("[NapcatCortex] 清洗后无有效内容，忽略。")
            return None

        # 7. Payload Generation: 生成标准化载荷
        return {
            # --- Standard Identity Protocol (标准化身份协议) ---
            # Reflex 仅依赖这三项进行注意力路由，完全解耦业务逻辑
            "vessel_id": "napcat",                                     # 模块标识
            "source_type": "group" if group_id else "private",         # 状态分支类型
            "source_id": str(group_id) if group_id else str(user_id),  # 状态对象ID

            # --- Business Payload (业务数据) ---
            # 透传给 Soul 进行语义处理
            "user_id": user_id,
            "group_id": group_id,
            "name": user_name,            # 用户昵称
            "content": final_prompt_text, # 已融合上下文的纯文本
            "original_images": images,    # 原始图片链接列表
            
            # --- Signals (控制信号) ---
            "is_strong_wake": is_strong_wake, # 是否强唤醒 (Reflex 状态机输入)
            
            # [Memory Isolation]: 注入短时记忆上下文
            "external_history": napcat_memory.get_context(group_id, user_id) 
        }

# Singleton instance
napcat_cortex = NapcatCortex()
