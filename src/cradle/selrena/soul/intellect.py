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

    def _preload_short_term_memories(self):
        """
        [DEPRECATED] Memory persistence is no longer handled by ShortTermMemory directly.
        This method is now a no-op to prevent errors until external session management is fully implemented.
        """
        pass

    async def _on_shutdown(self, signal: Any):
        logger.info("Soul 正在进入休眠...")
        await self.brain.cleanup()
        await self.senses.cleanup()

    def _get_short_term_memory(self, session_id: str) -> ShortTermMemory:
        """
        获取当前会话的短时记忆。
        注意：现在不再依赖具体的 user_id，而是统一的 session_id (对于单用户系统通常固定)。
        """
        # [Simplicity] Soul 应当只关注“当前对话对象”，而非维护庞大的用户列表
        # 如果需要多用户支持，应在 SessionManager 层处理
        if session_id not in self.short_term_store:
            self.short_term_store[session_id] = ShortTermMemory(
                max_history_len=self.config.memory.short_term_window
            )
        return self.short_term_store[session_id]

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
        
        # [Architectural Purity]
        # Soul 不再维护任何"访客"或"外部"会话状态。
        # 对于外部来源 (Napcat)，假定其上传的 Context 已经包含了所需的历史记录（由 Cortex 自行维护）。
        # Soul 只负责维护"主我"(Principal Ego) 的长期记忆流。
        source = event.source
        is_external_source = (source == "NapcatClient")

        if is_external_source:
             # 对于外部请求，Soul 不进行任何短时记忆维护
             # 使用一个临时的、空的 context 容器，完全依赖输入 payload 携带的信息
             # 也不应该去读取 ShortTermMemory，因为那是给主人用的
             stm = ShortTermMemory(max_history_len=0) 
        else:
            # 仅对主用户使用系统级短时记忆
            stm = self._get_short_term_memory("main_session")

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
        current_msg_obj = Message(role="user", content=final_content)
        
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
             
             chat_history_dicts = payload.get("external_history") if is_external_source else stm.get_messages()
             if chat_history_dicts is None:
                 chat_history_dicts = []
                 
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

            # [Isolation Logic]: 仅当是内部(主人)会话时，才存入长期记忆库
            # 外部对话被视为临时交互，不应污染 VectorStore
            if not is_external_source:
                try:
                    self.memory_vessel.memorize_episode(f"User: {perceived_text}")
                    self.memory_vessel.memorize_episode(f"Me: {clean_reply_text}", metadata={"is_bot": True})
                except Exception as e:
                     logger.warning(f"[Soul] 长时记忆写入失败: {e}")
            else:
                 # 对于外部会话，Soul 不做记忆留痕。
                 # 发出的 SpeakAction 可能会被 Napcat 捕获并回复，这也不关 Soul 的事
                 pass

            # 6. 表达 (Action)
            # [Simplification] Soul broadcasts thought; Synapse/Vessel decides routing based on last active context
            action = SpeakAction(
                source="Soul",
                text=clean_reply_text,
                emotion=detected_emotion
                # We removed explicit target binding here; let the Reflex/Router handle it if needed
                # or simply broadcast to the active channel.
            )
            # Inject raw targets back for now to keep existing Vessel logic working until further refactor
            # But conceptually Soul shouldn't care about IDs.
            if hasattr(action, 'target_user_id'): action.target_user_id = payload.get("user_id")
            if hasattr(action, 'target_group_id'): action.target_group_id = payload.get("group_id")
            
            await EventBus.publish(action)

        except Exception as e:
            logger.error(f"[Soul] 思考过程崩溃: {e}", exc_info=True)
