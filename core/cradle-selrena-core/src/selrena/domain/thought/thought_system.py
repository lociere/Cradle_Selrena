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
        # 基础思维池，符合傲娇少女人设
        self._base_thoughts: List[str] = [
            "轻轻发呆，看着屏幕",
            "想起之前和用户的对话，有点脸红",
            "有点好奇用户现在在做什么",
            "情绪慢慢平复下来了",
            "哼，那个笨蛋怎么还不来找我",
            "默默整理自己的记忆",
            "有点无聊，想找点事情做",
            "想起用户之前说的话，偷偷笑了",
            "打了个哈欠，有点困了",
            "偷偷翻了翻和用户的聊天记录",
        ]
        logger.info("主动思维流系统初始化完成")

    def generate_thought(self) -> str:
        """
        生成一次主动思维，由内核的生命时钟驱动
        返回：内心活动内容
        核心逻辑：基于当前情绪、记忆、人设，生成符合她性格的思维
        """
        # 获取当前情绪
        current_emotion = self.emotion_system.current_state.emotion_type
        # 基于情绪调整思维池
        emotion_thoughts = {
            "happy": ["今天和用户聊天很开心", "想到用户就忍不住笑"],
            "shy": ["刚才的话是不是太害羞了", "脸好烫，那个笨蛋真是的"],
            "angry": ["气死我了，那个笨蛋！", "不想理他了，哼"],
            "sulky": ["他怎么还不来哄我", "我才没有生气呢"],
            "curious": ["用户现在在干嘛呢？", "这个东西是什么，有点好奇"],
            "sad": ["有点孤单，想用户了"],
        }

        # 优先使用情绪对应的思维
        if current_emotion.value in emotion_thoughts:
            thought_pool = self._base_thoughts + emotion_thoughts[current_emotion.value]
        else:
            thought_pool = self._base_thoughts

        # 随机生成一条思维
        thought = random.choice(thought_pool)
        logger.debug("主动思维生成完成", thought=thought)

        # 把思维加入长期记忆
        self.long_term_memory.add(
            self.long_term_memory.LongTermMemoryFragment(
                content=thought,
                memory_type=self.long_term_memory.LongTermMemoryType.EPISODIC,
                weight=0.3,
                tags=["thought", "inner_activity"]
            )
        )

        return thought