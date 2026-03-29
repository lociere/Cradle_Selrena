"""
文件名称：thought_system.py
所属层级：领域层-思维模块
核心作用：实现月见的主动思维流，让她不是只有用户说话才活着，会自己发呆、思考、回忆
设计原则：
1. 由内核的生命时钟驱动，持续运行
2. 完全基于人设、情绪、记忆生成，符合真人逻辑
3. 无硬编码规则，所有思维都符合月见的性格
4. 仅做思维生成，不碰场景规则
"""
import random
from typing import List
from selrena.core.config import PersonaConfig
from selrena.domain.emotion.emotion_system import EmotionSystem
from selrena.domain.memory.long_term_memory import LongTermMemory
from selrena.domain.thought.thought_pool import ThoughtPool
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("thought_system")


# ======================================
# 主动思维流系统
# ======================================
class ThoughtSystem:
    """
    月见的主动思维流系统核心
    核心作用：让她有自己的内心世界，不是只会响应消息的机器人
    真人逻辑对齐：对应人脑的走神、发呆、内心活动，不需要外界触发也会自己思考
    """
    def __init__(
        self,
        emotion_system: EmotionSystem,
        long_term_memory: LongTermMemory,
        persona_config: PersonaConfig
    ):
        """
        初始化思维系统
        参数：
            emotion_system: 情绪系统实例
            long_term_memory: 长期记忆实例
            persona_config: 人设配置
        """
        self.emotion_system = emotion_system
        self.long_term_memory = long_term_memory
        self.persona_config = persona_config
        self._thought_pool = ThoughtPool()
        logger.info("主动思维流系统初始化完成")

    def generate_thought(self) -> str:
        """
        生成一次主动思维，由内核的生命时钟驱动
        返回：内心活动内容
        核心逻辑：基于当前情绪、记忆、人设，生成符合她性格的思维
        """
        current_emotion = self.emotion_system.current_state.emotion_type.value
        thought_candidates: List[str] = self._thought_pool.get_candidates(current_emotion)

        # 注入轻量反思记忆，不绑定主动思维模式，避免 domain 被单一场景绑死。
        all_memories = self.long_term_memory.get_all_memories()
        if all_memories:
            selected = random.choice(all_memories)
            thought_candidates.append(f"想到一段记忆：{selected.content[:24]}")

        thought = random.choice(thought_candidates)
        logger.debug("主动思维生成完成", thought=thought)

        return thought