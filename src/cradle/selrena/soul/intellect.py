import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

from cradle.schemas.configs.soul import SoulConfig
from cradle.schemas.domain.chat import Message
from cradle.schemas.protocol.events.base import BaseEvent
from cradle.schemas.protocol.events.action import ActionType, SpeakAction
from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath
from cradle.utils.string import extract_emotion_and_clean_text


from cradle.core.lifecycle import global_lifecycle
from ..synapse.event_bus import global_event_bus as EventBus
from ..vessel.perception.sensory_system import SensorySystem
from .memory.short_term import ShortTermMemory
from .memory.vector_store import MemoryVessel
from .persona import PersonaManager
from .brain.router import BrainFactory
from .brain.utils.prompt_builder import PromptBuilder
from .brain.utils.preprocessor import MultimodalPreprocessor


class SoulIntellect:
    """
    Soul Intellect (灵魂/中枢)

    【架构升级】：
    现在引入了 PerceptionSystem (感知系统)。
    流程变更为：UserMessage -> PerceptionSystem (提取感官信息) -> Brain (纯思考) -> Action
    """

    def __init__(self, config: SoulConfig):
        self.config = config
        self.brain = BrainFactory.create(config)
        self.persona = PersonaManager(config.persona)

        # 记忆系统 (Vessel is Singleton)
        self.memory_vessel = MemoryVessel()

        # 短时记忆 (按 User ID 隔离)
        self.short_term_store: Dict[str, ShortTermMemory] = {}

        # 躯体感官 (Body Sensors)
        # 通过神经连接接收外界信息
        self.senses = SensorySystem(config)

    async def initialize(self):
        logger.info(f"灵魂 ({self.config.persona.name}) 已苏醒...")
        global_lifecycle.register(self)

        # --- [Phase 1: 记忆构建 (Memory Construction)] ---
        # 优先加载记忆系统，确保在核心思考启动前拥有基础上下文 (Context)。
        # 这有助于提高首次交互的响应速度，并避免因记忆未就绪导致的冷启动卡顿。
        
        # 1.1 加载长时向量记忆 (Heavy IO)
        try:
            self.memory_vessel.initialize()
        except Exception as e:
            logger.error(f"[Soul] 长时记忆系统启动失败: {e}", exc_info=True)

        # 1.2 预热短时对话记忆 (Light IO) -> 提前加载所有已知用户的对话历史
        await self._preload_short_term_memories()

        # --- [Phase 2: 认知核心 (Cognitive Core)] ---
        # 加载大脑/LLM (Heavy Compute/VRAM)
        await self.brain.initialize()

        # --- [Phase 3: 感知接入 (Sensory Connection)] ---
        await self.senses.initialize()

        # --- [Phase 4: 神经监听 (Neural Listening)] ---
        EventBus.subscribe("input.user_message", self._on_hear)
        EventBus.subscribe("system.shutdown", self._on_shutdown)

    async def _preload_short_term_memories(self):
        """
        预加载所有已存在的短时记忆会话文件。
        遍历 data/memory/short_term_*.json，并提前实例化到内存缓存中。
        """
        try:
            # 引入 ProjectPath 辅助扫描
            from cradle.utils.path import ProjectPath
            
            memory_dir = ProjectPath.DATA_MEMORY
            if not memory_dir.exists():
                return
            
            # 扫描所有以 short_term_ 开头的 JSON 文件
            # Pattern: short_term_{sanitized_key}.json
            files = list(memory_dir.glob("short_term_*.json"))
            if not files:
                return

            logger.info(f"[Soul] 正在预热所发现的 {len(files)} 个短时记忆存档...")
            
            count = 0
            for f in files:
                try:
                    # 提取文件名中的 Session Key (去除前缀 'short_term_' 和后缀 '.json')
                    stem = f.stem # e.g. "short_term_user_123"
                    if len(stem) > 11 and stem.startswith("short_term_"):
                        key = stem[11:] # "user_123"
                        if key:
                            # 实例化时会自动触发 load() 读取文件内容
                            stm = ShortTermMemory(
                                max_history_len=self.config.memory.short_term_window,
                                session_key=key
                            )
                            # 加载成功后存入缓存
                            self.short_term_store[key] = stm
                            count += 1
                except Exception as ex:
                    logger.warning(f"[Soul] 预加载短时记忆文件 '{f.name}' 失败: {ex}")
            
            if count > 0:
                logger.info(f"[Soul] 短时记忆预热完成 (Loaded: {count}/{len(files)})")

        except Exception as e:
            logger.error(f"[Soul] 短时记忆预热流程异常: {e}")

    async def _on_shutdown(self, signal: Any):
        logger.info("Soul 正在进入休眠...")
        await self.brain.cleanup()
        await self.senses.cleanup()

    def _get_short_term_memory(self, user_id: str) -> ShortTermMemory:
        if user_id not in self.short_term_store:
            # 这里的 session_key 应该是 user_id
            self.short_term_store[user_id] = ShortTermMemory(
                max_history_len=self.config.memory.short_term_window,
                session_key=user_id
            )
        return self.short_term_store[user_id]

    async def _on_hear(self, event: BaseEvent):
        """
        听到用户消息 -> 感知 -> 检索记忆 -> 思考 -> 行动
        """
        payload = event.payload if isinstance(event.payload, dict) else {}

        # [Optimized] 使用 MultimodalPreprocessor 进行消息标准化与预处理
        # 自动去除 CQ 码、腾讯多媒体 URL 等占位符，返回标准化结果
        text, has_visual, is_valid = MultimodalPreprocessor.validate_ingress_payload(payload)

        # [Anti-Redundancy] 如果既没有有效文本，也没有视觉组件，说明是纯占位符消息
        if not is_valid:
             logger.debug("[Soul] 忽略纯 CQ 码/占位符消息，等待视觉事件...")
             return

        user_id = str(payload.get("user_id", "unknown"))
        target_user_id = payload.get("user_id") if isinstance(
            payload.get("user_id"), int) else None
        target_group_id = payload.get("group_id") if isinstance(
            payload.get("group_id"), int) else None

        logger.info(f"[Soul] 意识到: {text[:30]}...")
        stm = self._get_short_term_memory(user_id)

        # 1. 加载相关记忆 (Associative Memory)
        try:
            relevant_memories = self.memory_vessel.recall_episode(
                text, n_results=3)
        except Exception as e:
            logger.warning(f"[Soul] 记忆回溯失败: {e}")
            relevant_memories = []

        # 2. 感知现实 (Perception via Vessel)
        # 强制使用 content，不再依赖 text 回退
        initial_content = payload.get("content")
        
        # [Strict Mode] 如果没有 content，则直接返回
        if not initial_content:
             logger.warning("[Soul] 收到空内容感知消息，忽略")
             return
                 
        raw_msg_dict = {"role": "user", "content": initial_content}

        try:
            # 感官模块返回标准化后的 content (List[ContentBlock])
            # 注意：senses.perceive 可能会修改或扩展 content (如 OCR)
            perceived_msg_dict = await self.senses.perceive(raw_msg_dict)
            final_content = perceived_msg_dict.get("content") or initial_content
            
            # 使用 MultimodalPreprocessor 提取纯文本用于记忆索引 (Search Index)
            perceived_text = MultimodalPreprocessor.extract_pure_text(final_content)

        except Exception as e:
            logger.error(f"[Soul] 感知模块异常: {e}")
            final_content = initial_content
            perceived_text = MultimodalPreprocessor.extract_pure_text(initial_content)

            
        # [Validation] 确保 final_content 非空
        if not final_content:
             return

        # [Vision Optimization] 专家分工：如果是视觉消息，尝试获取视觉转述用于记忆
        # 避免将巨大的 Base64 或临时 URL 存入长期记忆
        vision_caption = ""
        current_msg_obj = Message(role=user_id if user_id in ["user", "assistant"] else "user", content=final_content)
        
        if MultimodalPreprocessor.has_visual_content(current_msg_obj):
            try:
                # 让大脑的视觉中心 (Visual Center) 进行转述
                logger.info("[Soul] 正在调用视觉专家进行记忆转述...")
                vision_caption = await self.brain.perceive(current_msg_obj)
                
                if vision_caption:
                    logger.info(f"[Soul] 视觉转述完成: {vision_caption[:30]}...")
                    # 增强用于记忆的纯文本：保留用户原话 + [视觉备注]
                    perceived_text = f"{perceived_text}\n[Vision Memory: {vision_caption}]".strip()
            except Exception as ve:
                logger.warning(f"[Soul] 视觉转述失败，仅存储原始文本: {ve}")

        # 3. 构建思考上下文 (Context Window)
        # 确保 Message 的 content 字段接收符合 Schema 的数据
        try:
             persona_dict = self.persona.build_system_prompt()
             persona_msg = Message(**persona_dict)
             
             chat_history_dicts = stm.get_messages()
             # 对历史消息进行清洗，确保它们也是有效的 Message 对象
             chat_history_objs = MultimodalPreprocessor.normalize_messages(chat_history_dicts)
             
             # 注意：传给 Brain 的是包含原始图片的多模态 content，确保它能“看到”
             context_messages = PromptBuilder.build_context_window(
                persona_msg,
                relevant_memories,
                chat_history_objs,
                final_content
            )
        except Exception as e:
            logger.error(f"[Soul] 构建上下文失败: {e}")
            return
        if relevant_memories:
            logger.debug(f"[Soul] 已注入 {len(relevant_memories)} 条相关记忆")

        # 4. 核心思考 (Cognition)
        try:
            # Brain accepts list of Message objects now
            reply_text = await self.brain.generate(context_messages)

            if not reply_text:
                logger.warning("[Soul] 大脑一片空白 (Empty response)")
                reply_text = PromptBuilder.build_fallback_message(
                    "empty_response")

            clean_reply_text, detected_emotion = extract_emotion_and_clean_text(
                reply_text)
            if not clean_reply_text:
                clean_reply_text = reply_text

            logger.info(f"[Soul] 生成意识: {clean_reply_text[:50]}...")

            # 5. 记忆固化 (Consolidation)
            stm.add("user", perceived_text)
            stm.add("assistant", clean_reply_text)

            try:
                self.memory_vessel.memorize_episode(
                    f"User: {perceived_text}", metadata={"user_id": user_id})
                self.memory_vessel.memorize_episode(f"Me: {clean_reply_text}", metadata={
                                                    "user_id": user_id, "is_bot": True})
            except Exception as e:
                logger.warning(f"[Soul] 长时记忆写入失败: {e}")

            # 6. 表达 (Action)
            action = SpeakAction(
                source="Soul",
                text=clean_reply_text,
                emotion=detected_emotion,
                target_user_id=target_user_id,
                target_group_id=target_group_id,
            )
            await EventBus.publish(action)

        except Exception as e:
            logger.error(f"[Soul] 思考过程崩溃: {e}", exc_info=True)
