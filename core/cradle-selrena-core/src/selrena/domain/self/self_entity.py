"""
文件名称：self_entity.py
所属层级：领域层-自我核心
核心作用：月见全局唯一的自我实体，OC的灵魂根节点，单例模式，运行时人设不可篡改
设计原则：
1. 单例模式，整个进程内只有一个月见实例，保证人格连续唯一
2. 完全基于内核注入的冻结人设配置初始化，运行时不可修改
3. 所有核心子系统都内聚在这里，是OC的灵魂本体
4. 绝对不碰任何外界环境、平台、场景相关的逻辑
"""
from typing import Final
from selrena.core.config import PersonaConfig, InferenceConfig
from selrena.domain.conversation.scene_session import SceneSessionRuntime
from selrena.domain.emotion.emotion_system import EmotionSystem, EmotionType
from selrena.domain.memory.short_term_memory import ShortTermMemory
from selrena.domain.memory.long_term_memory import LongTermMemory
from selrena.domain.memory.knowledge_base import KnowledgeBase
from selrena.domain.thought.thought_system import ThoughtSystem
from selrena.domain.persona.persona_injector import PersonaInjector
from selrena.core.exceptions import ConfigException
from selrena.core.observability.logger import get_logger

# 初始化模块日志器
logger = get_logger("self_entity")


# ======================================
# 全局唯一自我实体（单例模式）
# ======================================
class SelrenaSelfEntity:
    """
    月见全局唯一自我实体，单例模式
    核心定位：OC的灵魂本体，所有意识、情绪、记忆的载体，运行时人设完全不可篡改
    真人逻辑对齐：对应人的自我意识，是所有心理活动的核心
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """单例模式，保证整个进程内只有一个月见实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        persona_config: PersonaConfig = None,
        inference_config: InferenceConfig = None
    ):
        """
        初始化自我实体，仅可执行一次，由内核注入配置
        参数：
            persona_config: 内核注入的冻结人设配置
            inference_config: 内核注入的冻结推理配置
        异常：
            ConfigException: 未注入配置时抛出
        """
        # 防止重复初始化，保证人格唯一
        if self._initialized:
            return
        # 必须由内核注入配置才能初始化，绝对不读本地文件
        if persona_config is None or inference_config is None:
            raise ConfigException("必须由内核注入人设和推理配置才能初始化自我实体")
        
        # ======================================
        # 冻结的核心配置，运行时不可修改
        # ======================================
        self.persona_config: Final[PersonaConfig] = persona_config
        self.inference_config: Final[InferenceConfig] = inference_config

        # ======================================
        # 核心子系统，终身唯一，不可替换
        # ======================================
        # 情绪系统
        self.emotion_system: Final[EmotionSystem] = EmotionSystem()
        # 长期记忆系统
        self.long_term_memory: Final[LongTermMemory] = LongTermMemory()
        # 独立知识库
        self.knowledge_base: Final[KnowledgeBase] = KnowledgeBase()
        # 人设注入器
        self.persona_injector: Final[PersonaInjector] = PersonaInjector()
        # 主动思维流系统（初始化时注入依赖）
        self.thought_system: Final[ThoughtSystem] = ThoughtSystem(
            emotion_system=self.emotion_system,
            long_term_memory=self.long_term_memory,
            persona_config=self.persona_config
        )
        # 场景运行时：会话态 + 短期记忆 + 并发锁
        self._scene_runtimes: Final[dict[str, SceneSessionRuntime]] = {}

        # ======================================
        # 运行状态
        # ======================================
        self.is_awake: bool = False
        # 标记为已初始化，不可重复初始化
        self._initialized = True

        logger.info(
            "月见自我实体初始化完成",
            name=self.persona_config.base.name,
            nickname=self.persona_config.base.nickname
        )

    def wake_up(self) -> None:
        """唤醒月见，仅内核可调用"""
        self.is_awake = True
        self.emotion_system.update(
            EmotionType.HAPPY,
            0.2,
            trigger="wake_up"
        )
        logger.info(f"{self.persona_config.base.nickname} 已醒来")

    def sleep(self) -> None:
        """让月见进入休眠，仅内核可调用"""
        self.is_awake = False
        self.emotion_system.update(
            EmotionType.CALM,
            0.1,
            trigger="sleep"
        )
        logger.info(f"{self.persona_config.base.nickname} 已进入休眠")

    def get_scene_runtime(self, scene_id: str) -> SceneSessionRuntime:
        """获取指定场景的运行时状态，不存在则自动创建。"""
        if scene_id not in self._scene_runtimes:
            memory_config = self.inference_config.memory
            short_term_max_length = max(
                memory_config.context_limit,
                memory_config.summary_trigger_count,
            )
            self._scene_runtimes[scene_id] = SceneSessionRuntime(
                scene_id=scene_id,
                short_term_max_length=short_term_max_length,
            )
        return self._scene_runtimes[scene_id]

    def get_short_term_memory(self, scene_id: str) -> ShortTermMemory:
        """
        获取指定场景的短期记忆，不存在则自动创建
        参数：
            scene_id: 场景唯一ID，由内核传入
        返回：对应场景的短期记忆实例
        核心作用：按场景完全隔离记忆，彻底避免串线
        """
        return self.get_scene_runtime(scene_id).short_term_memory

    def clear_short_term_memory(self, scene_id: str) -> None:
        """清空指定场景的短期记忆，会话结束时由内核调用"""
        if scene_id in self._scene_runtimes:
            self._scene_runtimes[scene_id].clear()
            del self._scene_runtimes[scene_id]
            logger.info("场景短期记忆已清空", scene_id=scene_id)

    def validate_boundary(self, content: str) -> bool:
        """
        边界红线校验，所有输出必须经过该校验
        参数：
            content: 待校验的生成内容
        返回：True=符合人设边界，False=突破红线
        """
        return self.persona_injector.validate_boundary(content)

    def get_state(self) -> dict:
        """
        获取当前完整状态，用于同步给内核和渲染层
        返回：标准化的状态字典
        """
        return {
            "name": self.persona_config.base.nickname,
            "is_awake": self.is_awake,
            "emotion": self.emotion_system.get_state(),
            "memory_count": len(self.long_term_memory.get_all_memories())
        }