from cradle.utils.string import sanitize_text
from cradle.selrena.synapse.event_bus import global_event_bus
from cradle.utils.logger import logger
from cradle.selrena.soul.memory.short_term import ShortTermMemory
from cradle.selrena.soul.memory.vector_store import global_memory_vessel
from cradle.core.config_manager import global_config
from datetime import datetime
from cradle.schemas.protocol.events.action import SpeakAction
from cradle.schemas.protocol.events import BaseEvent
from .brain import BrainFactory
import asyncio
import re

class SoulIntellect:
    """
    灵魂思维核心：负责处理感知到的信息并生成意志
    """
    def __init__(self):
        # 使用全局配置管理器
        # 获取完整的灵魂层配置
        self.soul_config = global_config.get_soul()
        self.llm_config = self.soul_config.llm
        self.brain = None

        
        # 智能与模拟模式切换
        if self.soul_config.is_mock_mode:
            logger.info("[Soul] 运行于情感模拟模式 (Mock Mode)。")
        else:
            # 使用工厂模式创建大脑 (传入完整的 soul_config 以支持混合动力 router)
            self.brain = BrainFactory.create(self.soul_config)
        
        # 升级为持久化记忆系统
        self.memory = ShortTermMemory()
        
        # 【架构升级】连接到感知皮层 (SensoryCortex) 的意识流
        # input.user_message 是经过注意力过滤与多模态对齐的消息
        global_event_bus.subscribe("input.user_message", self._on_hear)
        # 移除底层的 signal:woken_up，因为 Cortex 会决定是否传达信息
        logger.info(f"灵魂 (Soul) 已苏醒，加载人格: {global_config.persona.name}")
        
    async def initialize(self):
        """异步初始化 (用于加载本地模型)"""
        # 1. 挂载长期记忆 (向量库)
        # 这可能需要几秒钟加载 Embedding 模型
        global_memory_vessel.initialize()

        # 2. 激活大脑 (Brain)
        if self.brain:
            await self.brain.initialize()

    async def _on_wake_up(self, event: BaseEvent):
        """(Deprecated)"""
        pass

    async def _on_hear(self, event: BaseEvent):
        """当意识到外界信息时"""
        # 兼容旧的字符串 Payload 或新的 Dict Payload
        payload = event.payload
        if isinstance(payload, dict):
            user_text = payload.get("text", "")
        else:
            user_text = str(payload)
            
        # [Sanitize Input] 清洗 SenseVoice 的特殊标签 (<|zh|>, <|emotion|>, etc.)
        user_text = re.sub(r"<\|.*?\|>", "", user_text).strip()
        if not user_text:
            return  # 忽略空语音
            
        logger.info(f"[Soul] 意识到: {user_text}")

        # 1. 将外界信息存入短期记忆
        self.memory.add("user", user_text)

        # 2. 调用 LLM 思考 或 模拟回复
        try:
            if self.soul_config.is_mock_mode:
                # 模拟模式：直接返回预设回复（支持简单格式化）
                await asyncio.sleep(1) # 模拟思考延迟
                reply_text = self.soul_config.mock_response.format(user=user_text)
            else:
                # 智能模式：请求 LLM
                # 动态获取当前人设 Prompt (确保配置文件修改后即时生效)
                current_system_prompt = global_config.persona.get_system_prompt()

                # --- Memory Injection (Project Mnemosyne) ---
                try:
                    # 检索相关长期记忆
                    related_memories = global_memory_vessel.recall_episode(user_text, n_results=3)
                    if related_memories:
                        # 过滤过短的记忆并拼接
                        valid_memories = [m for m in related_memories if isinstance(m, str) and len(m) > 5]
                        if valid_memories:
                            memory_context_str = "\n".join(f"- {m}" for m in valid_memories)
                            # 注入到 System Prompt 尾部
                            current_system_prompt += f"\n\n【相关回忆/Earlier Memories】:\n{memory_context_str}\n(参考这些回忆进行回答)"
                            logger.debug(f"[Soul] 已注入 {len(valid_memories)} 条相关记忆")
                except Exception as mem_err:
                    logger.warning(f"[Soul] 记忆检索失败: {mem_err}")
                # --------------------------------------------
                
                # 组装上下文 (System + History)
                messages_payload = self.memory.get_messages(
                    include_system=True, 
                    system_prompt=current_system_prompt
                )

                # 抽象生成调用
                reply_text = await self.brain.generate(messages_payload)
                logger.debug(f"[soul]生成:{reply_text}")
                
            # 使用独立文本清洗工具
            reply_text = sanitize_text(reply_text)
            
            # 3. 将自己的思考结果存入记忆 (Short Term)
            self.memory.add("assistant", reply_text)

            logger.info(f"[Soul] 生成意识意志: {reply_text}")
            
            # 4. 思考完毕，通过神经发送“想说的话”给嘴巴 (使用新协议)
            action = SpeakAction(text=reply_text, source="Soul")
            await global_event_bus.publish(action)
            
            # --- Memory Consolidation (Long Term) ---
            try:
                # 简单的即时存储 (未来可优化为异步摘要后存储)
                episode_text = f"User: {user_text}\nSelrena: {reply_text}"
                global_memory_vessel.memorize_episode(
                    episode_text, 
                    {"timestamp": datetime.now().isoformat(), "source": "chat"}
                )
            except Exception as save_err:
                logger.warning(f"[Soul] 长期记忆存储失败: {save_err}")
            # ----------------------------------------
            
        except Exception as e:
            logger.error(f"[Soul Error] 灵魂思考短路: {e}")


    async def cleanup(self):
        """
        生命周期钩子：系统关闭或组件卸载前调用
        1. 断开神经连接
        2. 保存记忆
        """
        logger.info("[Soul] 正在断开神经连接...")
        global_event_bus.unsubscribe_receiver(self)
        
        if self.brain:
            await self.brain.cleanup()
            
        logger.info("[Soul] 正在整理思绪(保存记忆)...")
        if self.memory:
            self.memory.save()
        logger.info("[Soul] 意识上传完成，已安全离线。")
